"""Command line entrypoints for controlled local pipeline operations."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum
import json
from pathlib import Path
import sys
from typing import TextIO

from nvidia_startup_intel.page_collection import (
    FetchResponse,
    PlaywrightPageRenderer,
    PlaywrightRenderer,
    StaticHTMLExtractionAdapter,
    collect_public_pages,
    fetch_url,
)
from nvidia_startup_intel.discovery import RawDiscoveryResult
from nvidia_startup_intel.persistence import (
    PipelineRun,
    create_pipeline_run,
    save_candidate_startups,
    save_collected_pages,
    save_collection_quality,
    save_field_evidences,
    save_raw_discovery_results,
    save_search_params,
    save_search_plan,
    save_startup_profiles,
)
from nvidia_startup_intel.pipeline import (
    ScrapingPipelineResult,
    candidate_result_key,
    profile_result_key,
    run_controlled_startup_collection,
)
from nvidia_startup_intel.robots import RobotsCache, RobotsFetcher
from nvidia_startup_intel.search_params import UNKNOWN
from nvidia_startup_intel.sql_repository import SqlPipelineRepository, postgres_repository_from_env


SCHEMA_VERSION = "collection_cli_result.v1"
STARTUP_COLLECTION_SCHEMA_VERSION = "startup_collection_cli_result.v1"
Clock = Callable[[], datetime]
Fetcher = Callable[[str], FetchResponse]
SqlRepositoryFactory = Callable[[], SqlPipelineRepository]


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    fetcher: Fetcher | None = None,
    playwright_renderer: PlaywrightRenderer | None = None,
    robots_fetcher: RobotsFetcher | None = None,
    clock: Clock | None = None,
    sql_repository_factory: SqlRepositoryFactory | None = None,
) -> int:
    """Run the project CLI and return a process-style exit code."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    output = stdout or sys.stdout
    errors = stderr or sys.stderr
    now = clock or _utc_now

    if args.command == "collect-pages":
        return _run_collect_pages(
            args,
            stdout=output,
            stderr=errors,
            fetcher=fetcher,
            playwright_renderer=playwright_renderer,
            robots_fetcher=robots_fetcher,
            clock=now,
        )
    if args.command == "collect-startup":
        return _run_collect_startup(
            args,
            stdout=output,
            stderr=errors,
            fetcher=fetcher,
            playwright_renderer=playwright_renderer,
            robots_fetcher=robots_fetcher,
            clock=now,
            sql_repository_factory=sql_repository_factory,
        )

    parser.print_help(errors)
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nvidia-startup-intel",
        description="Controlled local entrypoints for NVIDIA startup intelligence.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser(
        "collect-pages",
        help="Collect public pages from one startup URL and emit auditable JSON.",
    )
    collect.add_argument("url", help="Public startup URL to collect.")
    collect.add_argument("--max-pages", type=int, default=1, help="Maximum pages to collect.")
    collect.add_argument("--max-depth", type=int, default=0, help="Maximum crawl depth.")
    collect.add_argument(
        "--timeout-seconds",
        type=int,
        default=15,
        help="HTTP timeout for the standard-library fetcher.",
    )
    collect.add_argument(
        "--no-render-js",
        action="store_false",
        dest="render_js",
        help="Disable Playwright rendering and use only the deterministic debug/test harness.",
    )
    collect.set_defaults(render_js=True)
    collect.add_argument(
        "--robots-policy",
        choices=("conservative", "permissive-on-error", "off"),
        default="conservative",
        help="robots.txt policy for collection.",
    )
    collect.add_argument("--output", help="Write JSON payload to this path instead of stdout.")

    startup = subparsers.add_parser(
        "collect-startup",
        help="Collect one startup URL, extract profile evidence, and persist the run to Postgres.",
    )
    startup.add_argument("url", help="Public startup URL to collect.")
    startup.add_argument(
        "--startup-name",
        default=UNKNOWN,
        help="Optional startup name used as the controlled candidate identifier.",
    )
    startup.add_argument("--max-pages", type=int, default=1, help="Maximum pages to collect.")
    startup.add_argument("--max-depth", type=int, default=0, help="Maximum crawl depth.")
    startup.add_argument(
        "--timeout-seconds",
        type=int,
        default=15,
        help="HTTP timeout for the standard-library fetcher.",
    )
    startup.add_argument(
        "--no-render-js",
        action="store_false",
        dest="render_js",
        help="Disable Playwright rendering and use only the deterministic debug/test harness.",
    )
    startup.set_defaults(render_js=True)
    startup.add_argument(
        "--robots-policy",
        choices=("conservative", "permissive-on-error", "off"),
        default="conservative",
        help="robots.txt policy for collection.",
    )
    startup.add_argument(
        "--output-dir",
        default="runs",
        help="Base directory for JSON audit artifacts; the run id is created below it.",
    )
    return parser


def _run_collect_pages(
    args: argparse.Namespace,
    *,
    stdout: TextIO,
    stderr: TextIO,
    fetcher: Fetcher | None,
    playwright_renderer: PlaywrightRenderer | None,
    robots_fetcher: RobotsFetcher | None,
    clock: Clock,
) -> int:
    run_started_at = clock()
    active_fetcher = fetcher or (lambda url: fetch_url(url, timeout=args.timeout_seconds))
    active_renderer = _playwright_renderer(args, playwright_renderer)
    result = collect_public_pages(
        args.url,
        fetcher=active_fetcher,
        playwright_renderer=active_renderer,
        html_extractor=StaticHTMLExtractionAdapter(),
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        clock=clock,
        robots_cache=_robots_cache(args, robots_fetcher),
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": _run_id(run_started_at),
        "input_url": args.url,
        "created_at": _format_time(run_started_at),
        "options": {
            "max_pages": args.max_pages,
            "max_depth": args.max_depth,
            "timeout_seconds": args.timeout_seconds,
            "render_js": args.render_js,
            "robots_policy": args.robots_policy,
        },
        "pages": [_to_plain_data(page) for page in result.pages],
        "errors": [_to_plain_data(error) for error in result.errors],
    }
    _write_payload(payload, output_path=args.output, stdout=stdout)
    return 0


