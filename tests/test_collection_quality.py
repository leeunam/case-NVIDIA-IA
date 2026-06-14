from nvidia_startup_intel.collection_quality import (
    collection_quality_to_dict,
    summarize_collection_quality,
)
from nvidia_startup_intel.discovery import RawDiscoveryResult, discover_candidate_startups
from nvidia_startup_intel.page_collection import (
    CollectedPage,
    PageCollectionError,
    PageCollectionResult,
)
from nvidia_startup_intel.startup_profile import extract_startup_profile


COLLECTED_AT = "2026-06-14T12:00:00+00:00"


def test_summarizes_good_collection_as_ready_for_evaluation() -> None:
    candidates = discover_candidate_startups(
        (
            RawDiscoveryResult(
                title="NeuralMind",
                url="https://neuralmind.ai/",
                snippet="NeuralMind desenvolve IA para documentos.",
                source_name="web",
                discovered_name="NeuralMind",
            ),
        )
    )
    profiles = (
        extract_startup_profile(
            (
                CollectedPage(
                    url="https://neuralmind.ai/",
                    title="NeuralMind | IA",
                    main_text=(
                        "Resumo: IA para documentos. Setor: dados. "
                        "Produto: Plataforma de IA documental. "
                        "Sinais de IA: modelos de IA proprietarios. "
                        "Clientes: bancos. Founders: Ana Silva. "
                        "Tecnologias: machine learning. Localizacao: Campinas, SP."
                    ),
                    collected_at=COLLECTED_AT,
                    status_code=200,
                ),
            )
        ),
    )
    collection_results = {
        "official_site": PageCollectionResult(
            pages=(
                CollectedPage(
                    url="https://neuralmind.ai/",
                    title="NeuralMind",
                    main_text="IA para documentos.",
                    collected_at=COLLECTED_AT,
                    status_code=200,
                ),
            ),
            errors=(),
        )
    }

    summary = summarize_collection_quality(candidates, profiles, collection_results_by_source=collection_results)

    assert summary.candidate_count == 1
    assert summary.official_site_found_rate == 1.0
    assert summary.minimum_profile_complete_rate == 1.0
    assert summary.average_evidences_per_startup >= 3
    assert summary.source_success_rates[0].success_rate == 1.0
    assert summary.ready_for_evaluation is True
    assert summary.readiness_reasons == ("ready_for_ai_native_evaluation",)
    assert collection_quality_to_dict(summary)["candidate_count"] == 1


def test_summarizes_insufficient_collection_as_not_ready() -> None:
    candidates = discover_candidate_startups(
        (
            RawDiscoveryResult(
                title="Exemplo AI no Distrito",
                url="https://distrito.me/startups/exemplo-ai",
                snippet="Exemplo AI atua com IA.",
                source_name="Distrito",
                discovered_name="Exemplo AI",
            ),
        )
    )
    profiles = (
        extract_startup_profile(
            (),
            official_site="unknown",
        ),
    )
    collection_results = {
        "official_site": PageCollectionResult(
            pages=(),
            errors=(
                PageCollectionError(
                    url="https://example.ai/",
                    error_type="TimeoutError",
                    message="timeout",
                    collected_at=COLLECTED_AT,
                    error_category="timeout",
                ),
            ),
        )
    }

    summary = summarize_collection_quality(candidates, profiles, collection_results_by_source=collection_results)

    assert summary.ready_for_evaluation is False
    assert "official_site_coverage_below_threshold" in summary.readiness_reasons
    assert "minimum_profile_coverage_below_threshold" in summary.readiness_reasons
    assert ("product", 1) in summary.unknown_fields
    assert summary.source_success_rates[0].success_rate == 0.0
