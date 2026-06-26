"""robots.txt policy lookup with per-run cache.

The implementation uses Python's standard ``urllib.robotparser`` before adding
a larger crawler. The cache is explicit so tests and pipeline runs can audit and
reuse domain decisions.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from nvidia_startup_intel.normalization import normalize_domain, normalize_url


class RobotsDecisionReason(StrEnum):
    ALLOWED = "allowed"
    ROBOTS_DISALLOWED = "robots_disallowed"
    ROBOTS_UNAVAILABLE = "robots_unavailable"


@dataclass(frozen=True)
class RobotsDecision:
    allowed: bool
    reason: RobotsDecisionReason
    message: str
    crawl_delay_seconds: float | None = None


@dataclass(frozen=True)
class RobotsRules:
    parser: RobotFileParser | None
    available: bool
    error: str = ""


RobotsFetcher = Callable[[str], str]


@dataclass
class RobotsCache:
    user_agent: str = "nvidia-startup-intel/0.1"
    conservative_on_error: bool = True
    fetcher: RobotsFetcher | None = None
    _rules_by_domain: dict[str, RobotsRules] = field(default_factory=dict)

    def evaluate(self, url: str) -> RobotsDecision:
        """Return whether ``url`` is allowed by cached robots rules."""

        normalized_url = normalize_url(url)
        rules = self._rules_for_url(normalized_url)
        if not rules.available:
            allowed = not self.conservative_on_error
            return RobotsDecision(
                allowed=allowed,
                reason=RobotsDecisionReason.ALLOWED if allowed else RobotsDecisionReason.ROBOTS_UNAVAILABLE,
                message=(
                    "robots.txt unavailable; conservative policy blocked collection."
                    if not allowed
                    else "robots.txt unavailable; permissive policy allowed collection."
                ),
            )

        parser = rules.parser
        if parser is None or not parser.can_fetch(self.user_agent, normalized_url):
            return RobotsDecision(
                allowed=False,
                reason=RobotsDecisionReason.ROBOTS_DISALLOWED,
                message="URL blocked by robots.txt for configured user agent.",
            )

        delay = parser.crawl_delay(self.user_agent)
        return RobotsDecision(
            allowed=True,
            reason=RobotsDecisionReason.ALLOWED,
            message="URL allowed by robots.txt.",
            crawl_delay_seconds=float(delay) if delay is not None else None,
        )

    def cached_domain_count(self) -> int:
        return len(self._rules_by_domain)

    def _rules_for_url(self, url: str) -> RobotsRules:
        domain = normalize_domain(url)
        if domain not in self._rules_by_domain:
            self._rules_by_domain[domain] = _load_rules(
                _robots_url(url),
                fetcher=self.fetcher or fetch_robots_txt,
            )
        return self._rules_by_domain[domain]


def fetch_robots_txt(url: str, *, timeout: int = 10) -> str:
    request = Request(url, headers={"User-Agent": "nvidia-startup-intel/0.1"})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _load_rules(robots_url: str, *, fetcher: RobotsFetcher) -> RobotsRules:
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        parser.parse(fetcher(robots_url).splitlines())
    except Exception as exc:  # noqa: BLE001 - robots failures are pipeline decisions.
        return RobotsRules(parser=None, available=False, error=str(exc))
    return RobotsRules(parser=parser, available=True)


def _robots_url(url: str) -> str:
    parsed = urlparse(normalize_url(url))
    return f"{parsed.scheme}://{parsed.netloc}/robots.txt"
