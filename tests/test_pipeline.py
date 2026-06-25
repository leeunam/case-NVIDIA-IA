from nvidia_startup_intel.discovery import CandidateStartup, DiscoverySourceType, RawDiscoveryResult
from nvidia_startup_intel.normalization import normalize_startup_name
from nvidia_startup_intel.page_collection import CollectedPage, FetchResponse, PageCollectionResult
from nvidia_startup_intel.pipeline import (
    candidate_result_key,
    collect_pages_for_candidates,
    extract_profiles_for_candidates,
    fixture_fetcher,
    run_scraping_pipeline,
    structure_profile_evidence,
)
from nvidia_startup_intel.robots import RobotsCache
from nvidia_startup_intel.search_params import UNKNOWN


def allow_robots() -> RobotsCache:
    return RobotsCache(fetcher=lambda url: "User-agent: *\nAllow: /\n")


def test_two_startups_pass_through_complete_scraping_pipeline() -> None:
    raw_results = (
        RawDiscoveryResult(
            title="NeuralMind",
            url="https://neuralmind.ai/",
            snippet="NeuralMind desenvolve IA para documentos.",
            source_name="web",
            discovered_name="NeuralMind",
        ),
        RawDiscoveryResult(
            title="VisionHealth AI",
            url="https://visionhealth.ai/",
            snippet="VisionHealth AI usa computer vision em saude.",
            source_name="web",
            discovered_name="VisionHealth AI",
        ),
    )
    pages = {
        "https://neuralmind.ai": FetchResponse(
            url="https://neuralmind.ai/",
            status_code=200,
            body=(
                "<html><head><title>NeuralMind | IA</title></head><body>"
                "Resumo: IA para documentos. Setor: dados. "
                "Produto: Plataforma de IA documental. "
                "Sinais de IA: modelos de IA proprietarios. "
                "Clientes: bancos. Founders: Ana Silva. "
                "Tecnologias: machine learning. Localizacao: Campinas, SP."
                "</body></html>"
            ),
        ),
        "https://visionhealth.ai": FetchResponse(
            url="https://visionhealth.ai/",
            status_code=200,
            body=(
                "<html><head><title>VisionHealth AI</title></head><body>"
                "Resumo: Healthtech brasileira. Setor: healthtech. "
                "Produto: Triagem clinica com visao computacional. "
                "Sinais de IA: computer vision e machine learning. "
                "Clientes: clinicas. Founders: Bruno Lima. "
                "Tecnologias: machine learning. Localizacao: Sao Paulo, SP."
                "</body></html>"
            ),
        ),
    }

    result = run_scraping_pipeline(
        "startups AI-native do Brasil",
        raw_results,
        fetcher=fixture_fetcher(pages),
        robots_cache=allow_robots(),
        limit=2,
        max_pages_per_candidate=1,
    )

    assert result.search_params.theme == "ai_native"
    assert result.raw_results == raw_results
    assert len(result.search_plan.items) >= 2
    assert len(result.candidates) == 2
    assert set(result.collected_pages_by_candidate) == {
        "url:https://neuralmind.ai",
        "url:https://visionhealth.ai",
    }
    assert len(result.profiles) == 2
    assert {profile.schema_version for profile in result.profiles} == {"startup_profile.v1"}
    assert all(profile.ai_signals.value != "unknown" for profile in result.profiles)
    assert all(result.evidence_groups_by_profile.values())
    assert result.quality_summary.ready_for_evaluation is True


def test_profile_extraction_prefers_collected_page_name_over_candidate_fallback() -> None:
    candidate = CandidateStartup(
        name="10 startups brasileiras de IA para acompanhar",
        normalized_name=normalize_startup_name("10 startups brasileiras de IA para acompanhar"),
        primary_url="https://neuralmind.ai",
        discovery_source="NeoFeed",
        evidence_snippet="Materia lista startups brasileiras de IA.",
        confidence_score=0.65,
        source_types=(DiscoverySourceType.NEWS,),
        evidences=(),
    )
    collection_result = PageCollectionResult(
        pages=(
            CollectedPage(
                url="https://neuralmind.ai",
                title="NeuralMind | Inteligencia Artificial",
                main_text="Resumo: IA para documentos. Setor: dados.",
                collected_at="2026-06-14T12:00:00+00:00",
                status_code=200,
            ),
        ),
        errors=(),
    )

    profiles = extract_profiles_for_candidates(
        (candidate,),
        {candidate_result_key(candidate): collection_result},
    )

    assert profiles[0].company_name.value == "NeuralMind"
    assert profiles[0].company_name.evidences


