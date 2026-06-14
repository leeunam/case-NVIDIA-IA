import json
from pathlib import Path

from nvidia_startup_intel.search_params import parse_search_params
from nvidia_startup_intel.search_plan import (
    SearchScope,
    build_search_plan,
    search_plan_to_dict,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_build_search_plan_matches_expected_fixture() -> None:
    params = parse_search_params(
        "startups AI-native de Minas Gerais",
        source_priorities=["Distrito", "StartSe"],
    )
    expected = json.loads((FIXTURES_DIR / "search_plan_expected.json").read_text())

    plan = build_search_plan(params)

    assert search_plan_to_dict(plan) == expected


def test_build_search_plan_generates_portuguese_and_english_terms() -> None:
    params = parse_search_params("healthtechs com IA generativa no Nordeste")

    plan = build_search_plan(params)
    terms = [item.term for item in plan.items]

    assert "startups de IA generativa Nordeste Brasil" in terms
    assert "generative AI startups Nordeste Brazil" in terms


def test_build_search_plan_differentiates_broad_web_and_specific_sources() -> None:
    params = parse_search_params("startups de computer vision em Recife")

    plan = build_search_plan(params)

    assert plan.items[0].scope is SearchScope.BROAD_WEB
    assert plan.items[0].target_source == "web"
    assert any(item.scope is SearchScope.SPECIFIC_SOURCE for item in plan.items)
    assert any(item.target_source == "Distrito" for item in plan.items)


def test_build_search_plan_avoids_repeated_equivalent_terms() -> None:
    params = parse_search_params(
        "startups de IA no Brasil",
        source_priorities=["Distrito", "Distrito"],
    )

    plan = build_search_plan(params)
    keys = {(item.term.lower(), item.target_source.lower()) for item in plan.items}

    assert len(keys) == len(plan.items)


def test_unknown_source_priority_is_preserved_without_site_filter() -> None:
    params = parse_search_params(
        "startups de voz com IA em Recife",
        source_priorities=["Fonte Manual"],
    )

    plan = build_search_plan(params)

    assert plan.items[-1].target_source == "Fonte Manual"
    assert plan.items[-1].scope is SearchScope.SPECIFIC_SOURCE
    assert plan.items[-1].term == "startups de voz com IA Recife PE Fonte Manual"
