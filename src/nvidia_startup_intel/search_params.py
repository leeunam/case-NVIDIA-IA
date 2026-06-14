"""Parsing and normalization for startup search parameters.

Story 1 is intentionally deterministic. The next story can consume this
structured object to generate a search plan without reparsing free text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import re

from nvidia_startup_intel.normalization import normalize_text


UNKNOWN = "unknown"


class RegionType(StrEnum):
    COUNTRY = "country"
    MACRO_REGION = "macro_region"
    STATE = "state"
    CITY = "city"
    UNKNOWN = UNKNOWN


class StartupStage(StrEnum):
    EARLY_STAGE = "early_stage"
    GROWTH = "growth"
    SCALE_UP = "scale_up"
    UNKNOWN = UNKNOWN


@dataclass(frozen=True)
class Region:
    raw: str
    normalized: str = UNKNOWN
    type: RegionType = RegionType.UNKNOWN
    country: str = UNKNOWN
    state: str = UNKNOWN
    city: str = UNKNOWN


@dataclass(frozen=True)
class SearchParams:
    raw_query: str
    region: Region
    theme: str = UNKNOWN
    stage: StartupStage = StartupStage.UNKNOWN
    limit: int = 10
    source_priorities: tuple[str, ...] = field(default_factory=tuple)


STATE_ALIASES = {
    "acre": "AC",
    "alagoas": "AL",
    "amapa": "AP",
    "amazonas": "AM",
    "bahia": "BA",
    "ceara": "CE",
    "distrito federal": "DF",
    "espirito santo": "ES",
    "goias": "GO",
    "maranhao": "MA",
    "mato grosso": "MT",
    "mato grosso do sul": "MS",
    "minas gerais": "MG",
    "para": "PA",
    "paraiba": "PB",
    "parana": "PR",
    "pernambuco": "PE",
    "piaui": "PI",
    "rio de janeiro": "RJ",
    "rio grande do norte": "RN",
    "rio grande do sul": "RS",
    "rondonia": "RO",
    "roraima": "RR",
    "santa catarina": "SC",
    "sao paulo": "SP",
    "sergipe": "SE",
    "tocantins": "TO",
}

STATE_CODES = set(STATE_ALIASES.values())

MACRO_REGION_ALIASES = {
    "norte": "Norte",
    "nordeste": "Nordeste",
    "centro oeste": "Centro-Oeste",
    "centro-oeste": "Centro-Oeste",
    "sudeste": "Sudeste",
    "sul": "Sul",
}

CITY_ALIASES = {
    "belo horizonte": ("Belo Horizonte", "MG"),
    "brasilia": ("Brasilia", "DF"),
    "campinas": ("Campinas", "SP"),
    "curitiba": ("Curitiba", "PR"),
    "florianopolis": ("Florianopolis", "SC"),
    "fortaleza": ("Fortaleza", "CE"),
    "porto alegre": ("Porto Alegre", "RS"),
    "recife": ("Recife", "PE"),
    "rio de janeiro": ("Rio de Janeiro", "RJ"),
    "sao paulo": ("Sao Paulo", "SP"),
}

THEME_ALIASES = {
    "agentes": "agents",
    "agents": "agents",
    "ai-native": "ai_native",
    "cybersecurity": "cybersecurity",
    "ciberseguranca": "cybersecurity",
    "computer vision": "computer_vision",
    "dados": "data",
    "data": "data",
    "fintech": "fintech",
    "healthtech": "healthtech",
    "ia generativa": "generative_ai",
    "generative ai": "generative_ai",
    "industria": "industry",
    "robotics": "robotics",
    "robotica": "robotics",
    "voz": "voice",
}

STAGE_ALIASES = {
    "early stage": StartupStage.EARLY_STAGE,
    "growth": StartupStage.GROWTH,
    "scale up": StartupStage.SCALE_UP,
    "scale-up": StartupStage.SCALE_UP,
}

LOCATION_PREPOSITIONS = ("de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas")
STATE_QUALIFIERS = ("estado", "uf")
CITY_QUALIFIERS = ("cidade", "municipio")


def parse_search_params(
    query: str,
    *,
    limit: int | None = None,
    source_priorities: list[str] | tuple[str, ...] | None = None,
) -> SearchParams:
    """Parse a free-text startup search request into structured parameters."""

    clean_query = " ".join(query.split())
    normalized_query = normalize_text(clean_query)

    return SearchParams(
        raw_query=query,
        region=_extract_region(clean_query, normalized_query),
        theme=_extract_theme(normalized_query),
        stage=_extract_stage(normalized_query),
        limit=_normalize_limit(limit),
        source_priorities=tuple(source_priorities or ()),
    )


def normalize_region(raw_region: str) -> Region:
    """Normalize an explicit region value without parsing a whole query."""

    raw_region = " ".join(raw_region.split())
    return _normalize_region_value(raw_region)


def _extract_region(raw_query: str, normalized_query: str) -> Region:
    explicit_city = _extract_explicit_city(raw_query, normalized_query)
    if explicit_city is not None:
        return explicit_city

    explicit_state = _extract_explicit_state(raw_query, normalized_query)
    if explicit_state is not None:
        return explicit_state

    for city_alias, (city, state) in CITY_ALIASES.items():
        if _contains_location(normalized_query, city_alias):
            return _city_region(raw_query, city_alias, city, state)

    for state_alias, state_code in STATE_ALIASES.items():
        if _contains_location(normalized_query, state_alias):
            return _state_region(raw_query, state_alias, state_code)

    for code in sorted(STATE_CODES):
        if re.search(rf"\b{code.lower()}\b", normalized_query):
            return Region(
                raw=code,
                normalized=code,
                type=RegionType.STATE,
                country="BR",
                state=code,
            )

    for region_alias, normalized in MACRO_REGION_ALIASES.items():
        if _contains_location(normalized_query, region_alias):
            return Region(
                raw=_extract_raw_match(raw_query, region_alias),
                normalized=normalized,
                type=RegionType.MACRO_REGION,
                country="BR",
            )

    if re.search(r"\b(brasil|brazil)\b", normalized_query):
        return Region(raw="Brasil", normalized="BR", type=RegionType.COUNTRY, country="BR")

    candidate = _extract_unknown_region_candidate(raw_query, normalized_query)
    return Region(raw=candidate, normalized=UNKNOWN, type=RegionType.UNKNOWN)


def _extract_explicit_city(raw_query: str, normalized_query: str) -> Region | None:
    for city_alias, (city, state) in CITY_ALIASES.items():
        if _has_qualified_location(normalized_query, CITY_QUALIFIERS, city_alias):
            return _city_region(raw_query, city_alias, city, state)
    return None


def _extract_explicit_state(raw_query: str, normalized_query: str) -> Region | None:
    for state_alias, state_code in STATE_ALIASES.items():
        if _has_qualified_location(normalized_query, STATE_QUALIFIERS, state_alias):
            return _state_region(raw_query, state_alias, state_code)

    for state_code in sorted(STATE_CODES):
        if _has_qualified_location(normalized_query, STATE_QUALIFIERS, state_code.lower()):
            return Region(
                raw=state_code,
                normalized=state_code,
                type=RegionType.STATE,
                country="BR",
                state=state_code,
            )

    return None


def _city_region(raw_query: str, city_alias: str, city: str, state: str) -> Region:
    return Region(
        raw=_extract_raw_match(raw_query, city_alias),
        normalized=city,
        type=RegionType.CITY,
        country="BR",
        state=state,
        city=city,
    )


def _state_region(raw_query: str, state_alias: str, state_code: str) -> Region:
    return Region(
        raw=_extract_raw_match(raw_query, state_alias),
        normalized=state_code,
        type=RegionType.STATE,
        country="BR",
        state=state_code,
    )


def _normalize_region_value(raw_region: str) -> Region:
    normalized_region = normalize_text(raw_region)
    parsed = _extract_region(raw_region, normalized_region)
    if parsed.type is RegionType.UNKNOWN:
        return Region(raw=raw_region, normalized=UNKNOWN, type=RegionType.UNKNOWN)
    return parsed


def _extract_theme(normalized_query: str) -> str:
    for alias, theme in THEME_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", normalized_query):
            return theme
    if re.search(r"\bia\b|\bai\b", normalized_query):
        return "artificial_intelligence"
    return UNKNOWN


def _extract_stage(normalized_query: str) -> StartupStage:
    for alias, stage in STAGE_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", normalized_query):
            return stage
    return StartupStage.UNKNOWN


def _normalize_limit(limit: int | None) -> int:
    if limit is None:
        return 10
    if limit < 1:
        raise ValueError("limit must be greater than zero")
    return limit


def _contains_location(normalized_query: str, location_alias: str) -> bool:
    escaped = re.escape(location_alias)
    prepositions = "|".join(LOCATION_PREPOSITIONS)
    return bool(
        re.search(rf"\b(?:{prepositions})\s+{escaped}\b", normalized_query)
        or re.search(rf"\b{escaped}\b", normalized_query)
    )


def _has_qualified_location(
    normalized_query: str,
    qualifiers: tuple[str, ...],
    location_alias: str,
) -> bool:
    escaped_location = re.escape(location_alias)
    qualifier_pattern = "|".join(re.escape(qualifier) for qualifier in qualifiers)
    preposition_pattern = "|".join(LOCATION_PREPOSITIONS)

    return bool(
        re.search(
            rf"\b(?:{qualifier_pattern})\s+(?:{preposition_pattern})?\s*{escaped_location}\b",
            normalized_query,
        )
    )


def _extract_raw_match(raw_query: str, normalized_match: str) -> str:
    words = normalized_match.split()
    raw_tokens = raw_query.split()
    normalized_tokens = [normalize_text(token) for token in raw_tokens]

    for index in range(len(normalized_tokens) - len(words) + 1):
        if normalized_tokens[index : index + len(words)] == words:
            return " ".join(raw_tokens[index : index + len(words)]).strip(" ,.;:")

    return normalized_match


def _extract_unknown_region_candidate(raw_query: str, normalized_query: str) -> str:
    match = re.search(r"\b(?:de|do|da|em|no|na)\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s-]{1,40})", raw_query)
    if match:
        return match.group(1).strip(" ,.;:")

    if normalized_query:
        return raw_query
    return UNKNOWN
