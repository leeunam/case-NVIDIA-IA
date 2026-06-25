"""Search plan generation for startup discovery.

Story 2 converts structured search parameters into concrete search terms and
target sources. It does not execute search requests.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum

from nvidia_startup_intel.search_params import SearchParams, UNKNOWN


class SearchScope(StrEnum):
    BROAD_WEB = "broad_web"
    SPECIFIC_SOURCE = "specific_source"


@dataclass(frozen=True)
class SearchPlanItem:
    term: str
    target_source: str
    scope: SearchScope
    priority: int
    justification: str


@dataclass(frozen=True)
class SearchPlan:
    raw_query: str
    items: tuple[SearchPlanItem, ...]


SOURCE_DOMAINS = {
    "StartSe": "startse.com",
    "Distrito": "distrito.me",
    "Latitud": "latitud.com",
    "Cubo Itau": "cubo.network",
    "ACE Startups": "acestartups.com.br",
    "Endeavor Brasil": "endeavor.org.br",
    "Abstartups": "abstartups.com.br",
    "100 Open Startups": "openstartups.net",
    "NeoFeed": "neofeed.com.br",
    "Startups.com.br": "startups.com.br",
}

DEFAULT_SOURCE_PRIORITIES = (
    "Distrito",
    "StartSe",
    "Startups.com.br",
    "NeoFeed",
)

THEME_TERMS = {
    "agents": ("startups de agentes de IA", "AI agent startups"),
    "ai_native": ("startups AI-native", "AI-native startups"),
    "artificial_intelligence": ("startups de inteligencia artificial", "artificial intelligence startups"),
    "computer_vision": ("startups de visao computacional", "computer vision startups"),
    "cybersecurity": ("startups de ciberseguranca com IA", "AI cybersecurity startups"),
    "data": ("startups de dados e IA", "AI data startups"),
    "fintech": ("fintechs com IA", "AI fintech startups"),
    "generative_ai": ("startups de IA generativa", "generative AI startups"),
    "healthtech": ("healthtechs com IA", "AI healthtech startups"),
    "industry": ("startups de IA para industria", "industrial AI startups"),
    "robotics": ("startups de robotica com IA", "AI robotics startups"),
    "voice": ("startups de voz com IA", "AI voice startups"),
}


def build_search_plan(params: SearchParams) -> SearchPlan:
    """Generate a deterministic search plan from normalized search params."""

    region_label = _region_label(params)
    portuguese_theme, english_theme = _theme_terms(params.theme)

    items = [
        SearchPlanItem(
            term=_join_terms(portuguese_theme, region_label, "Brasil"),
            target_source="web",
            scope=SearchScope.BROAD_WEB,
            priority=1,
            justification="Busca ampla em portugues para encontrar candidatas e fontes brasileiras.",
        ),
        SearchPlanItem(
            term=_join_terms(english_theme, region_label, "Brazil"),
            target_source="web",
            scope=SearchScope.BROAD_WEB,
            priority=2,
            justification="Busca ampla em ingles para capturar startups que descrevem IA em ingles.",
        ),
    ]

    for offset, source_name in enumerate(_source_priorities(params), start=3):
        domain = SOURCE_DOMAINS.get(source_name)
        if domain is None:
            term = _join_terms(portuguese_theme, region_label, source_name)
            justification = "Fonte prioritaria informada pelo usuario sem dominio conhecido no catalogo local."
        else:
            term = _join_terms(f"site:{domain}", portuguese_theme, region_label)
            justification = "Busca direcionada em fonte prioritaria para reduzir ruido da web ampla."

        items.append(
            SearchPlanItem(
                term=term,
                target_source=source_name,
                scope=SearchScope.SPECIFIC_SOURCE,
                priority=offset,
                justification=justification,
            )
        )

    return SearchPlan(raw_query=params.raw_query, items=_dedupe_items(items))


def search_plan_to_dict(plan: SearchPlan) -> dict[str, object]:
    """Convert a search plan to plain dicts for fixtures and persistence."""

    return {
        "raw_query": plan.raw_query,
        "items": [
            {
                **asdict(item),
                "scope": item.scope.value,
            }
            for item in plan.items
        ],
    }


def _source_priorities(params: SearchParams) -> tuple[str, ...]:
    if params.source_priorities or not params.use_default_sources:
        return params.source_priorities
    return DEFAULT_SOURCE_PRIORITIES


def _region_label(params: SearchParams) -> str:
    region = params.region
    if region.normalized == UNKNOWN:
        return UNKNOWN
    if region.city != UNKNOWN:
        return _join_terms(region.city, region.state)
    if region.raw != UNKNOWN:
        return region.raw
    if region.state != UNKNOWN:
        return region.state
    return region.normalized


def _theme_terms(theme: str) -> tuple[str, str]:
    return THEME_TERMS.get(theme, ("startups de inteligencia artificial", "artificial intelligence startups"))


def _dedupe_items(items: list[SearchPlanItem]) -> tuple[SearchPlanItem, ...]:
    unique: dict[tuple[str, str], SearchPlanItem] = {}
    for item in items:
        key = (item.term.lower(), item.target_source.lower())
        unique.setdefault(key, item)
    return tuple(unique.values())


def _join_terms(*parts: str) -> str:
    return " ".join(part.strip() for part in parts if part and part != UNKNOWN)
