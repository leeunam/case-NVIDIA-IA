"""LangGraph-ready orchestration facade for the scraping pipeline.

The domain modules stay small and testable; this file provides one stable
surface for future graph nodes or CLI/application entrypoints.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from nvidia_startup_intel.ai_native_assessment import AINativeAssessment, assess_ai_native_maturity
from nvidia_startup_intel.collection_quality import (
    CollectionQualitySummary,
    summarize_collection_quality,
)
from nvidia_startup_intel.discovery import CandidateStartup, RawDiscoveryResult, discover_candidate_startups
from nvidia_startup_intel.evidence import FieldEvidenceGroup, claims_from_profile, structure_evidence_by_field
from nvidia_startup_intel.page_collection import (
    CollectedPage,
    FetchResponse,
    Fetcher,
    PageCollectionResult,
    collect_public_pages,
)
from nvidia_startup_intel.scraping_policy import ScrapingPolicy
from nvidia_startup_intel.robots import RobotsCache
from nvidia_startup_intel.search_execution import SearchClient, SearchExecutionError, execute_search_plan
from nvidia_startup_intel.search_params import UNKNOWN, SearchParams, parse_search_params
from nvidia_startup_intel.search_plan import SearchPlan, build_search_plan
from nvidia_startup_intel.startup_profile import StartupProfile, extract_startup_profile


@dataclass(frozen=True)
class ScrapingPipelineResult:
    search_params: SearchParams
    search_plan: SearchPlan
    candidates: tuple[CandidateStartup, ...]
    collected_pages_by_candidate: Mapping[str, PageCollectionResult]
    profiles: tuple[StartupProfile, ...]
    evidence_groups_by_profile: Mapping[str, tuple[FieldEvidenceGroup, ...]]
    quality_summary: CollectionQualitySummary
    search_errors: tuple[SearchExecutionError, ...] = ()


def plan_startup_search(query: str, *, limit: int | None = None) -> tuple[SearchParams, SearchPlan]:
    """Parse a user query and build deterministic search terms."""

    params = parse_search_params(query, limit=limit)
    return params, build_search_plan(params)


def build_candidates(
    raw_results: list[RawDiscoveryResult] | tuple[RawDiscoveryResult, ...],
    *,
    limit: int | None = None,
) -> tuple[CandidateStartup, ...]:
    """Convert executed search results into deduplicated startup candidates."""

    return tuple(discover_candidate_startups(raw_results, limit=limit))


def collect_pages_for_candidates(
    candidates: list[CandidateStartup] | tuple[CandidateStartup, ...],
    *,
    fetcher: Fetcher | None = None,
    scraping_policy: ScrapingPolicy | None = None,
    robots_cache: RobotsCache | None = None,
    max_pages_per_candidate: int = 5,
    max_depth: int = 1,
) -> dict[str, PageCollectionResult]:
    """Collect public pages for candidates that have an official site."""

    collected: dict[str, PageCollectionResult] = {}
    for candidate in candidates:
        if candidate.primary_url == UNKNOWN:
            continue
        collected[candidate.name] = collect_public_pages(
            candidate.primary_url,
            fetcher=fetcher,
            max_pages=max_pages_per_candidate,
            max_depth=max_depth,
            scraping_policy=scraping_policy,
            robots_cache=robots_cache,
        )
    return collected


def extract_profiles_for_candidates(
    candidates: list[CandidateStartup] | tuple[CandidateStartup, ...],
    collected_pages_by_candidate: Mapping[str, PageCollectionResult],
) -> tuple[StartupProfile, ...]:
    """Extract evidence-backed profiles from collected pages."""

    profiles: list[StartupProfile] = []
    for candidate in candidates:
        collection_result = collected_pages_by_candidate.get(candidate.name)
        pages = collection_result.pages if collection_result else ()
        profiles.append(
            extract_startup_profile(
                pages,
                fallback_company_name=candidate.name,
                official_site=candidate.primary_url,
            )
        )
    return tuple(profiles)


def structure_profile_evidence(
    profiles: list[StartupProfile] | tuple[StartupProfile, ...],
) -> dict[str, tuple[FieldEvidenceGroup, ...]]:
    """Group profile evidences by field for each startup profile."""

    return {
        profile.company_name.value: structure_evidence_by_field(claims_from_profile(profile))
        for profile in profiles
    }


def assess_profiles_ai_native(
    profiles: list[StartupProfile] | tuple[StartupProfile, ...],
    evidence_groups_by_profile: Mapping[str, tuple[FieldEvidenceGroup, ...]],
    quality_summary: CollectionQualitySummary,
    *,
    run_id: str,
) -> dict[str, AINativeAssessment]:
    """Assess profiles that are ready for AI-native evaluation."""

    if not quality_summary.ready_for_evaluation:
        return {}

    assessments: dict[str, AINativeAssessment] = {}
    for profile in profiles:
        company_name = profile.company_name.value
        assessments[company_name] = assess_ai_native_maturity(
            profile,
            evidence_groups_by_profile.get(company_name, ()),
            quality_summary,
            run_id=run_id,
        )
    return assessments


def run_scraping_pipeline(
    query: str,
    raw_results: list[RawDiscoveryResult] | tuple[RawDiscoveryResult, ...],
    *,
    fetcher: Fetcher | None = None,
    scraping_policy: ScrapingPolicy | None = None,
    robots_cache: RobotsCache | None = None,
    limit: int | None = None,
    max_pages_per_candidate: int = 5,
    max_depth: int = 1,
) -> ScrapingPipelineResult:
    """Run the offline scraping pipeline after search results are available."""

    params, plan = plan_startup_search(query, limit=limit)
    candidates = build_candidates(raw_results, limit=params.limit)
    collected_pages = collect_pages_for_candidates(
        candidates,
        fetcher=fetcher,
        scraping_policy=scraping_policy,
        robots_cache=robots_cache,
        max_pages_per_candidate=max_pages_per_candidate,
        max_depth=max_depth,
    )
    profiles = extract_profiles_for_candidates(candidates, collected_pages)
    evidence_groups = structure_profile_evidence(profiles)
    quality_summary = summarize_collection_quality(
        candidates,
        profiles,
        collection_results_by_source=collected_pages,
    )

    return ScrapingPipelineResult(
        search_params=params,
        search_plan=plan,
        candidates=candidates,
        search_errors=(),
        collected_pages_by_candidate=collected_pages,
        profiles=profiles,
        evidence_groups_by_profile=evidence_groups,
        quality_summary=quality_summary,
    )


def run_scraping_pipeline_with_search(
    query: str,
    search_client: SearchClient,
    *,
    fetcher: Fetcher | None = None,
    scraping_policy: ScrapingPolicy | None = None,
    robots_cache: RobotsCache | None = None,
    limit: int | None = None,
    per_term_limit: int = 5,
    max_pages_per_candidate: int = 5,
    max_depth: int = 1,
) -> ScrapingPipelineResult:
    """Run the full scraping pipeline, including search plan execution."""

    params, plan = plan_startup_search(query, limit=limit)
    execution = execute_search_plan(
        plan,
        search_client,
        per_term_limit=per_term_limit,
        total_limit=params.limit,
    )
    candidates = build_candidates(execution.raw_results, limit=params.limit)
    collected_pages = collect_pages_for_candidates(
        candidates,
        fetcher=fetcher,
        scraping_policy=scraping_policy,
        robots_cache=robots_cache,
        max_pages_per_candidate=max_pages_per_candidate,
        max_depth=max_depth,
    )
    profiles = extract_profiles_for_candidates(candidates, collected_pages)
    evidence_groups = structure_profile_evidence(profiles)
    quality_summary = summarize_collection_quality(
        candidates,
        profiles,
        collection_results_by_source=collected_pages,
    )

    return ScrapingPipelineResult(
        search_params=params,
        search_plan=plan,
        candidates=candidates,
        search_errors=execution.errors,
        collected_pages_by_candidate=collected_pages,
        profiles=profiles,
        evidence_groups_by_profile=evidence_groups,
        quality_summary=quality_summary,
    )


def fixture_fetcher(pages: Mapping[str, FetchResponse]) -> Fetcher:
    """Build a deterministic fetcher for local fixtures and tests."""

    def fetch(url: str) -> FetchResponse:
        return pages[url]

    return fetch
