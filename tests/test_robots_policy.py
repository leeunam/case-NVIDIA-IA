from datetime import UTC, datetime

from nvidia_startup_intel.page_collection import FetchResponse, collect_public_pages
from nvidia_startup_intel.robots import RobotsCache


FIXED_TIME = datetime(2026, 6, 14, 12, 0, tzinfo=UTC)


def fixed_clock() -> datetime:
    return FIXED_TIME


def test_collects_url_allowed_by_robots_and_uses_cache() -> None:
    robots_calls = []

    def robots_fetcher(url: str) -> str:
        robots_calls.append(url)
        return "User-agent: *\nAllow: /\nCrawl-delay: 2\n"

    slept = []
    robots_cache = RobotsCache(fetcher=robots_fetcher)

    result = collect_public_pages(
        "https://startup.ai/",
        fetcher=lambda url: FetchResponse(url=url, status_code=200, body="<html><body>IA</body></html>"),
        robots_cache=robots_cache,
        max_pages=1,
        clock=fixed_clock,
        sleeper=lambda seconds: slept.append(seconds),
    )

    assert len(result.pages) == 1
    assert result.errors == ()
    assert robots_calls == ["https://startup.ai/robots.txt"]
    assert slept == [2.0]
    assert robots_cache.cached_domain_count() == 1


def test_blocks_url_disallowed_by_robots() -> None:
    robots_cache = RobotsCache(fetcher=lambda url: "User-agent: *\nDisallow: /\n")

    result = collect_public_pages(
        "https://startup.ai/",
        fetcher=lambda url: FetchResponse(url=url, status_code=200, body="<html></html>"),
        robots_cache=robots_cache,
        clock=fixed_clock,
    )

    assert result.pages == ()
    assert len(result.errors) == 1
    assert result.errors[0].error_type == "RobotsDisallowed"
    assert result.errors[0].error_category == "robots_disallowed"


def test_robots_unavailable_is_conservative_by_default_and_configurable() -> None:
    def failing_fetcher(url: str) -> str:
        raise TimeoutError("robots timeout")

    blocked = collect_public_pages(
        "https://startup.ai/",
        fetcher=lambda url: FetchResponse(url=url, status_code=200, body="<html></html>"),
        robots_cache=RobotsCache(fetcher=failing_fetcher),
        clock=fixed_clock,
    )
    allowed = collect_public_pages(
        "https://startup.ai/",
        fetcher=lambda url: FetchResponse(url=url, status_code=200, body="<html><body>IA</body></html>"),
        robots_cache=RobotsCache(fetcher=failing_fetcher, conservative_on_error=False),
        max_pages=1,
        clock=fixed_clock,
    )

    assert blocked.pages == ()
    assert blocked.errors[0].error_type == "RobotsUnavailable"
    assert blocked.errors[0].error_category == "robots_unavailable"
    assert len(allowed.pages) == 1
