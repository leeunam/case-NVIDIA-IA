"""Candidate startup discovery from raw search results.

Story 3 starts after a search plan has been executed. This module does not
search the web; it turns raw results into auditable candidate startups.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
import unicodedata
from urllib.parse import urlparse

from nvidia_startup_intel.search_params import UNKNOWN


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

LEGAL_SUFFIXES = {
    "brasil",
    "company",
    "inc",
    "ltda",
    "me",
    "sa",
    "startup",
    "startups",
    "tecnologia",
}


def discover_candidate_startups(
    results: list[RawDiscoveryResult] | tuple[RawDiscoveryResult, ...],
    *,
    limit: int | None = None,
) -> list[CandidateStartup]:
    """Return deduplicated candidate startups from raw discovery results."""

    if limit is not None and limit < 1:
        raise ValueError("limit must be greater than zero")

    candidates_by_key: dict[str, CandidateStartup] = {}

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
            normalized_name=normalize_company_name(name),
            primary_url=_primary_url(result.url, source_type),
            discovery_source=result.source_name,
            evidence_snippet=result.snippet,
            confidence_score=_score_candidate(source_type, evidence_count=1),
            source_types=(source_type,),
            evidences=(evidence,),
        )

        key = _dedupe_key(candidate)
        existing = candidates_by_key.get(key)
        if existing is None:
            candidates_by_key[key] = candidate
        else:
            candidates_by_key[key] = _merge_candidates(existing, candidate)

    candidates = sorted(
        candidates_by_key.values(),
        key=lambda candidate: (-candidate.confidence_score, candidate.name),
    )
    if limit is None:
        return candidates
    return candidates[:limit]


def classify_source_type(url: str) -> DiscoverySourceType:
    """Classify a discovery source by URL/domain."""

    domain = _registered_domain(url)
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

    normalized = _normalize_text(name)
    normalized = re.sub(r"[^\w\s-]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    tokens = [token for token in normalized.split() if token not in LEGAL_SUFFIXES]
    return " ".join(tokens) or UNKNOWN


def _merge_candidates(existing: CandidateStartup, new: CandidateStartup) -> CandidateStartup:
    evidences = _dedupe_evidences(existing.evidences + new.evidences)
    source_types = tuple(dict.fromkeys(existing.source_types + new.source_types))
    name = _preferred_name(existing.name, new.name)
    primary_url = _preferred_primary_url(existing.primary_url, new.primary_url)

    return CandidateStartup(
        name=name,
        normalized_name=normalize_company_name(name),
        primary_url=primary_url,
        discovery_source=existing.discovery_source,
        evidence_snippet=existing.evidence_snippet,
        confidence_score=_score_candidate_for_evidences(evidences),
        source_types=source_types,
        evidences=evidences,
    )


def _dedupe_evidences(evidences: tuple[DiscoveryEvidence, ...]) -> tuple[DiscoveryEvidence, ...]:
    unique: dict[tuple[str, str], DiscoveryEvidence] = {}
    for evidence in evidences:
        unique[(evidence.url, evidence.snippet)] = evidence
    return tuple(unique.values())


def _candidate_name(result: RawDiscoveryResult, source_type: DiscoverySourceType) -> str:
    if result.discovered_name != UNKNOWN and result.discovered_name.strip():
        return result.discovered_name.strip()
    if source_type is DiscoverySourceType.COMPANY:
        return _name_from_domain(result.url)
    return UNKNOWN


def _primary_url(url: str, source_type: DiscoverySourceType) -> str:
    if source_type is DiscoverySourceType.COMPANY:
        return _canonical_home_url(url)
    return UNKNOWN


def _dedupe_key(candidate: CandidateStartup) -> str:
    domain = _registered_domain(candidate.primary_url)
    if domain != UNKNOWN:
        return f"domain:{domain}"
    return f"name:{candidate.normalized_name}"


def _score_candidate(source_type: DiscoverySourceType, *, evidence_count: int) -> float:
    base_score = {
        DiscoverySourceType.COMPANY: 0.9,
        DiscoverySourceType.DIRECTORY: 0.75,
        DiscoverySourceType.NEWS: 0.65,
        DiscoverySourceType.PERSONAL_PROFILE: 0.45,
        DiscoverySourceType.UNKNOWN: 0.2,
    }[source_type]
    return round(min(base_score + max(evidence_count - 1, 0) * 0.05, 0.98), 2)


def _score_candidate_for_evidences(evidences: tuple[DiscoveryEvidence, ...]) -> float:
    best_source = max(evidences, key=lambda evidence: _score_candidate(evidence.source_type, evidence_count=1))
    return _score_candidate(best_source.source_type, evidence_count=len(evidences))


def _preferred_name(existing_name: str, new_name: str) -> str:
    if len(new_name) < len(existing_name):
        return new_name
    return existing_name


def _preferred_primary_url(existing_url: str, new_url: str) -> str:
    if existing_url != UNKNOWN:
        return existing_url
    return new_url


def _canonical_home_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.netloc:
        return UNKNOWN
    scheme = parsed.scheme or "https"
    return f"{scheme}://{parsed.netloc.removeprefix('www.')}"


def _registered_domain(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    if not host:
        return UNKNOWN

    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in {"com", "net", "org", "gov"} and parts[-1] == "br":
        return ".".join(parts[-3:])
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def _name_from_domain(url: str) -> str:
    domain = _registered_domain(url)
    if domain == UNKNOWN:
        return UNKNOWN
    return domain.split(".")[0].replace("-", " ").title()


def _normalize_text(value: str) -> str:
    without_accents = "".join(
        char
        for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )
    return without_accents.lower().strip()
