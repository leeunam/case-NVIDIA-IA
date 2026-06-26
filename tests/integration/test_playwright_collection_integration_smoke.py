from __future__ import annotations

import os

import pytest

from nvidia_startup_intel.playwright_collection_smoke import (
    PlaywrightCollectionSmokeError,
    run_playwright_collection_smoke,
)


pytestmark = pytest.mark.playwright_collection_integration

_RUN_ENV = "NVIDIA_STARTUP_INTEL_RUN_PLAYWRIGHT_COLLECTION_SMOKE"


def test_playwright_collection_smoke_renders_local_page_with_real_browser() -> None:
    if os.environ.get(_RUN_ENV) != "1":
        pytest.skip(
            "optional Playwright collection smoke is disabled; set "
            f"{_RUN_ENV}=1 after installing Chromium browser binaries"
        )

    try:
        result = run_playwright_collection_smoke()
    except PlaywrightCollectionSmokeError as exc:
        pytest.fail(f"OPTIONAL PLAYWRIGHT COLLECTION SMOKE FAILED: {exc}", pytrace=False)

    first_page = result.collection_result.pages[0]

    assert result.schema_version == "playwright_collection_smoke.v1"
    assert first_page.status_code in {0, 200}
    assert first_page.extraction_strategy.endswith("+playwright")
    assert first_page.needs_js_rendering is False
    assert "Playwright rendered public startup collection smoke" in first_page.main_text
    assert result.collection_result.errors == ()
