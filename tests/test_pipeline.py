from nvidia_startup_intel.discovery import RawDiscoveryResult
from nvidia_startup_intel.page_collection import FetchResponse
from nvidia_startup_intel.pipeline import fixture_fetcher, run_scraping_pipeline


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
        limit=2,
        max_pages_per_candidate=1,
    )

    assert result.search_params.theme == "ai_native"
    assert len(result.search_plan.items) >= 2
    assert len(result.candidates) == 2
    assert len(result.profiles) == 2
    assert {profile.schema_version for profile in result.profiles} == {"startup_profile.v1"}
    assert all(profile.ai_signals.value != "unknown" for profile in result.profiles)
    assert all(result.evidence_groups_by_profile.values())
    assert result.quality_summary.ready_for_evaluation is True
