import pytest

from nvidia_startup_intel.search_params import (
    RegionType,
    StartupStage,
    normalize_region,
    parse_search_params,
)


def test_parse_query_with_state_and_theme() -> None:
    params = parse_search_params("startups AI-native de Minas Gerais", limit=5)

    assert params.raw_query == "startups AI-native de Minas Gerais"
    assert params.limit == 5
    assert params.theme == "ai_native"
    assert params.stage is StartupStage.UNKNOWN
    assert params.region.type is RegionType.STATE
    assert params.region.normalized == "MG"
    assert params.region.country == "BR"
    assert params.region.state == "MG"
    assert params.region.city == "unknown"


def test_parse_query_with_macro_region() -> None:
    params = parse_search_params("healthtechs com IA generativa no Nordeste")

    assert params.theme == "generative_ai"
    assert params.region.type is RegionType.MACRO_REGION
    assert params.region.normalized == "Nordeste"
    assert params.region.country == "BR"


def test_parse_query_with_city() -> None:
    params = parse_search_params("startups de computer vision em Recife early stage")

    assert params.theme == "computer_vision"
    assert params.stage is StartupStage.EARLY_STAGE
    assert params.region.type is RegionType.CITY
    assert params.region.normalized == "Recife"
    assert params.region.state == "PE"


def test_state_qualifier_disambiguates_sao_paulo() -> None:
    params = parse_search_params("startups AI-native no estado de São Paulo")

    assert params.region.type is RegionType.STATE
    assert params.region.normalized == "SP"
    assert params.region.state == "SP"
    assert params.region.city == "unknown"


def test_city_qualifier_disambiguates_sao_paulo() -> None:
    params = parse_search_params("startups AI-native na cidade de São Paulo")

    assert params.region.type is RegionType.CITY
    assert params.region.normalized == "Sao Paulo"
    assert params.region.state == "SP"
    assert params.region.city == "Sao Paulo"


def test_state_qualifier_disambiguates_rio_de_janeiro() -> None:
    params = parse_search_params("startups de IA no estado do Rio de Janeiro")

    assert params.region.type is RegionType.STATE
    assert params.region.normalized == "RJ"
    assert params.region.state == "RJ"
    assert params.region.city == "unknown"


def test_city_qualifier_disambiguates_rio_de_janeiro() -> None:
    params = parse_search_params("startups de IA na cidade do Rio de Janeiro")

    assert params.region.type is RegionType.CITY
    assert params.region.normalized == "Rio de Janeiro"
    assert params.region.state == "RJ"
    assert params.region.city == "Rio de Janeiro"


def test_normalize_explicit_state() -> None:
    region = normalize_region("Minas Gerais")

    assert region.type is RegionType.STATE
    assert region.normalized == "MG"
    assert region.country == "BR"


def test_unknown_region_preserves_original_text() -> None:
    region = normalize_region("Vale do Silício Brasileiro")

    assert region.raw == "Vale do Silício Brasileiro"
    assert region.normalized == "unknown"
    assert region.type is RegionType.UNKNOWN


def test_limit_must_be_positive() -> None:
    with pytest.raises(ValueError, match="limit must be greater than zero"):
        parse_search_params("startups de IA no Brasil", limit=0)


def test_source_priorities_are_preserved_for_next_story() -> None:
    params = parse_search_params(
        "startups de IA no Brasil",
        source_priorities=["Distrito", "StartSe"],
    )

    assert params.source_priorities == ("Distrito", "StartSe")
