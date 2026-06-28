"""Opt-in production scraping validation for public startup websites."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum
import json
from pathlib import Path
import sys
from time import monotonic
from typing import TextIO, cast

from nvidia_startup_intel.evidence import FieldEvidenceGroup
from nvidia_startup_intel.normalization import normalize_url
from nvidia_startup_intel.page_collection import (
    CollectedPage,
    Fetcher,
    HTMLExtractor,
    PageCollectionError,
    PlaywrightPageRenderer,
    PlaywrightRenderer,
    StaticHTMLExtractionAdapter,
    fetch_url,
)
from nvidia_startup_intel.pipeline import (
    ScrapingPipelineResult,
    candidate_result_key,
    run_controlled_startup_collection,
)
from nvidia_startup_intel.robots import RobotsCache, RobotsDecision, RobotsFetcher
from nvidia_startup_intel.scraping_policy import ScrapeDecision, ScrapingPolicy, evaluate_scrape_request
from nvidia_startup_intel.search_params import UNKNOWN
from nvidia_startup_intel.startup_profile import ProfileField, StartupProfile


SCHEMA_VERSION = "production_scraping_validation.v1"
LOW_TEXT_THRESHOLD = 80
Clock = Callable[[], datetime]
Timer = Callable[[], float]


@dataclass(frozen=True)
class CrawlLimits:
    max_pages: int
    max_depth: int


@dataclass(frozen=True)
class RobotsValidationDecision:
    allowed: bool
    reason: str
    message: str
    crawl_delay_seconds: float | None = None


@dataclass(frozen=True)
class PolicyValidationDecision:
    allowed: bool
    reason: str
    message: str
    delay_seconds: float


@dataclass(frozen=True)
class PageValidationSummary:
    url: str
    title: str
    status_code: int
    extraction_strategy: str
    needs_js_rendering: bool
    text_length: int
    empty_or_low_text: bool
    collected_at: str


@dataclass(frozen=True)
class ProfileQualitySummary:
    profile_schema_version: str
    completeness_rate: float
    unknown_rate: float
    unknown_fields: tuple[str, ...]
    conflicts: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class StartupProductionScrapingReport:
    input_url: str
    startup_name: str
    collection_strategy: str
    policy_decision: PolicyValidationDecision
    robots_decision: RobotsValidationDecision
    crawl_limits: CrawlLimits
    elapsed_ms: int
    page_count: int
    error_count: int
    pages: tuple[PageValidationSummary, ...]
    errors: tuple[PageCollectionError, ...]
    empty_or_low_text_pages: tuple[str, ...]
    profile_quality: ProfileQualitySummary
    quality_reasons: tuple[str, ...]
    ready_for_ai_native_assessment: bool


@dataclass(frozen=True)
class ProductionScrapingSmokeResult:
    schema_version: str
    run_id: str
    created_at: str
    startup_reports: tuple[StartupProductionScrapingReport, ...]

    def to_dict(self) -> dict[str, object]:
        """Serialize the validation result without provider objects."""

        return cast(dict[str, object], _to_plain_data(self))


def run_production_scraping_smoke(
    urls: Sequence[str],
    *,
    startup_names: Mapping[str, str] | None = None,
    fetcher: Fetcher | None = None,
    playwright_renderer: PlaywrightRenderer | None = None,
    html_extractor: HTMLExtractor | None = None,
    robots_fetcher: RobotsFetcher | None = None,
    scraping_policy: ScrapingPolicy | None = None,
    clock: Clock | None = None,
    timer: Timer | None = None,
    max_pages: int = 2,
    max_depth: int = 1,
    render_js: bool = True,
    robots_policy: str = "conservative",
) -> ProductionScrapingSmokeResult:
    """Validate the production collection path against configured public URLs."""

    if not urls:
        raise ValueError("urls must contain at least one public startup URL")

    now = clock or _utc_now
    elapsed_timer = timer or monotonic
    created_at = _utc(now())
    run_id = f"production-scraping-{created_at.strftime('%Y%m%dT%H%M%SZ')}"
    robots_cache = _robots_cache(robots_policy, robots_fetcher)
    active_policy = scraping_policy or ScrapingPolicy()
    names = startup_names or {}

    reports = []
    for url in urls:
        reports.append(
            _run_one_startup_validation(
                url,
                startup_name=names.get(url, UNKNOWN),
                fetcher=fetcher,
                playwright_renderer=playwright_renderer if render_js else None,
                html_extractor=html_extractor,
                robots_cache=robots_cache,
                scraping_policy=active_policy,
                elapsed_timer=elapsed_timer,
                max_pages=max_pages,
                max_depth=max_depth,
                collection_strategy=_collection_strategy(
                    render_js=render_js,
                    fetcher=fetcher,
                    playwright_renderer=playwright_renderer,
                ),
            )
        )

    return ProductionScrapingSmokeResult(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        created_at=_format_time(created_at),
        startup_reports=tuple(reports),
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    fetcher: Fetcher | None = None,
    playwright_renderer: PlaywrightRenderer | None = None,
    html_extractor: HTMLExtractor | None = None,
    robots_fetcher: RobotsFetcher | None = None,
    clock: Clock | None = None,
    timer: Timer | None = None,
) -> int:
    """Run the opt-in production scraping validation smoke."""

    parser = argparse.ArgumentParser(
        description="Run opt-in Playwright-first production scraping validation."
    )
    parser.add_argument("urls", nargs="+", help="Public Brazilian startup URLs to validate.")
    parser.add_argument("--max-pages", type=int, default=2, help="Maximum pages per startup.")
    parser.add_argument("--max-depth", type=int, default=1, help="Maximum crawl depth.")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=15,
        help="HTTP and Playwright timeout for real opt-in collection.",
    )
    parser.add_argument(
        "--no-render-js",
        action="store_false",
        dest="render_js",
        help="Disable Playwright rendering and use the deterministic debug fetch path.",
    )
    parser.set_defaults(render_js=True)
    parser.add_argument(
        "--robots-policy",
        choices=("conservative", "permissive-on-error", "off"),
        default="conservative",
        help="robots.txt policy for collection.",
    )
    parser.add_argument(
        "--output",
        help="Write JSON payload to this path instead of stdout.",
    )
    args = parser.parse_args(argv)

    active_fetcher = fetcher or (lambda url: fetch_url(url, timeout=args.timeout_seconds))
    active_renderer = _renderer_for_main(args, playwright_renderer)
    result = run_production_scraping_smoke(
        tuple(args.urls),
        fetcher=active_fetcher,
        playwright_renderer=active_renderer,
        html_extractor=html_extractor or StaticHTMLExtractionAdapter(),
        robots_fetcher=robots_fetcher,
        clock=clock,
        timer=timer,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        render_js=args.render_js,
        robots_policy=args.robots_policy,
    )
    _write_json_payload(result.to_dict(), output_path=args.output, stdout=stdout or sys.stdout)
    return 0


def _run_one_startup_validation(
    url: str,
    *,
    startup_name: str,
    fetcher: Fetcher | None,
    playwright_renderer: PlaywrightRenderer | None,
    html_extractor: HTMLExtractor | None,
    robots_cache: RobotsCache | None,
    scraping_policy: ScrapingPolicy,
    elapsed_timer: Timer,
    max_pages: int,
    max_depth: int,
    collection_strategy: str,
) -> StartupProductionScrapingReport:
    start = elapsed_timer()
    policy_decision = evaluate_scrape_request(url, scraping_policy)
    robots_decision = _robots_decision(url, robots_cache, policy_decision)
    result = run_controlled_startup_collection(
        url,
        startup_name=startup_name,
        fetcher=fetcher,
        playwright_renderer=playwright_renderer,
        html_extractor=html_extractor,
        robots_cache=robots_cache,
        scraping_policy=scraping_policy,
        max_pages_per_candidate=max_pages,
        max_depth=max_depth,
    )
    elapsed_ms = int(round((elapsed_timer() - start) * 1000))
    candidate_key = candidate_result_key(result.candidates[0])
    collection_result = result.collected_pages_by_candidate[candidate_key]
    pages = tuple(_page_summary(page) for page in collection_result.pages)
    low_text_pages = tuple(page.url for page in pages if page.empty_or_low_text)
    profile = result.profiles[0] if result.profiles else None
    evidence_groups = _first_evidence_groups(result)

    return StartupProductionScrapingReport(
        input_url=url,
        startup_name=_startup_name(url, startup_name, profile),
        collection_strategy=collection_strategy,
        policy_decision=_policy_validation_decision(policy_decision),
        robots_decision=robots_decision,
        crawl_limits=CrawlLimits(max_pages=max_pages, max_depth=max_depth),
        elapsed_ms=elapsed_ms,
        page_count=len(collection_result.pages),
        error_count=len(collection_result.errors),
        pages=pages,
        errors=collection_result.errors,
        empty_or_low_text_pages=low_text_pages,
        profile_quality=_profile_quality(profile, evidence_groups),
        quality_reasons=result.quality_summary.readiness_reasons,
        ready_for_ai_native_assessment=result.quality_summary.ready_for_evaluation,
    )


def _renderer_for_main(
    args: argparse.Namespace,
    renderer: PlaywrightRenderer | None,
) -> PlaywrightRenderer | None:
    if not args.render_js:
        return None
    return renderer or PlaywrightPageRenderer(timeout_ms=args.timeout_seconds * 1000)


def _robots_cache(robots_policy: str, robots_fetcher: RobotsFetcher | None) -> RobotsCache | None:
    if robots_policy == "off":
        return None
    if robots_policy not in {"conservative", "permissive-on-error"}:
        raise ValueError("robots_policy must be conservative, permissive-on-error, or off")
    return RobotsCache(
        conservative_on_error=robots_policy == "conservative",
        fetcher=robots_fetcher,
    )


def _robots_decision(
    url: str,
    robots_cache: RobotsCache | None,
    policy_decision: ScrapeDecision,
) -> RobotsValidationDecision:
    if not policy_decision.allowed:
        return RobotsValidationDecision(
            allowed=False,
            reason="not_checked_policy_blocked",
            message="robots.txt was not checked because scraping policy blocked the URL.",
        )
    if robots_cache is None:
        return RobotsValidationDecision(
            allowed=True,
            reason="not_checked",
            message="robots.txt policy disabled for this opt-in validation run.",
        )
    decision = robots_cache.evaluate(url)
    return _robots_validation_decision(decision)


def _policy_validation_decision(decision: ScrapeDecision) -> PolicyValidationDecision:
    return PolicyValidationDecision(
        allowed=decision.allowed,
        reason=decision.reason.value,
        message=decision.message,
        delay_seconds=decision.delay_seconds,
    )


def _robots_validation_decision(decision: RobotsDecision) -> RobotsValidationDecision:
    return RobotsValidationDecision(
        allowed=decision.allowed,
        reason=decision.reason.value,
        message=decision.message,
        crawl_delay_seconds=decision.crawl_delay_seconds,
    )


def _collection_strategy(
    *,
    render_js: bool,
    fetcher: Fetcher | None,
    playwright_renderer: PlaywrightRenderer | None,
) -> str:
    if not render_js:
        return "deterministic_fetch_debug"
    if playwright_renderer is not None or fetcher is None:
        return "playwright_first"
    return "deterministic_fetch_debug"


def _page_summary(page: CollectedPage) -> PageValidationSummary:
    text_length = 0 if page.main_text == UNKNOWN else len(page.main_text)
    return PageValidationSummary(
        url=page.url,
        title=page.title,
        status_code=page.status_code,
        extraction_strategy=page.extraction_strategy,
        needs_js_rendering=page.needs_js_rendering,
        text_length=text_length,
        empty_or_low_text=text_length < LOW_TEXT_THRESHOLD,
        collected_at=page.collected_at,
    )


def _first_evidence_groups(
    result: ScrapingPipelineResult,
) -> tuple[FieldEvidenceGroup, ...]:
    if not result.evidence_groups_by_profile:
        return ()
    return next(iter(result.evidence_groups_by_profile.values()))


def _profile_quality(
    profile: StartupProfile | None,
    evidence_groups: tuple[FieldEvidenceGroup, ...],
) -> ProfileQualitySummary:
    if profile is None:
        return ProfileQualitySummary(
            profile_schema_version=UNKNOWN,
            completeness_rate=0.0,
            unknown_rate=1.0,
            unknown_fields=(),
            conflicts=(),
        )

    fields_by_name = _profile_fields(profile)
    unknown_fields = tuple(
        field_name for field_name, field_value in fields_by_name.items() if field_value.value == UNKNOWN
    )
    total_fields = len(fields_by_name)
    unknown_count = len(unknown_fields)
    conflicts = tuple(
        {
            "field_name": group.field_name,
            "conflicting_values": list(group.conflicting_values),
        }
        for group in evidence_groups
        if group.has_conflict
    )
    return ProfileQualitySummary(
        profile_schema_version=profile.schema_version,
        completeness_rate=round((total_fields - unknown_count) / total_fields, 2),
        unknown_rate=round(unknown_count / total_fields, 2),
        unknown_fields=unknown_fields,
        conflicts=conflicts,
    )


def _profile_fields(profile: StartupProfile) -> dict[str, ProfileField]:
    return {
        field_name: field_value
        for field_name, field_value in profile.__dict__.items()
        if isinstance(field_value, ProfileField)
    }


def _startup_name(url: str, startup_name: str, profile: StartupProfile | None) -> str:
    if startup_name != UNKNOWN:
        return startup_name
    if profile is not None and profile.company_name.value != UNKNOWN:
        return profile.company_name.value
    return normalize_url(url)


def _to_plain_data(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _to_plain_data(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _to_plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain_data(item) for item in value]
    return value


def _write_json_payload(
    payload: dict[str, object],
    *,
    output_path: str | None,
    stdout: TextIO,
) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    if output_path:
        Path(output_path).write_text(f"{encoded}\n", encoding="utf-8")
        return
    stdout.write(f"{encoded}\n")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _format_time(value: datetime) -> str:
    return _utc(value).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
