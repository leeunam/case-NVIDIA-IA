"""Basic startup profile extraction from collected pages.

Story 5 converts collected page text into a versioned, evidence-backed startup
profile. This MVP uses deterministic extraction from explicit text patterns and
returns ``unknown`` when evidence is insufficient.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
import re

from nvidia_startup_intel.normalization import normalize_text, origin_url
from nvidia_startup_intel.page_collection import CollectedPage
from nvidia_startup_intel.search_params import UNKNOWN


SCHEMA_VERSION = "startup_profile.v1"


class ClaimSource(StrEnum):
    OBSERVED = "observed"
    INFERRED = "inferred"
    RECOMMENDED = "recommended"
    UNKNOWN = UNKNOWN


@dataclass(frozen=True)
class FieldEvidence:
    url: str
    title: str
    snippet: str
    collected_at: str
    source_type: str


@dataclass(frozen=True)
class ProfileField:
    value: str
    claim_source: ClaimSource
    evidences: tuple[FieldEvidence, ...]


@dataclass(frozen=True)
class StartupProfile:
    schema_version: str
    company_name: ProfileField
    official_site: ProfileField
    company_summary: ProfileField
    sector: ProfileField
    product: ProfileField
    customers: ProfileField
    funding: ProfileField
    founders: ProfileField
    technologies_used: ProfileField
    ai_signals: ProfileField
    location: ProfileField


FIELD_LABELS = {
    "company_summary": ("resumo", "summary", "sobre", "about"),
    "sector": ("setor", "sector"),
    "product": ("produto", "product", "solucao", "solution"),
    "customers": ("clientes", "customers"),
    "funding": ("funding", "investimento", "rodada"),
    "founders": ("founders", "fundadores", "fundador", "fundadora"),
    "technologies_used": ("tecnologias", "technologies", "stack"),
    "ai_signals": ("sinais de ia", "ai signals", "ia", "ai"),
    "location": ("localizacao", "localização", "location", "sede"),
}

SECTOR_KEYWORDS = {
    "healthtech": "healthtech",
    "fintech": "fintech",
    "cybersecurity": "cybersecurity",
    "ciberseguranca": "cybersecurity",
    "industria": "industry",
    "industrial": "industry",
    "dados": "data",
    "data": "data",
}

AI_SIGNAL_KEYWORDS = (
    "agente de ia",
    "agentes de ia",
    "ai-native",
    "computer vision",
    "ia generativa",
    "inteligencia artificial",
    "machine learning",
    "modelo de ia",
    "modelos de ia",
    "visao computacional",
)


def extract_startup_profile(
    pages: list[CollectedPage] | tuple[CollectedPage, ...],
    *,
    fallback_company_name: str = UNKNOWN,
    official_site: str = UNKNOWN,
) -> StartupProfile:
    """Extract a basic profile from collected public pages."""

    pages_tuple = tuple(pages)
    site_value = official_site if official_site != UNKNOWN else _official_site_from_pages(pages_tuple)

    return StartupProfile(
        schema_version=SCHEMA_VERSION,
        company_name=_extract_company_name(pages_tuple, fallback_company_name),
        official_site=_observed_field(site_value, _site_evidence(pages_tuple, site_value)),
        company_summary=_extract_labeled_field(pages_tuple, "company_summary"),
        sector=_extract_sector(pages_tuple),
        product=_extract_labeled_field(pages_tuple, "product"),
        customers=_extract_labeled_field(pages_tuple, "customers"),
        funding=_extract_labeled_field(pages_tuple, "funding"),
        founders=_extract_labeled_field(pages_tuple, "founders"),
        technologies_used=_extract_labeled_field(pages_tuple, "technologies_used"),
        ai_signals=_extract_ai_signals(pages_tuple),
        location=_extract_labeled_field(pages_tuple, "location"),
    )


def startup_profile_to_dict(profile: StartupProfile) -> dict[str, object]:
    """Convert profile dataclasses to JSON-serializable dictionaries."""

    data = asdict(profile)
    for field_name, field_value in data.items():
        if isinstance(field_value, dict) and isinstance(field_value.get("claim_source"), ClaimSource):
            field_value["claim_source"] = field_value["claim_source"].value
    return _enum_values(data)


def _extract_company_name(pages: tuple[CollectedPage, ...], fallback_company_name: str) -> ProfileField:
    if fallback_company_name != UNKNOWN:
        return _observed_field(fallback_company_name, ())

    for page in pages:
        if page.title != UNKNOWN:
            value = re.split(r"\s+[|-]\s+", page.title, maxsplit=1)[0].strip()
            if value:
                return _observed_field(value, (_evidence(page, value),))

    return _unknown_field()


def _extract_labeled_field(pages: tuple[CollectedPage, ...], field_name: str) -> ProfileField:
    labels = FIELD_LABELS[field_name]
    for page in pages:
        match = _find_labeled_value(page.main_text, labels)
        if match:
            return _observed_field(match, (_evidence(page, match),))
    return _unknown_field()


def _extract_sector(pages: tuple[CollectedPage, ...]) -> ProfileField:
    labeled = _extract_labeled_field(pages, "sector")
    if labeled.value != UNKNOWN:
        return labeled

    for page in pages:
        normalized_text = normalize_text(page.main_text)
        for keyword, sector in SECTOR_KEYWORDS.items():
            if keyword in normalized_text:
                return ProfileField(
                    value=sector,
                    claim_source=ClaimSource.INFERRED,
                    evidences=(_evidence(page, keyword),),
                )
    return _unknown_field()


def _extract_ai_signals(pages: tuple[CollectedPage, ...]) -> ProfileField:
    labeled = _extract_labeled_field(pages, "ai_signals")
    if labeled.value != UNKNOWN:
        return labeled

    signals: list[str] = []
    evidences: list[FieldEvidence] = []
    for page in pages:
        normalized_text = normalize_text(page.main_text)
        for keyword in AI_SIGNAL_KEYWORDS:
            if keyword in normalized_text and keyword not in signals:
                signals.append(keyword)
                evidences.append(_evidence(page, keyword))

    if not signals:
        return _unknown_field()

    return ProfileField(
        value=", ".join(signals),
        claim_source=ClaimSource.INFERRED,
        evidences=tuple(evidences),
    )


def _find_labeled_value(text: str, labels: tuple[str, ...]) -> str:
    if text == UNKNOWN:
        return UNKNOWN

    for label in labels:
        match = re.search(
            rf"(?:^|[.;\n])\s*{re.escape(label)}\s*:\s*([^.;\n]+)",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()
    return UNKNOWN


def _official_site_from_pages(pages: tuple[CollectedPage, ...]) -> str:
    if not pages:
        return UNKNOWN
    return origin_url(pages[0].url)


def _site_evidence(pages: tuple[CollectedPage, ...], site_value: str) -> tuple[FieldEvidence, ...]:
    if site_value == UNKNOWN or not pages:
        return ()
    return (_evidence(pages[0], site_value),)


def _observed_field(value: str, evidences: tuple[FieldEvidence, ...]) -> ProfileField:
    if value == UNKNOWN:
        return _unknown_field()
    return ProfileField(value=value, claim_source=ClaimSource.OBSERVED, evidences=evidences)


def _unknown_field() -> ProfileField:
    return ProfileField(value=UNKNOWN, claim_source=ClaimSource.UNKNOWN, evidences=())


def _evidence(page: CollectedPage, value: str) -> FieldEvidence:
    return FieldEvidence(
        url=page.url,
        title=page.title,
        snippet=_snippet_around(page.main_text, value),
        collected_at=page.collected_at,
        source_type="collected_page",
    )


def _snippet_around(text: str, value: str, *, window: int = 160) -> str:
    if text == UNKNOWN:
        return UNKNOWN

    lower_text = text.lower()
    lower_value = value.lower()
    index = lower_text.find(lower_value)
    if index == -1:
        return text[:window].strip()

    start = max(index - window // 2, 0)
    end = min(index + len(value) + window // 2, len(text))
    return text[start:end].strip()


def _enum_values(data: object) -> object:
    if isinstance(data, ClaimSource):
        return data.value
    if isinstance(data, dict):
        return {key: _enum_values(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_enum_values(value) for value in data]
    if isinstance(data, tuple):
        return tuple(_enum_values(value) for value in data)
    return data
