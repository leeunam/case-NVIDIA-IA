"""Search plan execution against configurable providers.

Story 11 keeps search execution behind a small interface. Tests can use a fake
client, while production can configure a real HTTP provider through
environment variables without leaking credentials into code.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
import os
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from nvidia_startup_intel.discovery import RawDiscoveryResult
from nvidia_startup_intel.search_plan import SearchPlan, SearchPlanItem


@dataclass(frozen=True)
class SearchProviderResult:
    title: str
    url: str
    snippet: str
    position: int


@dataclass(frozen=True)
class SearchExecutionError:
    term: str
    target_source: str
    provider: str
    error_type: str
    message: str


@dataclass(frozen=True)
class SearchExecutionResult:
    raw_results: tuple[RawDiscoveryResult, ...]
    errors: tuple[SearchExecutionError, ...]


class SearchClient(Protocol):
    provider_name: str

    def search(self, query: str, *, limit: int) -> tuple[SearchProviderResult, ...]:
        """Execute one provider query and return normalized results."""


HttpTransport = Callable[[Request, int], bytes]
BRAVE_SEARCH_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


class BraveSearchClient:
    """Minimal Brave Search API adapter configured by environment variables."""

    provider_name = "brave"

    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str = BRAVE_SEARCH_ENDPOINT,
        timeout: int = 15,
        transport: HttpTransport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required for BraveSearchClient")
        self.api_key = api_key
        self.endpoint = endpoint
        self.timeout = timeout
        self.transport = transport or _default_transport

    def search(self, query: str, *, limit: int) -> tuple[SearchProviderResult, ...]:
        url = f"{self.endpoint}?{urlencode({'q': query, 'count': limit})}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "nvidia-startup-intel/0.1",
                "X-Subscription-Token": self.api_key,
            },
        )
        payload = json.loads(self.transport(request, self.timeout).decode("utf-8"))
        return normalize_brave_response(payload, limit=limit)


def execute_search_plan(
    plan: SearchPlan,
    client: SearchClient,
    *,
    per_term_limit: int = 5,
    total_limit: int | None = None,
) -> SearchExecutionResult:
    """Execute a search plan and preserve term/source provenance."""

    if per_term_limit < 1:
        raise ValueError("per_term_limit must be greater than zero")
    if total_limit is not None and total_limit < 1:
        raise ValueError("total_limit must be greater than zero")

    raw_results: list[RawDiscoveryResult] = []
    errors: list[SearchExecutionError] = []

    sorted_items = tuple(sorted(plan.items, key=lambda search_item: search_item.priority))
    for index, item in enumerate(sorted_items):
        remaining = None if total_limit is None else total_limit - len(raw_results)
        if remaining is not None and remaining <= 0:
            break

        remaining_items = len(sorted_items) - index - 1
        query_limit = _query_limit(
            per_term_limit=per_term_limit,
            remaining=remaining,
            remaining_items=remaining_items,
        )
        try:
            provider_results = client.search(item.term, limit=query_limit)
        except Exception as exc:  # noqa: BLE001 - failures are pipeline data.
            errors.append(_execution_error(item, client.provider_name, exc))
            continue

        for provider_result in provider_results[:query_limit]:
            raw_results.append(
                RawDiscoveryResult(
                    title=provider_result.title,
                    url=provider_result.url,
                    snippet=_traceable_snippet(
                        provider_result.snippet,
                        term=item.term,
                        source=item.target_source,
                        position=provider_result.position,
                    ),
                    source_name=item.target_source,
                )
            )
            if total_limit is not None and len(raw_results) >= total_limit:
                break

    return SearchExecutionResult(raw_results=tuple(raw_results), errors=tuple(errors))


def normalize_brave_response(payload: dict[str, Any], *, limit: int) -> tuple[SearchProviderResult, ...]:
    """Normalize Brave Search JSON into provider-neutral results."""

    web_results = payload.get("web", {}).get("results", [])
    normalized: list[SearchProviderResult] = []
    for index, item in enumerate(web_results[:limit], start=1):
        normalized.append(
            SearchProviderResult(
                title=str(item.get("title") or "unknown"),
                url=str(item.get("url") or "unknown"),
                snippet=str(item.get("description") or item.get("snippet") or "unknown"),
                position=index,
            )
        )
    return tuple(normalized)


def search_client_from_env(environ: dict[str, str] | None = None) -> SearchClient:
    """Build a real search client from environment configuration."""

    env = os.environ if environ is None else environ
    provider = env.get("NVIDIA_STARTUP_INTEL_SEARCH_PROVIDER", "brave").lower()
    if provider != "brave":
        raise ValueError(f"Unsupported search provider: {provider}")
    return BraveSearchClient(
        api_key=env.get("BRAVE_SEARCH_API_KEY", ""),
        endpoint=env.get("BRAVE_SEARCH_ENDPOINT", BRAVE_SEARCH_ENDPOINT),
    )


def _traceable_snippet(snippet: str, *, term: str, source: str, position: int) -> str:
    return f"{snippet} [search_term={term}; source={source}; position={position}]"


def _query_limit(*, per_term_limit: int, remaining: int | None, remaining_items: int) -> int:
    if remaining is None:
        return per_term_limit

    reserved_for_later = min(remaining_items, max(remaining - 1, 0))
    usable_now = max(remaining - reserved_for_later, 1)
    return min(per_term_limit, usable_now)


def _execution_error(item: SearchPlanItem, provider: str, exc: Exception) -> SearchExecutionError:
    return SearchExecutionError(
        term=item.term,
        target_source=item.target_source,
        provider=provider,
        error_type=type(exc).__name__,
        message=str(exc),
    )


def _default_transport(request: Request, timeout: int) -> bytes:
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read()
    except (HTTPError, URLError):
        raise
