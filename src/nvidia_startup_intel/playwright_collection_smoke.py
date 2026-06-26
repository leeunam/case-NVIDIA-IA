"""Optional smoke validation for the real Playwright-first collection path."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import TextIO

from nvidia_startup_intel.page_collection import (
    Fetcher,
    HTMLExtractor,
    PageCollectionResult,
    PlaywrightPageRenderer,
    PlaywrightRenderer,
    StaticHTMLExtractionAdapter,
    collect_public_pages,
)


SCHEMA_VERSION = "playwright_collection_smoke.v1"
DEFAULT_SMOKE_HTML = """\
<!doctype html>
<html>
  <head><title>Playwright Collection Smoke</title></head>
  <body>
    <div id="root"></div>
    <script>
      document.getElementById("root").innerHTML =
        "<main>Playwright rendered public startup collection smoke with enough public text "
        + "to prove the browser path produced readable evidence for the collection contract.</main>";
    </script>
  </body>
</html>
"""

Clock = Callable[[], datetime]


class PlaywrightCollectionSmokeError(RuntimeError):
    """Actionable failure for optional real Playwright collection validation."""


@dataclass(frozen=True)
class PlaywrightCollectionSmokeResult:
    schema_version: str
    run_id: str
    input_url: str
    collection_result: PageCollectionResult

    def to_dict(self) -> dict[str, object]:
        """Serialize the smoke output without leaking provider objects."""

        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "input_url": self.input_url,
            "collection_result": _to_plain_data(self.collection_result),
        }


def run_playwright_collection_smoke(
    url: str | None = None,
    *,
    playwright_renderer: PlaywrightRenderer | None = None,
    fetcher: Fetcher | None = None,
    html_extractor: HTMLExtractor | None = None,
    clock: Clock | None = None,
) -> PlaywrightCollectionSmokeResult:
    """Run one controlled Playwright-first collection and return project contracts."""

    if url is None:
        with TemporaryDirectory() as temp_dir:
            smoke_path = Path(temp_dir) / "playwright-collection-smoke.html"
            smoke_path.write_text(DEFAULT_SMOKE_HTML, encoding="utf-8")
            return _run_smoke_for_url(
                smoke_path.as_uri(),
                playwright_renderer=playwright_renderer,
                fetcher=fetcher,
                html_extractor=html_extractor,
                clock=clock,
            )

    return _run_smoke_for_url(
        url,
        playwright_renderer=playwright_renderer,
        fetcher=fetcher,
        html_extractor=html_extractor,
        clock=clock,
    )


def _run_smoke_for_url(
    url: str,
    *,
    playwright_renderer: PlaywrightRenderer | None,
    fetcher: Fetcher | None,
    html_extractor: HTMLExtractor | None,
    clock: Clock | None,
) -> PlaywrightCollectionSmokeResult:
    now = clock or _utc_now
    run_started_at = now()
    result = collect_public_pages(
        url,
        fetcher=fetcher,
        playwright_renderer=playwright_renderer or PlaywrightPageRenderer(),
        html_extractor=html_extractor or StaticHTMLExtractionAdapter(),
        max_pages=1,
        max_depth=0,
        clock=now,
        robots_cache=None,
    )
    _assert_playwright_collection_succeeded(result)
    return PlaywrightCollectionSmokeResult(
        schema_version=SCHEMA_VERSION,
        run_id=f"playwright-smoke-{_utc(run_started_at).strftime('%Y%m%dT%H%M%SZ')}",
        input_url=url,
        collection_result=result,
    )


def _assert_playwright_collection_succeeded(result: PageCollectionResult) -> None:
    if not result.pages:
        error_messages = "; ".join(error.message for error in result.errors) or "no page collected"
        raise PlaywrightCollectionSmokeError(
            "Optional Playwright collection smoke did not collect a page: "
            f"{error_messages}"
        )

    browser_errors = [
        error for error in result.errors if error.error_category == "browser_render_failed"
    ]
    if browser_errors:
        raise PlaywrightCollectionSmokeError(
            "Optional Playwright collection smoke rendered with browser errors: "
            + "; ".join(error.message for error in browser_errors)
        )

    first_page = result.pages[0]
    if not first_page.extraction_strategy.endswith("+playwright"):
        raise PlaywrightCollectionSmokeError(
            "Optional Playwright collection smoke did not use Playwright as the "
            f"primary renderer; extraction_strategy={first_page.extraction_strategy!r}"
        )


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


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None) -> int:
    """Run the optional Playwright collection smoke as a module."""

    parser = argparse.ArgumentParser(
        description="Run optional real Playwright-first collection smoke."
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="Optional URL to collect. Defaults to a temporary local HTML smoke page.",
    )
    args = parser.parse_args(argv)
    output = stdout or sys.stdout

    try:
        result = run_playwright_collection_smoke(args.url)
    except PlaywrightCollectionSmokeError as exc:
        output.write(f"OPTIONAL PLAYWRIGHT COLLECTION SMOKE FAILED: {exc}\n")
        return 1

    output.write(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    output.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
