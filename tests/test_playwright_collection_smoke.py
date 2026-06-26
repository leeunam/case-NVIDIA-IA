from __future__ import annotations

from datetime import UTC, datetime

from nvidia_startup_intel.page_collection import FetchResponse
from nvidia_startup_intel.playwright_collection_smoke import run_playwright_collection_smoke


FIXED_TIME = datetime(2026, 6, 26, 10, 45, tzinfo=UTC)


def test_playwright_collection_smoke_preserves_collection_contract_with_injected_renderer() -> None:
    result = run_playwright_collection_smoke(
        "https://startup.ai/",
        playwright_renderer=lambda url: FetchResponse(
            url=url,
            status_code=200,
            body=(
                "<html><head><title>Startup AI Smoke</title></head>"
                "<body>Playwright rendered public startup collection.</body></html>"
            ),
        ),
        clock=lambda: FIXED_TIME,
    )

    payload = result.to_dict()

    assert result.schema_version == "playwright_collection_smoke.v1"
    assert result.run_id == "playwright-smoke-20260626T104500Z"
    assert result.collection_result.pages[0].title == "Startup AI Smoke"
    assert result.collection_result.pages[0].extraction_strategy.endswith("+playwright")
    assert result.collection_result.errors == ()
    assert payload["collection_result"]["pages"][0]["title"] == "Startup AI Smoke"
    assert payload["collection_result"]["errors"] == []
