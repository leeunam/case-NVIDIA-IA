"""Public page collection for candidate startups.

Story 4 collects a small, relevant set of public pages from a startup website.
The default fetcher uses the Python standard library, and tests inject a fake
fetcher so collection behavior stays deterministic.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from nvidia_startup_intel.normalization import (
    normalize_domain,
    normalize_text,
    normalize_url,
    normalize_whitespace,
)
from nvidia_startup_intel.scraping_policy import (
    ScrapeDecisionReason,
    ScrapingPolicy,
    ScrapeDecision,
    classify_scrape_error,
    evaluate_scrape_request,
)
from nvidia_startup_intel.robots import RobotsCache, RobotsDecisionReason
from nvidia_startup_intel.search_params import UNKNOWN


Fetcher = Callable[[str], "FetchResponse"]
Clock = Callable[[], datetime]
Sleeper = Callable[[float], None]


@dataclass(frozen=True)
class FetchResponse:
    url: str
    status_code: int
    body: str
    content_type: str = "text/html"


@dataclass(frozen=True)
class CollectedPage:
    url: str
    title: str
    main_text: str
    collected_at: str
    status_code: int


@dataclass(frozen=True)
class PageCollectionError:
    url: str
    error_type: str
    message: str
    collected_at: str
    status_code: int | None = None
    error_category: str = UNKNOWN


@dataclass(frozen=True)
class PageCollectionResult:
    pages: tuple[CollectedPage, ...]
    errors: tuple[PageCollectionError, ...]


RELEVANT_PATH_KEYWORDS = (
    "about",
    "blog",
    "carreira",
    "carreiras",
    "case",
    "cases",
    "cliente",
    "clientes",
    "docs",
    "documentacao",
    "documentation",
    "news",
    "noticia",
    "noticias",
    "pricing",
    "produto",
    "produtos",
    "sobre",
    "solucao",
    "solucoes",
    "solution",
    "solutions",
)

IRRELEVANT_EXTENSIONS = (
    ".avi",
    ".css",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".js",
    ".mov",
    ".mp4",
    ".pdf",
    ".png",
    ".svg",
    ".webp",
    ".zip",
)


def collect_public_pages(
    start_url: str,
    *,
    fetcher: Fetcher | None = None,
    max_pages: int = 5,
    max_depth: int = 1,
    clock: Clock | None = None,
    scraping_policy: ScrapingPolicy | None = None,
    robots_cache: RobotsCache | None = None,
    sleeper: Sleeper | None = None,
) -> PageCollectionResult:
    """Collect relevant public pages from one website without crossing domains."""

    if max_pages < 1:
        raise ValueError("max_pages must be greater than zero")
    if max_depth < 0:
        raise ValueError("max_depth must be zero or greater")

    fetch = fetcher or fetch_url
    now = clock or _utc_now
    wait = sleeper or sleep
    active_policy = scraping_policy or ScrapingPolicy()
    normalized_start_url = normalize_url(start_url)
    start_domain = normalize_domain(normalized_start_url)

    pages: list[CollectedPage] = []
    errors: list[PageCollectionError] = []
    visited: set[str] = set()
    queued: set[str] = {normalized_start_url}
    queue: deque[tuple[str, int]] = deque([(normalized_start_url, 0)])

    while queue and len(pages) < max_pages:
        url, depth = queue.popleft()
        queued.discard(url)
        if url in visited:
            continue
        visited.add(url)

        collected_at = _format_time(now())
        decision = _evaluate_collection_request(url, active_policy, robots_cache)
        if not decision.allowed:
            errors.append(
                PageCollectionError(
                    url=url,
                    error_type=_policy_error_type(decision.reason),
                    message=decision.message,
                    collected_at=collected_at,
                    error_category=decision.reason.value,
                )
            )
            continue

        try:
            if decision.delay_seconds > 0:
                wait(decision.delay_seconds)
            response = fetch(url)
        except Exception as exc:  # noqa: BLE001 - errors are persisted as pipeline data.
            errors.append(
                PageCollectionError(
                    url=url,
                    error_type=type(exc).__name__,
                    message=str(exc),
                    collected_at=collected_at,
                    status_code=getattr(exc, "code", None),
                    error_category=classify_scrape_error(exc).value,
                )
            )
            continue

        parser = _ReadableHTMLParser()
        parser.feed(response.body)
        parser.close()

        main_text = normalize_whitespace(" ".join(parser.text_parts))
        pages.append(
            CollectedPage(
                url=normalize_url(response.url),
                title=parser.title or UNKNOWN,
                main_text=main_text or UNKNOWN,
                collected_at=collected_at,
                status_code=response.status_code,
            )
        )

        if depth >= max_depth:
            continue

        for link in _prioritized_links(response.url, parser.links, start_domain):
            if len(pages) + len(queue) >= max_pages:
                break
            if link in visited or link in queued:
                continue
            queue.append((link, depth + 1))
            queued.add(link)

    return PageCollectionResult(pages=tuple(pages), errors=tuple(errors))


def fetch_url(url: str, *, timeout: int = 15) -> FetchResponse:
    """Fetch one URL with the standard library."""

    request = Request(url, headers={"User-Agent": "nvidia-startup-intel/0.1"})
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return FetchResponse(
                url=response.geturl(),
                status_code=response.status,
                body=body,
                content_type=response.headers.get("content-type", UNKNOWN),
            )
    except HTTPError:
        raise
    except URLError:
        raise


class _ReadableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.links: list[str] = []
        self.text_parts: list[str] = []
        self._tag_stack: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._tag_stack.append(tag)
        if tag == "title":
            self._in_title = True
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        for index in range(len(self._tag_stack) - 1, -1, -1):
            if self._tag_stack[index] == tag:
                del self._tag_stack[index]
                break

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self.title = normalize_whitespace(f"{self.title} {text}")
            return
        if any(tag in {"script", "style", "noscript"} for tag in self._tag_stack):
            return
        self.text_parts.append(text)


def _prioritized_links(base_url: str, links: list[str], start_domain: str) -> tuple[str, ...]:
    normalized_links = {
        normalize_url(urljoin(base_url, link))
        for link in links
        if _is_relevant_link(urljoin(base_url, link), start_domain)
    }
    return tuple(sorted(normalized_links, key=_link_priority))


def _is_relevant_link(url: str, start_domain: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if normalize_domain(url) != start_domain:
        return False
    if parsed.path.lower().endswith(IRRELEVANT_EXTENSIONS):
        return False
    return _is_home_path(parsed.path) or any(keyword in _slugify_path(parsed.path) for keyword in RELEVANT_PATH_KEYWORDS)


def _link_priority(url: str) -> tuple[int, str]:
    path = _slugify_path(urlparse(url).path)
    if _is_home_path(path):
        return (0, url)
    for index, keyword in enumerate(RELEVANT_PATH_KEYWORDS, start=1):
        if keyword in path:
            return (index, url)
    return (len(RELEVANT_PATH_KEYWORDS) + 1, url)


def _is_home_path(path: str) -> bool:
    return path in {"", "/"}


def _slugify_path(path: str) -> str:
    return normalize_text(path)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _format_time(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def _policy_error_type(reason: ScrapeDecisionReason) -> str:
    return {
        ScrapeDecisionReason.BLOCKED_DOMAIN: "ScrapeBlocked",
        ScrapeDecisionReason.LOGIN_REQUIRED: "LoginRequired",
        ScrapeDecisionReason.ROBOTS_DISALLOWED: "RobotsDisallowed",
        ScrapeDecisionReason.ROBOTS_UNAVAILABLE: "RobotsUnavailable",
        ScrapeDecisionReason.ALLOWED: "unknown",
    }[reason]


def _evaluate_collection_request(
    url: str,
    scraping_policy: ScrapingPolicy,
    robots_cache: RobotsCache | None,
) -> ScrapeDecision:
    policy_decision = evaluate_scrape_request(url, scraping_policy)
    if not policy_decision.allowed:
        return policy_decision

    delay_seconds = scraping_policy.rate_limit_seconds
    if robots_cache is None:
        return ScrapeDecision(
            allowed=True,
            reason=ScrapeDecisionReason.ALLOWED,
            message=policy_decision.message,
            delay_seconds=delay_seconds,
        )

    robots_decision = robots_cache.evaluate(url)
    if not robots_decision.allowed:
        reason = (
            ScrapeDecisionReason.ROBOTS_DISALLOWED
            if robots_decision.reason is RobotsDecisionReason.ROBOTS_DISALLOWED
            else ScrapeDecisionReason.ROBOTS_UNAVAILABLE
        )
        return ScrapeDecision(
            allowed=False,
            reason=reason,
            message=robots_decision.message,
        )

    if robots_decision.crawl_delay_seconds is not None:
        delay_seconds = max(delay_seconds, robots_decision.crawl_delay_seconds)

    return ScrapeDecision(
        allowed=True,
        reason=ScrapeDecisionReason.ALLOWED,
        message=robots_decision.message,
        delay_seconds=delay_seconds,
    )
