import pytest

from nvidia_startup_intel.discovery import (
    CandidateStartup,
    DiscoverySourceType,
    RawDiscoveryResult,
    classify_source_type,
    discover_candidate_startups,
    normalize_company_name,
)


def test_discover_candidate_from_company_website() -> None:
    results = [
        RawDiscoveryResult(
            title="NeuralMind | Inteligencia Artificial",
            url="https://www.neuralmind.ai/produtos",
            snippet="A NeuralMind desenvolve solucoes de IA para documentos.",
            source_name="web",
            discovered_name="NeuralMind",
        )
    ]

    candidates = discover_candidate_startups(results)

    assert len(candidates) == 1
    assert candidates[0] == CandidateStartup(
        name="NeuralMind",
        normalized_name="neuralmind",
        primary_url="https://neuralmind.ai",
        discovery_source="web",
        evidence_snippet="A NeuralMind desenvolve solucoes de IA para documentos.",
        confidence_score=0.9,
        source_types=(DiscoverySourceType.COMPANY,),
        evidences=candidates[0].evidences,
    )
    assert candidates[0].evidences[0].url == "https://www.neuralmind.ai/produtos"


def test_company_result_prefers_domain_when_discovered_name_is_seo_title() -> None:
    candidates = discover_candidate_startups(
        [
            RawDiscoveryResult(
                title="NeuralMind | Inteligencia Artificial",
                url="https://www.neuralmind.ai/produtos",
                snippet="A NeuralMind desenvolve solucoes de IA para documentos.",
                source_name="web",
                discovered_name="NeuralMind | Inteligencia Artificial",
            )
        ]
    )

    assert len(candidates) == 1
    assert candidates[0].name == "NeuralMind"
    assert candidates[0].primary_url == "https://neuralmind.ai"


def test_classify_company_news_directory_and_personal_profile() -> None:
    assert classify_source_type("https://www.startup.com.br") is DiscoverySourceType.COMPANY
    assert classify_source_type("https://distrito.me/startups/exemplo") is DiscoverySourceType.DIRECTORY
    assert classify_source_type("https://neofeed.com.br/startups/exemplo-capta") is DiscoverySourceType.NEWS
    assert classify_source_type("https://www.linkedin.com/in/founder-exemplo") is DiscoverySourceType.PERSONAL_PROFILE


def test_deduplicate_obvious_duplicates_by_domain() -> None:
    results = [
        RawDiscoveryResult(
            title="Aquarela Advanced Analytics",
            url="https://www.aquare.la/",
            snippet="Aquarela usa IA e data analytics.",
            source_name="web",
            discovered_name="Aquarela",
        ),
        RawDiscoveryResult(
            title="Aquarela Blog",
            url="https://aquare.la/blog/inteligencia-artificial",
            snippet="Blog da Aquarela sobre inteligencia artificial.",
            source_name="web",
            discovered_name="Aquarela Analytics",
        ),
    ]

    candidates = discover_candidate_startups(results)

    assert len(candidates) == 1
    assert candidates[0].primary_url == "https://aquare.la"
    assert candidates[0].confidence_score == 0.95
    assert len(candidates[0].evidences) == 2


def test_deduplicate_obvious_name_variations_without_official_domain() -> None:
    results = [
        RawDiscoveryResult(
            title="Exemplo AI no Distrito",
            url="https://distrito.me/startups/exemplo-ai",
            snippet="Exemplo AI atua com agentes de IA.",
            source_name="Distrito",
            discovered_name="Exemplo AI Ltda.",
        ),
        RawDiscoveryResult(
            title="Exemplo AI capta rodada",
            url="https://startups.com.br/negocios/exemplo-ai-capta",
            snippet="A Exemplo AI captou investimento.",
            source_name="Startups.com.br",
            discovered_name="Exemplo AI",
        ),
    ]

    candidates = discover_candidate_startups(results)

    assert len(candidates) == 1
    assert candidates[0].name == "Exemplo AI"
    assert candidates[0].normalized_name == "exemplo ai"
    assert candidates[0].primary_url == "https://distrito.me/startups/exemplo-ai"
    assert candidates[0].confidence_score == 0.8
    assert set(candidates[0].source_types) == {
        DiscoverySourceType.DIRECTORY,
        DiscoverySourceType.NEWS,
    }


def test_do_not_merge_different_companies_with_similar_names() -> None:
    results = [
        RawDiscoveryResult(
            title="DataMind",
            url="https://datamind.ai",
            snippet="DataMind usa IA para dados.",
            source_name="web",
            discovered_name="DataMind",
        ),
        RawDiscoveryResult(
            title="DataMind Health",
            url="https://datamindhealth.com.br",
            snippet="DataMind Health usa IA em saude.",
            source_name="web",
            discovered_name="DataMind Health",
        ),
    ]

    candidates = discover_candidate_startups(results)

    assert len(candidates) == 2
    assert {candidate.normalized_name for candidate in candidates} == {
        "datamind",
        "datamind health",
    }


def test_skip_result_without_company_name_when_source_is_not_official_company() -> None:
    results = [
        RawDiscoveryResult(
            title="Lista de startups brasileiras",
            url="https://neofeed.com.br/startups/lista-startups-brasileiras/",
            snippet="Materia lista startups do Brasil.",
            source_name="NeoFeed",
        )
    ]

    assert discover_candidate_startups(results) == []


def test_skip_news_title_when_discovered_name_is_article_headline() -> None:
    results = [
        RawDiscoveryResult(
            title="10 startups brasileiras de IA para acompanhar",
            url="https://neofeed.com.br/startups/10-startups-brasileiras-de-ia/",
            snippet="Materia lista startups brasileiras de IA.",
            source_name="NeoFeed",
            discovered_name="10 startups brasileiras de IA para acompanhar",
        )
    ]

    assert discover_candidate_startups(results) == []


def test_news_and_directory_candidates_keep_source_url_for_collection() -> None:
    candidates = discover_candidate_startups(
        [
            RawDiscoveryResult(
                title="Exemplo AI capta rodada",
                url="https://startups.com.br/negocios/exemplo-ai-capta/",
                snippet="A Exemplo AI captou investimento.",
                source_name="Startups.com.br",
                discovered_name="Exemplo AI",
            )
        ]
    )

    assert candidates[0].primary_url == "https://startups.com.br/negocios/exemplo-ai-capta"


def test_company_result_can_infer_candidate_name_from_domain() -> None:
    candidates = discover_candidate_startups(
        [
            RawDiscoveryResult(
                title="Empresa",
                url="https://visao-computacional.ai",
                snippet="Plataforma de visao computacional.",
                source_name="web",
            )
        ]
    )

    assert candidates[0].name == "Visao Computacional"
    assert candidates[0].normalized_name == "visao computacional"


def test_limit_is_respected() -> None:
    results = [
        RawDiscoveryResult(
            title="Alpha AI",
            url="https://alpha.ai",
            snippet="Alpha AI usa IA.",
            source_name="web",
            discovered_name="Alpha AI",
        ),
        RawDiscoveryResult(
            title="Beta AI",
            url="https://beta.ai",
            snippet="Beta AI usa IA.",
            source_name="web",
            discovered_name="Beta AI",
        ),
    ]

    candidates = discover_candidate_startups(results, limit=1)

    assert len(candidates) == 1


def test_limit_must_be_positive() -> None:
    with pytest.raises(ValueError, match="limit must be greater than zero"):
        discover_candidate_startups([], limit=0)


def test_normalize_company_name_removes_obvious_suffixes() -> None:
    assert normalize_company_name("Exemplo AI Ltda.") == "exemplo ai"