def _run_collect_startup(
    args: argparse.Namespace,
    *,
    stdout: TextIO,
    stderr: TextIO,
    fetcher: Fetcher | None,
    playwright_renderer: PlaywrightRenderer | None,
    robots_fetcher: RobotsFetcher | None,
    clock: Clock,
    sql_repository_factory: SqlRepositoryFactory | None,
) -> int:
    del stderr
    run_started_at = clock()
    run_id = _run_id(run_started_at)
    active_fetcher = fetcher or (lambda url: fetch_url(url, timeout=args.timeout_seconds))
    result = run_controlled_startup_collection(
        args.url,
        startup_name=args.startup_name,
        fetcher=active_fetcher,
        playwright_renderer=_playwright_renderer(args, playwright_renderer),
        html_extractor=StaticHTMLExtractionAdapter(),
        robots_cache=_robots_cache(args, robots_fetcher),
        max_pages_per_candidate=args.max_pages,
        max_depth=args.max_depth,
    )

    json_run = create_pipeline_run(args.output_dir, run_id=run_id, created_at=run_started_at)
    _save_json_artifacts(json_run, result, raw_results=result.raw_results)

    repository = (sql_repository_factory or postgres_repository_from_env)()
    repository.create_run(run_id=run_id, created_at=run_started_at)
    repository.save_pipeline_result(run_id, result)

    payload = {
        "schema_version": STARTUP_COLLECTION_SCHEMA_VERSION,
        "run_id": run_id,
        "input_url": args.url,
        "created_at": _format_time(run_started_at),
        "candidate_identifier": _candidate_identifier(result),
        "startup_identifier": _startup_identifier(result),
        "source_urls": _source_urls(result),
        "json_run_dir": str(json_run.root_dir),
        "postgres": {"persisted": True, "run_id": run_id},
        "options": {
            "max_pages": args.max_pages,
            "max_depth": args.max_depth,
            "timeout_seconds": args.timeout_seconds,
            "render_js": args.render_js,
            "robots_policy": args.robots_policy,
        },
        "summary": {
            "candidate_count": len(result.candidates),
            "collected_pages": sum(
                len(collection.pages) for collection in result.collected_pages_by_candidate.values()
            ),
            "collection_errors": sum(
                len(collection.errors) for collection in result.collected_pages_by_candidate.values()
            ),
            "startup_profiles": len(result.profiles),
            "field_evidences": _field_evidence_count(result),
            "ready_for_evaluation": result.quality_summary.ready_for_evaluation,
        },
    }
    _write_payload(payload, output_path=None, stdout=stdout)
    return 0


def _save_json_artifacts(
    run: PipelineRun,
    result: ScrapingPipelineResult,
    *,
    raw_results: tuple[RawDiscoveryResult, ...],
) -> None:
    save_search_params(run, result.search_params)
    save_search_plan(run, result.search_plan)
    save_raw_discovery_results(run, raw_results)
    save_candidate_startups(run, result.candidates)
    save_collected_pages(run, result.collected_pages_by_candidate)
    save_startup_profiles(run, result.profiles)
    save_field_evidences(run, result.evidence_groups_by_profile)
    save_collection_quality(run, result.quality_summary)


def _candidate_identifier(result: ScrapingPipelineResult) -> str:
    if not result.candidates:
        return UNKNOWN
    return candidate_result_key(result.candidates[0])


def _startup_identifier(result: ScrapingPipelineResult) -> str:
    if not result.profiles:
        return UNKNOWN
    return profile_result_key(result.profiles[0])


def _source_urls(result: ScrapingPipelineResult) -> list[str]:
    urls: list[str] = []
    for collection in result.collected_pages_by_candidate.values():
        for page in collection.pages:
            if page.url not in urls:
                urls.append(page.url)
        for error in collection.errors:
            if error.url not in urls:
                urls.append(error.url)
    return urls


def _field_evidence_count(result: ScrapingPipelineResult) -> int:
    return sum(
        len(group.evidences)
        for groups in result.evidence_groups_by_profile.values()
        for group in groups
    )


def _playwright_renderer(
    args: argparse.Namespace,
    renderer: PlaywrightRenderer | None,
) -> PlaywrightRenderer | None:
    if not args.render_js:
        return None
    return renderer or PlaywrightPageRenderer(timeout_ms=args.timeout_seconds * 1000)


def _robots_cache(
    args: argparse.Namespace,
    robots_fetcher: RobotsFetcher | None,
) -> RobotsCache | None:
    if args.robots_policy == "off":
        return None
    return RobotsCache(
        conservative_on_error=args.robots_policy == "conservative",
        fetcher=robots_fetcher,
    )


def _write_payload(payload: dict[str, object], *, output_path: str | None, stdout: TextIO) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    if output_path:
        Path(output_path).write_text(f"{encoded}\n", encoding="utf-8")
        return
    stdout.write(f"{encoded}\n")


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


def _run_id(value: datetime) -> str:
    return f"cli-{_utc(value).strftime('%Y%m%dT%H%M%SZ')}"


def _format_time(value: datetime) -> str:
    return _utc(value).isoformat()


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _utc_now() -> datetime:
    return datetime.now(UTC)
