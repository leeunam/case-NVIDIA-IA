from datetime import UTC, datetime

from nvidia_startup_intel.collection_adapters import (
    FirecrawlCollectionAdapter,
    PublicPageCollectionAdapter,
    ScrapyCollectionAdapter,
)
from nvidia_startup_intel.page_collection import FetchResponse, PageCollectionResult


FIXED_TIME = datetime(2026, 6, 26, 15, 30, tzinfo=UTC)


def fixed_clock() -> datetime:
    return FIXED_TIME


def test_firecrawl_adapter_returns_project_collection_contract_from_clean_extraction() -> None:
    client = _FakeFirecrawlClient(
        {
            "markdown": "Plataforma AI-native para atendimento B2B.",
            "metadata": {
                "title": "Startup AI",
                "sourceURL": "https://startup.ai/",
                "statusCode": 200,
            },
        }
    )

    result = FirecrawlCollectionAdapter(client=client).collect(
        "https://startup.ai/",
        max_pages=1,
        max_depth=0,
        clock=fixed_clock,
    )

    assert isinstance(result, PageCollectionResult)
    assert result.errors == ()
    assert len(result.pages) == 1
    assert result.pages[0].url == "https://startup.ai"
    assert result.pages[0].title == "Startup AI"
    assert result.pages[0].main_text == "Plataforma AI-native para atendimento B2B."
    assert result.pages[0].collected_at == "2026-06-26T15:30:00+00:00"
    assert result.pages[0].status_code == 200
    assert result.pages[0].extraction_strategy == "firecrawl_clean_extraction"


def test_firecrawl_adapter_accepts_sdk_data_payload_without_leaking_provider_shape() -> None:
    client = _FakeFirecrawlClient(
        {
            "success": True,
            "data": {
                "markdown": "Texto limpo dentro do payload data.",
                "metadata": {
                    "title": "Startup AI Data",
                    "sourceURL": "https://startup.ai/data/",
                    "statusCode": 200,
                },
            },
        }
    )

    result = FirecrawlCollectionAdapter(client=client).collect(
        "https://startup.ai/",
        max_pages=1,
        max_depth=0,
        clock=fixed_clock,
    )

    assert result.errors == ()
    assert result.pages[0].url == "https://startup.ai/data"
    assert result.pages[0].title == "Startup AI Data"
    assert result.pages[0].main_text == "Texto limpo dentro do payload data."


def test_scrapy_adapter_returns_project_collection_contract_from_structured_crawl() -> None:
    crawler = _FakeScrapyCrawler(
        (
            {
                "url": "https://startup.ai/",
                "title": "Startup AI",
                "main_text": "Home com evidencias publicas de IA.",
                "status_code": 200,
            },
            {
                "url": "https://startup.ai/produtos/",
                "title": "Produtos",
                "main_text": "Produto AI-native para operacoes financeiras.",
                "status_code": 200,
            },
        )
    )

    result = ScrapyCollectionAdapter(crawler=crawler).collect(
        "https://startup.ai/",
        max_pages=2,
        max_depth=1,
        clock=fixed_clock,
    )

    assert isinstance(result, PageCollectionResult)
    assert result.errors == ()
    assert [page.url for page in result.pages] == [
        "https://startup.ai",
        "https://startup.ai/produtos",
    ]
    assert result.pages[1].title == "Produtos"
    assert result.pages[1].main_text == "Produto AI-native para operacoes financeiras."
    assert result.pages[1].collected_at == "2026-06-26T15:30:00+00:00"
    assert result.pages[1].status_code == 200
    assert result.pages[1].extraction_strategy == "scrapy_structured_crawl"
    assert crawler.calls == (("https://startup.ai/", 2, 1),)


def test_firecrawl_adapter_failure_returns_categorized_collection_error() -> None:
    result = FirecrawlCollectionAdapter(client=_FailingFirecrawlClient()).collect(
        "https://startup.ai/",
        max_pages=1,
        max_depth=0,
        clock=fixed_clock,
    )

    assert result.pages == ()
    assert len(result.errors) == 1
    assert result.errors[0].url == "https://startup.ai"
    assert result.errors[0].error_type == "RuntimeError"
    assert result.errors[0].message == "firecrawl service unavailable"
    assert result.errors[0].collected_at == "2026-06-26T15:30:00+00:00"
    assert result.errors[0].status_code is None
    assert result.errors[0].error_category == "firecrawl_adapter_failed"


def test_scrapy_adapter_failure_returns_categorized_collection_error() -> None:
    result = ScrapyCollectionAdapter(crawler=_FailingScrapyCrawler()).collect(
        "https://startup.ai/",
        max_pages=2,
        max_depth=1,
        clock=fixed_clock,
    )

    assert result.pages == ()
    assert len(result.errors) == 1
    assert result.errors[0].url == "https://startup.ai"
    assert result.errors[0].error_type == "TimeoutError"
    assert result.errors[0].message == "scrapy crawl timed out"
    assert result.errors[0].collected_at == "2026-06-26T15:30:00+00:00"
    assert result.errors[0].status_code is None
    assert result.errors[0].error_category == "scrapy_adapter_failed"


def test_public_page_collection_adapter_wraps_local_collection_strategy() -> None:
    adapter = PublicPageCollectionAdapter(
        fetcher=lambda url: FetchResponse(
            url=url,
            status_code=200,
            body="<html><head><title>Startup AI</title></head><body>Texto publico.</body></html>",
        )
    )

    result = adapter.collect(
        "https://startup.ai/",
        max_pages=1,
        max_depth=0,
        clock=fixed_clock,
    )

    assert result.errors == ()
    assert result.pages[0].url == "https://startup.ai"
    assert result.pages[0].title == "Startup AI"
    assert result.pages[0].main_text == "Texto publico."
    assert result.pages[0].collected_at == "2026-06-26T15:30:00+00:00"


class _FakeFirecrawlClient:
    def __init__(self, response: object) -> None:
        self.response = response

    def scrape(
        self,
        url: str,
        *,
        formats: tuple[str, ...],
        only_main_content: bool,
    ) -> object:
        return self.response


class _FailingFirecrawlClient:
    def scrape(
        self,
        url: str,
        *,
        formats: tuple[str, ...],
        only_main_content: bool,
    ) -> object:
        raise RuntimeError("firecrawl service unavailable")


class _FakeScrapyCrawler:
    def __init__(self, items: tuple[dict[str, object], ...]) -> None:
        self.items = items
        self.calls: tuple[tuple[str, int, int], ...] = ()

    def crawl(self, start_url: str, *, max_pages: int, max_depth: int) -> tuple[dict[str, object], ...]:
        self.calls = (*self.calls, (start_url, max_pages, max_depth))
        return self.items


class _FailingScrapyCrawler:
    def crawl(self, start_url: str, *, max_pages: int, max_depth: int) -> tuple[dict[str, object], ...]:
        raise TimeoutError("scrapy crawl timed out")
