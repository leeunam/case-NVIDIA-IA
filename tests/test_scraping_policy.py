from datetime import UTC, datetime
from urllib.error import HTTPError, URLError

from nvidia_startup_intel.page_collection import FetchResponse, collect_public_pages
from nvidia_startup_intel.scraping_policy import (
    ScrapeErrorCategory,
    ScrapingPolicy,
    classify_scrape_error,
    evaluate_scrape_request,
)


FIXED_TIME = datetime(2026, 6, 14, 12, 0, tzinfo=UTC)


def fixed_clock() -> datetime:
    return FIXED_TIME


def test_blocks_manually_blocked_domain_without_fetching() -> None:
    fetched_urls: list[str] = []

    def fetch(url: str) -> FetchResponse:
        fetched_urls.append(url)
        return FetchResponse(url=url, status_code=200, body="<html><body>ok</body></html>")

    result = collect_public_pages(
        "https://blocked.ai/",
        fetcher=fetch,
        clock=fixed_clock,
        scraping_policy=ScrapingPolicy(blocked_domains=frozenset({"blocked.ai"})),
    )

    assert result.pages == ()
    assert fetched_urls == []
    assert result.errors[0].error_type == "ScrapeBlocked"
    assert result.errors[0].error_category == "blocked_domain"


def test_identifies_login_content_and_does_not_attempt_collection() -> None:
    decision = evaluate_scrape_request("https://startup.ai/login", ScrapingPolicy())

    assert decision.allowed is False
    assert decision.reason.value == "login_required"

    result = collect_public_pages(
        "https://startup.ai/login",
        fetcher=lambda url: FetchResponse(url=url, status_code=200, body="private"),
        clock=fixed_clock,
    )

    assert result.pages == ()
    assert result.errors[0].error_type == "LoginRequired"
    assert result.errors[0].message == "URL appears to require login; collection was not attempted."


def test_uses_configurable_rate_limit_before_fetching() -> None:
    sleeps: list[float] = []

    result = collect_public_pages(
        "https://startup.ai/",
        fetcher=lambda url: FetchResponse(url=url, status_code=200, body="<html><body>ok</body></html>"),
        clock=fixed_clock,
        scraping_policy=ScrapingPolicy(rate_limit_seconds=1.5),
        sleeper=sleeps.append,
    )

    assert len(result.pages) == 1
    assert sleeps == [1.5]


def test_classifies_network_timeout_blocked_and_unavailable_errors() -> None:
    assert classify_scrape_error(TimeoutError("timeout")) is ScrapeErrorCategory.TIMEOUT
    assert classify_scrape_error(URLError("dns")) is ScrapeErrorCategory.NETWORK_ERROR
    assert classify_scrape_error(HTTPError("https://x.ai", 403, "forbidden", {}, None)) is ScrapeErrorCategory.BLOCKED
    assert classify_scrape_error(HTTPError("https://x.ai", 404, "missing", {}, None)) is ScrapeErrorCategory.UNAVAILABLE
