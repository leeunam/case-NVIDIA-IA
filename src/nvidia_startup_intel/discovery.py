"""Candidate startup discovery from raw search results.

This module starts after a search plan has been executed. It does not search
the web; it turns raw provider results into auditable candidate startups.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from urllib.parse import urlparse

from nvidia_startup_intel.normalization import (
    normalize_domain,
    normalize_startup_name,
    normalize_text,
    normalize_url,
    origin_url,
)
from nvidia_startup_intel.search_params import UNKNOWN
from nvidia_startup_intel.startup_deduplication import deduplicate_startups


class DiscoverySourceType(StrEnum):
    COMPANY = "company"
    NEWS = "news"
    DIRECTORY = "directory"
    PERSONAL_PROFILE = "personal_profile"
    UNKNOWN = UNKNOWN


@dataclass(frozen=True)
class RawDiscoveryResult:
    title: str
    url: str
    snippet: str
    source_name: str
    discovered_name: str = UNKNOWN


@dataclass(frozen=True)
class DiscoveryEvidence:
    url: str
    title: str
    snippet: str
    source_name: str
    source_type: DiscoverySourceType


@dataclass(frozen=True)
class CandidateStartup:
    name: str
    normalized_name: str
    primary_url: str
    discovery_source: str
    evidence_snippet: str
    confidence_score: float
    source_types: tuple[DiscoverySourceType, ...]
    evidences: tuple[DiscoveryEvidence, ...]


DIRECTORY_DOMAINS = {
    "100openstartups.net",
    "abstartups.com.br",
    "acestartups.com.br",
    "anjosdobrasil.net",
    "bossainvest.com",
    "cubo.network",
    "darwinstartups.com",
    "distrito.me",
    "endeavor.org.br",
    "inovativabrasil.com.br",
    "latitud.com",
    "liga.ventures",
    "openstartups.net",
    "startse.com",
    "wow.ac",
}

NEWS_DOMAINS = {
    "braziljournal.com",
    "exame.com",
    "globo.com",
    "meioemensagem.com.br",
    "mobiletime.com.br",
    "neofeed.com.br",
    "startups.com.br",
    "valor.globo.com",
}

PERSONAL_PROFILE_DOMAINS = {
    "linkedin.com",
    "twitter.com",
    "x.com",
}

ARTICLE_OR_LIST_TITLE_PATTERNS = (
    r"^\d+\b",
    r"\b\d+\s+startups?\b",
    r"\bstartups?\s+(?:brasileiras?|de ia|para acompanhar|promissoras?)\b",
    r"\b(?:lista|ranking|melhores|conheca|top)\b",
    r"\bpara acompanhar\b",
)

TITLE_GENERIC_SEGMENTS = {
    "artificial intelligence",
    "blog",
    "home",
    "ia",
    "inicio",
    "inteligencia artificial",
    "produtos",
    "sobre",
}


def discover_candidate_startups(
    results: list[RawDiscoveryResult] | tuple[RawDiscoveryResult, ...],
    *,
    limit: int | None = None,
) -> list[CandidateStartup]:
    """Return deduplicated candidate startups from raw discovery results."""

    if limit is not None and limit < 1:
        raise ValueError("limit must be greater than zero")

    candidates: list[CandidateStartup] = []

    for result in results:
        source_type = classify_source_type(result.url)
        name = _candidate_name(result, source_type)
        if name == UNKNOWN:
            continue

        evidence = DiscoveryEvidence(
            url=result.url,
            title=result.title,
            snippet=result.snippet,
            source_name=result.source_name,
            source_type=source_type,
        )
        candidate = CandidateStartup(
            name=name,
            normalized_name=normalize_startup_name(name),
            primary_url=_primary_url(result.url, source_type),
            discovery_source=result.source_name,
            evidence_snippet=result.snippet,
            confidence_score=_score_candidate(source_type, evidence_count=1),
            source_types=(source_type,),
            evidences=(evidence,),
        )
        candidates.append(candidate)

    deduplicated_candidates = sorted(
        deduplicate_startups(candidates),
        key=lambda candidate: (-candidate.confidence_score, candidate.name),
    )
    if limit is None:
        return list(deduplicated_candidates)
    return list(deduplicated_candidates[:limit])


def classify_source_type(url: str) -> DiscoverySourceType:
    """Classify a discovery source by URL/domain."""

    domain = normalize_domain(url)
    path = urlparse(url).path.lower()

    if domain in PERSONAL_PROFILE_DOMAINS or "/in/" in path:
        return DiscoverySourceType.PERSONAL_PROFILE
    if domain in DIRECTORY_DOMAINS:
        return DiscoverySourceType.DIRECTORY
    if domain in NEWS_DOMAINS:
        return DiscoverySourceType.NEWS
    if domain != UNKNOWN:
        return DiscoverySourceType.COMPANY
    return DiscoverySourceType.UNKNOWN


def normalize_company_name(name: str) -> str:
    """Normalize obvious company name variants for conservative deduplication."""

    return normalize_startup_name(name)


def _candidate_name(result: RawDiscoveryResult, source_type: DiscoverySourceType) -> str:
    discovered_name = _clean_discovered_name(result.discovered_name)
    if source_type is DiscoverySourceType.COMPANY:
        domain_name = _name_from_domain(result.url)
        if _matches_company_domain(discovered_name, domain_name):
            return discovered_name
        return domain_name
    if source_type in {DiscoverySourceType.DIRECTORY, DiscoverySourceType.NEWS}:
        if _is_plausible_discovered_name(discovered_name):
            return discovered_name
    return UNKNOWN


def _primary_url(url: str, source_type: DiscoverySourceType) -> str:
    if source_type is DiscoverySourceType.COMPANY:
        return origin_url(url)
    if source_type in {DiscoverySourceType.DIRECTORY, DiscoverySourceType.NEWS}:
        return normalize_url(url)
    return UNKNOWN


def _score_candidate(source_type: DiscoverySourceType, *, evidence_count: int) -> float:
    base_score = {
        DiscoverySourceType.COMPANY: 0.9,
        DiscoverySourceType.DIRECTORY: 0.75,
        DiscoverySourceType.NEWS: 0.65,
        DiscoverySourceType.PERSONAL_PROFILE: 0.45,
        DiscoverySourceType.UNKNOWN: 0.2,
    }[source_type]
    return round(min(base_score + max(evidence_count - 1, 0) * 0.05, 0.98), 2)


def _name_from_domain(url: str) -> str:
    domain = normalize_domain(url)
    if domain == UNKNOWN:
        return UNKNOWN
    return domain.split(".")[0].replace("-", " ").title()


def _clean_discovered_name(discovered_name: str) -> str:
    name = discovered_name.strip()
    if not name or name == UNKNOWN:
        return UNKNOWN

    segments = [
        segment.strip(" \t\n\r,.;:")
        for segment in re.split(r"\s+(?:\||-|::)\s+", name)
        if segment.strip(" \t\n\r,.;:")
    ]
    for segment in segments:
        if normalize_text(segment) not in TITLE_GENERIC_SEGMENTS:
            return segment
    return segments[0] if segments else UNKNOWN


def _matches_company_domain(discovered_name: str, domain_name: str) -> bool:
    if discovered_name == UNKNOWN or domain_name == UNKNOWN:
        return False
    discovered_key = normalize_startup_name(discovered_name)
    domain_key = normalize_startup_name(domain_name)
    compact_discovered_key = discovered_key.replace(" ", "")
    compact_domain_key = domain_key.replace(" ", "")
    return (
        discovered_key == domain_key
        or discovered_key.startswith(f"{domain_key} ")
        or compact_discovered_key == compact_domain_key
        or compact_discovered_key.startswith(compact_domain_key)
    )


def _is_plausible_discovered_name(discovered_name: str) -> bool:
    if discovered_name == UNKNOWN:
        return False

    normalized = normalize_text(discovered_name)
    if any(re.search(pattern, normalized) for pattern in ARTICLE_OR_LIST_TITLE_PATTERNS):
        return False
    if len(normalized.split()) > 7:
        return False
    return normalize_startup_name(discovered_name) != UNKNOWN
