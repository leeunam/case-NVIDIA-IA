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
from nvidia_startup_intel.robots import RobotsCache, RobotsFetcher


SCHEMA_VERSION = "collection_cli_result.v1"
Clock = Callable[[], datetime]
Fetcher = Callable[[str], FetchResponse]


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    fetcher: Fetcher | None = None,
    playwright_renderer: PlaywrightRenderer | None = None,
    robots_fetcher: RobotsFetcher | None = None,
    clock: Clock | None = None,
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
        help="Disable Playwright rendering and keep only the deterministic HTTP/static path.",
    )
    collect.set_defaults(render_js=True)
    collect.add_argument(
        "--robots-policy",
        choices=("conservative", "permissive-on-error", "off"),
        default="conservative",
        help="robots.txt policy for collection.",
    )
    collect.add_argument("--output", help="Write JSON payload to this path instead of stdout.")
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
