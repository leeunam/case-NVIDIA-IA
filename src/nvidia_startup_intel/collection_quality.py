"""Collection quality metrics for pipeline runs.

This module summarizes whether discovery, collection, and extraction produced
enough sourced data to move into AI-native evaluation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace

from nvidia_startup_intel.discovery import CandidateStartup
from nvidia_startup_intel.page_collection import PageCollectionResult
from nvidia_startup_intel.search_params import UNKNOWN
from nvidia_startup_intel.startup_profile import ProfileField, StartupProfile


MINIMUM_PROFILE_FIELDS = (
    "company_name",
    "official_site",
    "company_summary",
    "sector",
    "product",
    "ai_signals",
)


@dataclass(frozen=True)
class SourceQualitySummary:
    source_name: str
    attempts: int
    successes: int
    failures: int
    success_rate: float


@dataclass(frozen=True)
class CollectionQualitySummary:
    candidate_count: int
    official_site_found_count: int
    official_site_found_rate: float
    minimum_profile_complete_count: int
    minimum_profile_complete_rate: float
    average_evidences_per_startup: float
    unknown_fields: tuple[tuple[str, int], ...]
    source_success_rates: tuple[SourceQualitySummary, ...]
    ready_for_evaluation: bool
    readiness_reasons: tuple[str, ...]


def summarize_collection_quality(
    candidates: list[CandidateStartup] | tuple[CandidateStartup, ...],
    profiles: list[StartupProfile] | tuple[StartupProfile, ...],
    *,
    collection_results_by_source: Mapping[str, PageCollectionResult] | None = None,
    min_candidates: int = 1,
    min_official_site_rate: float = 0.7,
    min_complete_profile_rate: float = 0.6,
    min_average_evidences: float = 3.0,
) -> CollectionQualitySummary:
    """Generate run-level quality metrics and readiness decision."""

    candidate_tuple = tuple(candidates)
    profile_tuple = tuple(profiles)
    candidate_count = len(candidate_tuple)
    official_site_found_count = _official_site_found_count(candidate_tuple, profile_tuple)
    minimum_profile_complete_count = sum(1 for profile in profile_tuple if _has_minimum_profile(profile))
    average_evidences = _average_evidences_per_startup(profile_tuple)

    summary = CollectionQualitySummary(
        candidate_count=candidate_count,
        official_site_found_count=official_site_found_count,
        official_site_found_rate=_rate(official_site_found_count, candidate_count),
        minimum_profile_complete_count=minimum_profile_complete_count,
        minimum_profile_complete_rate=_rate(minimum_profile_complete_count, candidate_count),
        average_evidences_per_startup=average_evidences,
        unknown_fields=_unknown_fields(profile_tuple),
        source_success_rates=_source_success_rates(collection_results_by_source or {}),
        ready_for_evaluation=False,
        readiness_reasons=(),
    )
    reasons = _readiness_reasons(
        summary,
        min_candidates=min_candidates,
        min_official_site_rate=min_official_site_rate,
        min_complete_profile_rate=min_complete_profile_rate,
        min_average_evidences=min_average_evidences,
    )
    return replace(
        summary,
        ready_for_evaluation=not reasons,
        readiness_reasons=reasons or ("ready_for_ai_native_evaluation",),
    )


def collection_quality_to_dict(summary: CollectionQualitySummary) -> dict[str, object]:
    """Convert quality summary to JSON-serializable dictionaries."""

    return asdict(summary)


def _official_site_found_count(
    candidates: tuple[CandidateStartup, ...],
    profiles: tuple[StartupProfile, ...],
) -> int:
    profile_sites = sum(1 for profile in profiles if profile.official_site.value != UNKNOWN)
    if profiles:
        return profile_sites
    return sum(1 for candidate in candidates if candidate.primary_url != UNKNOWN)


def _has_minimum_profile(profile: StartupProfile) -> bool:
    return all(getattr(profile, field_name).value != UNKNOWN for field_name in MINIMUM_PROFILE_FIELDS)


def _average_evidences_per_startup(profiles: tuple[StartupProfile, ...]) -> float:
    if not profiles:
        return 0.0
    evidence_count = 0
    for profile in profiles:
        for field_value in profile.__dict__.values():
            if isinstance(field_value, ProfileField):
                evidence_count += len(field_value.evidences)
    return round(evidence_count / len(profiles), 2)


def _unknown_fields(profiles: tuple[StartupProfile, ...]) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for profile in profiles:
        for field_name, field_value in profile.__dict__.items():
            if isinstance(field_value, ProfileField) and field_value.value == UNKNOWN:
                counts[field_name] = counts.get(field_name, 0) + 1
    return tuple(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _source_success_rates(
    collection_results_by_source: Mapping[str, PageCollectionResult],
) -> tuple[SourceQualitySummary, ...]:
    summaries: list[SourceQualitySummary] = []
    for source_name, result in collection_results_by_source.items():
        successes = len(result.pages)
        failures = len(result.errors)
        attempts = successes + failures
        summaries.append(
            SourceQualitySummary(
                source_name=source_name,
                attempts=attempts,
                successes=successes,
                failures=failures,
                success_rate=_rate(successes, attempts),
            )
        )
    return tuple(sorted(summaries, key=lambda item: (-item.success_rate, item.source_name)))


def _readiness_reasons(
    summary: CollectionQualitySummary,
    *,
    min_candidates: int,
    min_official_site_rate: float,
    min_complete_profile_rate: float,
    min_average_evidences: float,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if summary.candidate_count < min_candidates:
        reasons.append("not_enough_candidates")
    if summary.official_site_found_rate < min_official_site_rate:
        reasons.append("official_site_coverage_below_threshold")
    if summary.minimum_profile_complete_rate < min_complete_profile_rate:
        reasons.append("minimum_profile_coverage_below_threshold")
    if summary.average_evidences_per_startup < min_average_evidences:
        reasons.append("average_evidence_below_threshold")
    return tuple(reasons)


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 2)
