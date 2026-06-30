from nvidia_startup_intel.collection_quality import compare_collection_strategy_quality
from nvidia_startup_intel.page_collection import (
    CollectedPage,
    PageCollectionError,
    PageCollectionResult,
)
from nvidia_startup_intel.search_params import UNKNOWN


def test_collection_strategy_quality_compares_text_unknowns_and_failures() -> None:
    comparison = compare_collection_strategy_quality(
        {
            "playwright_trafilatura_beautifulsoup": PageCollectionResult(
                pages=(
                    CollectedPage(
                        url="https://startup.ai",
                        title="Startup AI",
                        main_text="Plataforma AI-native com evidencia publica suficiente." * 3,
                        collected_at="2026-06-26T15:30:00+00:00",
                        status_code=200,
                        extraction_strategy="trafilatura+beautifulsoup+playwright",
                    ),
                ),
                errors=(),
            ),
            "firecrawl": PageCollectionResult(
                pages=(
                    CollectedPage(
                        url="https://startup.ai",
                        title="Startup AI",
                        main_text=UNKNOWN,
                        collected_at="2026-06-26T15:30:00+00:00",
                        status_code=200,
                        extraction_strategy="firecrawl_clean_extraction",
                    ),
                ),
                errors=(
                    PageCollectionError(
                        url="https://startup.ai/blog",
                        error_type="TimeoutError",
                        message="provider timeout",
                        collected_at="2026-06-26T15:30:00+00:00",
                        error_category="firecrawl_adapter_failed",
                    ),
                ),
            ),
        }
    )

    by_strategy = {summary.strategy_name: summary for summary in comparison}

    playwright = by_strategy["playwright_trafilatura_beautifulsoup"]
    assert playwright.failure_rate == 0.0
    assert playwright.unknown_text_rate == 0.0
    assert playwright.empty_or_low_text_rate == 0.0
    assert playwright.average_text_length > 80
    assert playwright.extraction_strategies == ("trafilatura+beautifulsoup+playwright",)

    firecrawl = by_strategy["firecrawl"]
    assert firecrawl.attempts == 2
    assert firecrawl.failure_rate == 0.5
    assert firecrawl.unknown_text_rate == 1.0
    assert firecrawl.empty_or_low_text_rate == 1.0
    assert firecrawl.average_text_length == 0.0