def test_collect_pages_uses_stable_candidate_keys_for_repeated_names() -> None:
    candidates = (
        CandidateStartup(
            name="Atlas AI",
            normalized_name="atlas ai",
            primary_url="https://atlas.ai",
            discovery_source="web",
            evidence_snippet="Atlas AI para dados.",
            confidence_score=0.9,
            source_types=(DiscoverySourceType.COMPANY,),
            evidences=(),
        ),
        CandidateStartup(
            name="Atlas AI",
            normalized_name="atlas ai",
            primary_url="https://atlashealth.ai",
            discovery_source="web",
            evidence_snippet="Atlas AI para saude.",
            confidence_score=0.9,
            source_types=(DiscoverySourceType.COMPANY,),
            evidences=(),
        ),
    )
    pages = {
        "https://atlas.ai": FetchResponse(
            url="https://atlas.ai",
            status_code=200,
            body="<html><head><title>Atlas AI</title></head><body>Dados.</body></html>",
        ),
        "https://atlashealth.ai": FetchResponse(
            url="https://atlashealth.ai",
            status_code=200,
            body="<html><head><title>Atlas AI</title></head><body>Saude.</body></html>",
        ),
    }

    collected = collect_pages_for_candidates(
        candidates,
        fetcher=fixture_fetcher(pages),
        robots_cache=allow_robots(),
        max_pages_per_candidate=1,
    )

    assert set(collected) == {"url:https://atlas.ai", "url:https://atlashealth.ai"}


def test_collect_pages_uses_robots_cache_by_default(monkeypatch) -> None:
    candidate = CandidateStartup(
        name="Atlas AI",
        normalized_name="atlas ai",
        primary_url="https://atlas.ai",
        discovery_source="web",
        evidence_snippet="Atlas AI para dados.",
        confidence_score=0.9,
        source_types=(DiscoverySourceType.COMPANY,),
        evidences=(),
    )
    robots_fetches: list[str] = []

    def robots_cache_factory() -> RobotsCache:
        return RobotsCache(
            fetcher=lambda url: robots_fetches.append(url) or "User-agent: *\nAllow: /\n",
        )

    monkeypatch.setattr("nvidia_startup_intel.pipeline.RobotsCache", robots_cache_factory)

    collected = collect_pages_for_candidates(
        (candidate,),
        fetcher=fixture_fetcher(
            {
                "https://atlas.ai": FetchResponse(
                    url="https://atlas.ai/",
                    status_code=200,
                    body="<html><head><title>Atlas AI</title></head><body>Dados.</body></html>",
                ),
            }
        ),
        max_pages_per_candidate=1,
    )

    assert tuple(collected) == ("url:https://atlas.ai",)
    assert robots_fetches == ["https://atlas.ai/robots.txt"]


def test_collect_pages_records_error_for_candidate_without_primary_url() -> None:
    candidate = CandidateStartup(
        name="Sem Site AI",
        normalized_name="sem site ai",
        primary_url=UNKNOWN,
        discovery_source="Distrito",
        evidence_snippet="Citada em diretorio.",
        confidence_score=0.75,
        source_types=(DiscoverySourceType.DIRECTORY,),
        evidences=(),
    )

    collected = collect_pages_for_candidates((candidate,), robots_cache=allow_robots())

    result = collected["name:sem site ai"]
    assert result.pages == ()
    assert result.errors[0].error_type == "MissingPrimaryUrl"


def test_structure_profile_evidence_uses_stable_profile_keys_for_repeated_names() -> None:
    candidates = (
        CandidateStartup(
            name="Atlas AI",
            normalized_name="atlas ai",
            primary_url="https://atlas.ai",
            discovery_source="web",
            evidence_snippet="Atlas AI para dados.",
            confidence_score=0.9,
            source_types=(DiscoverySourceType.COMPANY,),
            evidences=(),
        ),
        CandidateStartup(
            name="Atlas AI",
            normalized_name="atlas ai",
            primary_url="https://atlashealth.ai",
            discovery_source="web",
            evidence_snippet="Atlas AI para saude.",
            confidence_score=0.9,
            source_types=(DiscoverySourceType.COMPANY,),
            evidences=(),
        ),
    )
    collected = {
        "url:https://atlas.ai": PageCollectionResult(
            pages=(
                CollectedPage(
                    url="https://atlas.ai",
                    title="Atlas AI",
                    main_text="Resumo: IA para dados. Sinais de IA: machine learning.",
                    collected_at="2026-06-14T12:00:00+00:00",
                    status_code=200,
                ),
            ),
            errors=(),
        ),
        "url:https://atlashealth.ai": PageCollectionResult(
            pages=(
                CollectedPage(
                    url="https://atlashealth.ai",
                    title="Atlas AI",
                    main_text="Resumo: IA para saude. Sinais de IA: computer vision.",
                    collected_at="2026-06-14T12:00:00+00:00",
                    status_code=200,
                ),
            ),
            errors=(),
        ),
    }

    profiles = extract_profiles_for_candidates(candidates, collected)
    groups = structure_profile_evidence(profiles)

    assert set(groups) == {"url:https://atlas.ai", "url:https://atlashealth.ai"}
