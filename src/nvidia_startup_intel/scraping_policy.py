"""Scraping limits, block rules, and error classification.

The policy keeps collection predictable and auditable without adding a heavy
crawler framework before a measured need exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

from nvidia_startup_intel.normalization import normalize_domain, normalize_text


class ScrapeDecisionReason(StrEnum):
    ALLOWED = "allowed"
    BLOCKED_DOMAIN = "blocked_domain"
    LOGIN_REQUIRED = "login_required"
    ROBOTS_DISALLOWED = "robots_disallowed"
    ROBOTS_UNAVAILABLE = "robots_unavailable"


class ScrapeErrorCategory(StrEnum):
    NETWORK_ERROR = "network_error"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ScrapingPolicy:
    rate_limit_seconds: float = 0.0
    blocked_domains: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class ScrapeDecision:
    allowed: bool
    reason: ScrapeDecisionReason
    message: str
    delay_seconds: float = 0.0


LOGIN_PATH_KEYWORDS = (
    "auth",
    "entrar",
    "login",
    "log-in",
    "signin",
    "sign-in",
)


def evaluate_scrape_request(url: str, policy: ScrapingPolicy | None = None) -> ScrapeDecision:
    """Decide whether a URL can be collected under the configured policy."""

    active_policy = policy or ScrapingPolicy()
    domain = normalize_domain(url)
    blocked_domains = {_normalized_policy_domain(domain_name) for domain_name in active_policy.blocked_domains}

    if domain in blocked_domains:
        return ScrapeDecision(
            allowed=False,
            reason=ScrapeDecisionReason.BLOCKED_DOMAIN,
            message=f"Domain {domain} is blocked by manual scraping policy.",
        )

    if _requires_login(url):
        return ScrapeDecision(
            allowed=False,
            reason=ScrapeDecisionReason.LOGIN_REQUIRED,
            message="URL appears to require login; collection was not attempted.",
        )

    return ScrapeDecision(
        allowed=True,
        reason=ScrapeDecisionReason.ALLOWED,
        message="URL allowed by scraping policy.",
    )


def classify_scrape_error(error: Exception) -> ScrapeErrorCategory:
    """Map low-level fetch exceptions to auditable scraping categories."""

    if isinstance(error, TimeoutError):
        return ScrapeErrorCategory.TIMEOUT
    if isinstance(error, HTTPError):
        if error.code in {401, 403, 429}:
            return ScrapeErrorCategory.BLOCKED
        if error.code in {404, 410, 500, 502, 503, 504}:
            return ScrapeErrorCategory.UNAVAILABLE
        return ScrapeErrorCategory.NETWORK_ERROR
    if isinstance(error, URLError):
        return ScrapeErrorCategory.NETWORK_ERROR
    return ScrapeErrorCategory.UNKNOWN


def _requires_login(url: str) -> bool:
    path = normalize_text(urlparse(url).path)
    path_parts = {part for part in path.replace("_", "-").split("/") if part}
    return any(keyword in path_parts for keyword in LOGIN_PATH_KEYWORDS)


def _normalized_policy_domain(domain_name: str) -> str:
    if "://" in domain_name:
        return normalize_domain(domain_name)
    return normalize_domain(f"https://{domain_name}")
