from __future__ import annotations

import os

import pytest

from nvidia_startup_intel.production_scraping_smoke import run_production_scraping_smoke


pytestmark = pytest.mark.production_scraping_integration

_RUN_ENV = "NVIDIA_STARTUP_INTEL_RUN_PRODUCTION_SCRAPING_SMOKE"
_URLS_ENV = "NVIDIA_STARTUP_INTEL_PRODUCTION_SCRAPING_URLS"


def test_production_scraping_smoke_collects_configured_public_startup_urls() -> None:
    if os.environ.get(_RUN_ENV) != "1":
        pytest.skip(
            "optional production scraping smoke is disabled; set "
            f"{_RUN_ENV}=1 and {_URLS_ENV}=https://startup.example,https://startup2.example"
        )

    urls = tuple(
        url.strip()
        for url in os.environ.get(_URLS_ENV, "").split(",")
        if url.strip()
    )
    if not urls:
        pytest.skip(f"set {_URLS_ENV} to one or more public startup URLs")

    try:
        result = run_production_scraping_smoke(urls, max_pages=2, max_depth=1)
    except Exception as exc:  # noqa: BLE001 - optional smoke should report environment failures.
        pytest.fail(f"OPTIONAL PRODUCTION SCRAPING SMOKE FAILED: {exc}", pytrace=False)

    assert result.schema_version == "production_scraping_validation.v1"
    assert len(result.startup_reports) == len(urls)
    assert all(report.collection_strategy == "playwright_first" for report in result.startup_reports)
    assert all(report.crawl_limits.max_pages == 2 for report in result.startup_reports)
    assert all(report.quality_reasons for report in result.startup_reports)
