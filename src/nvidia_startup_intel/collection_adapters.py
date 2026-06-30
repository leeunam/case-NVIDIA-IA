"""Optional production collection adapters behind project-owned contracts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
import os
from typing import Protocol

from nvidia_startup_intel.normalization import normalize_domain, normalize_url, normalize_whitespace
from nvidia_startup_intel.page_collection import (
    Fetcher,
    HTMLExtractor,
    PlaywrightRenderer,
    CollectedPage,
    PageCollectionError,
    PageCollectionResult,
    collect_public_pages,
    collection_policy_error_type,
    evaluate_collection_request,
)
from nvidia_startup_intel.robots import RobotsCache
from nvidia_startup_intel.scraping_policy import ScrapingPolicy
from nvidia_startup_intel.search_params import UNKNOWN


FIRECRAWL_ENV_PREFIX = "NVIDIA_STARTUP_INTEL_FIRECRAWL_"


class CollectionClock(Protocol):
    def __call__(self) -> datetime: ...


class CollectionAdapter(Protocol):
    """Project-owned collection adapter seam for optional external tools."""

    def collect(
        self,
        start_url: str,
        *,
        max_pages: int = 5,
        max_depth: int = 1,
        clock: CollectionClock | None = None,
    ) -> PageCollectionResult: ...


class FirecrawlClient(Protocol):
    """Minimal Firecrawl boundary used by the adapter and fakes."""

    def scrape(
        self,
        url: str,
        *,
        formats: tuple[str, ...],
        only_main_content: bool,
    ) -> object: ...


@dataclass(frozen=True)
class FirecrawlProviderConfig:
    """Explicit Firecrawl provider config without storing credential values."""

    provider: str = "firecrawl"
    api_key_env_var: str = "FIRECRAWL_API_KEY"
    api_key_configured: bool = False
    api_base: str = ""


def firecrawl_provider_config_from_env(
    env: Mapping[str, str] | None = None,
) -> FirecrawlProviderConfig:
    """Build Firecrawl config from environment-style inputs without secrets."""

    source = os.environ if env is None else env
    api_key_env_var = (
        source.get(f"{FIRECRAWL_ENV_PREFIX}API_KEY_ENV", "FIRECRAWL_API_KEY").strip()
        or "FIRECRAWL_API_KEY"
    )
    return FirecrawlProviderConfig(
        api_key_env_var=api_key_env_var,
        api_key_configured=bool(source.get(api_key_env_var, "").strip()),
        api_base=source.get(f"{FIRECRAWL_ENV_PREFIX}API_BASE", "").strip(),
    )


class ScrapyCrawler(Protocol):
    """Minimal Scrapy boundary used by the adapter and fakes."""

    def crawl(
        self,
        start_url: str,
        *,
        max_pages: int,
        max_depth: int,
        allowed_domains: tuple[str, ...],
        throttle_seconds: float,
    ) -> Iterable[object]: ...


@dataclass(frozen=True)
class PublicPageCollectionAdapter:
    """Local public-page collection strategy behind the CollectionAdapter seam."""

    fetcher: Fetcher | None = None
    playwright_renderer: PlaywrightRenderer | None = None
    html_extractor: HTMLExtractor | None = None
    scraping_policy: ScrapingPolicy | None = None
    robots_cache: RobotsCache | None = None

    def collect(
        self,
        start_url: str,
        *,
        max_pages: int = 5,
        max_depth: int = 1,
        clock: CollectionClock | None = None,
    ) -> PageCollectionResult:
        return collect_public_pages(
            start_url,
            fetcher=self.fetcher,
            playwright_renderer=self.playwright_renderer,
            html_extractor=self.html_extractor,
            max_pages=max_pages,
            max_depth=max_depth,
            clock=clock,
            scraping_policy=self.scraping_policy,
            robots_cache=self.robots_cache,
        )


@dataclass(frozen=True)
class FirecrawlCollectionAdapter:
    """Firecrawl clean extraction adapter returning PageCollectionResult."""

    client: FirecrawlClient
    provider_config: FirecrawlProviderConfig = field(default_factory=FirecrawlProviderConfig)
    formats: tuple[str, ...] = ("markdown", "html")
    only_main_content: bool = True
    scraping_policy: ScrapingPolicy | None = None
    robots_cache: RobotsCache | None = None

    def collect(
        self,
        start_url: str,
        *,
        max_pages: int = 5,
        max_depth: int = 1,
        clock: CollectionClock | None = None,
    ) -> PageCollectionResult:
        collected_at = _format_time((clock or _utc_now)())
        decision = evaluate_collection_request(
            start_url,
            self.scraping_policy or ScrapingPolicy(),
            self.robots_cache,
        )
        if not decision.allowed:
            return _blocked_adapter_result(
                start_url,
                collected_at=collected_at,
                error_type=collection_policy_error_type(decision.reason),
                message=decision.message,
                error_category=decision.reason.value,
            )
        try:
            response = self.client.scrape(
                start_url,
                formats=self.formats,
                only_main_content=self.only_main_content,
            )
        except Exception as exc:  # noqa: BLE001 - adapter failures are collection data.
            return _adapter_error_result(
                start_url,
                collected_at=collected_at,
                error=exc,
                error_category="firecrawl_adapter_failed",
            )
        document = _firecrawl_document(response)
        metadata = _as_mapping(document.get("metadata", {}))
        page_url = normalize_url(str(metadata.get("sourceURL") or metadata.get("url") or start_url))
        status_code = _status_code(document, metadata)
        main_text = _first_text(document, ("markdown", "text", "content", "html"))
        if not main_text:
            return _empty_content_result(
                page_url,
                collected_at=collected_at,
                status_code=status_code,
                error_category="firecrawl_empty_content",
            )
        page = CollectedPage(
            url=page_url,
            title=normalize_whitespace(str(metadata.get("title") or document.get("title") or UNKNOWN)),
            main_text=main_text,
            collected_at=collected_at,
            status_code=status_code,
            extraction_strategy="firecrawl_clean_extraction",
            needs_js_rendering=False,
        )
        return PageCollectionResult(pages=(page,), errors=())


@dataclass(frozen=True)
class ScrapyCollectionAdapter:
    """Scrapy structured crawling adapter returning PageCollectionResult."""

    crawler: ScrapyCrawler
    scraping_policy: ScrapingPolicy | None = None
    robots_cache: RobotsCache | None = None

    def collect(
        self,
        start_url: str,
        *,
        max_pages: int = 5,
        max_depth: int = 1,
        clock: CollectionClock | None = None,
    ) -> PageCollectionResult:
        collected_at = _format_time((clock or _utc_now)())
        try:
            decision = evaluate_collection_request(
                start_url,
                self.scraping_policy or ScrapingPolicy(),
                self.robots_cache,
            )
            if not decision.allowed:
                return _blocked_adapter_result(
                    start_url,
                    collected_at=collected_at,
                    error_type=collection_policy_error_type(decision.reason),
                    message=decision.message,
                    error_category=decision.reason.value,
                )
            items = tuple(
                self.crawler.crawl(
                    start_url,
                    max_pages=max_pages,
                    max_depth=max_depth,
                    allowed_domains=(normalize_domain(start_url),),
                    throttle_seconds=decision.delay_seconds,
                )
            )
        except Exception as exc:  # noqa: BLE001 - adapter failures are collection data.
            return _adapter_error_result(
                start_url,
                collected_at=collected_at,
                error=exc,
                error_category="scrapy_adapter_failed",
            )
        pages: list[CollectedPage] = []
        errors: list[PageCollectionError] = []
        for document in (_as_mapping(item) for item in items[:max_pages]):
            page_url = normalize_url(str(document.get("url") or start_url))
            status_code = _status_code(document, {})
            main_text = _first_text(document, ("main_text", "text", "content", "body", "html"))
            if not main_text:
                errors.append(
                    _empty_content_error(
                        page_url,
                        collected_at=collected_at,
                        status_code=status_code,
                        error_category="scrapy_empty_content",
                    )
                )
                continue
            pages.append(
                CollectedPage(
                    url=page_url,
                    title=normalize_whitespace(str(document.get("title") or UNKNOWN)),
                    main_text=main_text,
                    collected_at=collected_at,
                    status_code=status_code,
                    extraction_strategy="scrapy_structured_crawl",
                    needs_js_rendering=False,
                )
            )
        return PageCollectionResult(pages=tuple(pages), errors=tuple(errors))


def _as_mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}


def _firecrawl_document(response: object) -> Mapping[str, object]:
    payload = _as_mapping(response)
    data = payload.get("data")
    if isinstance(data, Mapping):
        return data
    if isinstance(data, list) and data:
        return _as_mapping(data[0])
    return payload


def _adapter_error_result(
    url: str,
    *,
    collected_at: str,
    error: Exception,
    error_category: str,
) -> PageCollectionResult:
    return PageCollectionResult(
        pages=(),
        errors=(
            PageCollectionError(
                url=normalize_url(url),
                error_type=type(error).__name__,
                message=str(error),
                collected_at=collected_at,
                status_code=_error_status_code(error),
                error_category=error_category,
            ),
        ),
    )


def _blocked_adapter_result(
    url: str,
    *,
    collected_at: str,
    error_type: str,
    message: str,
    error_category: str,
) -> PageCollectionResult:
    return PageCollectionResult(
        pages=(),
        errors=(
            PageCollectionError(
                url=normalize_url(url),
                error_type=error_type,
                message=message,
                collected_at=collected_at,
                error_category=error_category,
            ),
        ),
    )


def _empty_content_result(
    url: str,
    *,
    collected_at: str,
    status_code: int,
    error_category: str,
) -> PageCollectionResult:
    return PageCollectionResult(
        pages=(),
        errors=(
            _empty_content_error(
                url,
                collected_at=collected_at,
                status_code=status_code,
                error_category=error_category,
            ),
        ),
    )


def _empty_content_error(
    url: str,
    *,
    collected_at: str,
    status_code: int,
    error_category: str,
) -> PageCollectionError:
    return PageCollectionError(
        url=normalize_url(url),
        error_type="EmptyContent",
        message="Provider returned no extractable public page text.",
        collected_at=collected_at,
        status_code=status_code,
        error_category=error_category,
    )


def _error_status_code(error: Exception) -> int | None:
    for attribute in ("status_code", "status", "code"):
        value = getattr(error, attribute, None)
        if isinstance(value, int):
            return value
    return None


def _first_text(document: Mapping[str, object], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = document.get(key)
        if value:
            return normalize_whitespace(str(value))
    return ""


def _status_code(document: Mapping[str, object], metadata: Mapping[str, object]) -> int:
    for value in (
        document.get("status_code"),
        document.get("statusCode"),
        metadata.get("status_code"),
        metadata.get("statusCode"),
    ):
        if isinstance(value, int):
            return value
    return 200


def _format_time(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def _utc_now() -> datetime:
    return datetime.now(UTC)
