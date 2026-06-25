import json

from nvidia_startup_intel.ai_native_assessment import (
    SCHEMA_VERSION,
    assess_ai_native_maturity,
    ai_native_assessment_to_dict,
)
from nvidia_startup_intel.collection_quality import CollectionQualitySummary
from nvidia_startup_intel.evidence import claims_from_profile, structure_evidence_by_field
from nvidia_startup_intel.page_collection import CollectedPage
from nvidia_startup_intel.startup_profile import extract_startup_profile


COLLECTED_AT = "2026-06-14T12:00:00+00:00"


def test_schema_serializes_complete_ai_native_assessment() -> None:
    profile = _profile(
        "Resumo: A DeepDocs e uma plataforma AI-native para automacao documental. "
        "Setor: dados. Produto: Plataforma de IA com agentes autonomos para documentos. "
        "Sinais de IA: modelos proprietarios, fine-tuning, avaliacao de modelos e MLOps. "
        "Tecnologias: inference em producao, model serving, dados proprietarios e feedback loop. "
        "Clientes: bancos. Founders: Ana Silva. Localizacao: Campinas, SP."
    )

    assessment = assess_ai_native_maturity(
        profile,
        _groups(profile),
        _ready_quality(),
        run_id="run-123",
    )

    payload = ai_native_assessment_to_dict(assessment)

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["run_id"] == "run-123"
    assert payload["company_name"] == "DeepDocs"
    assert payload["classification"] == "ai_native"
    assert payload["confidence"] >= 0.8
    assert payload["nvidia_opportunity_urgency"] == "urgent"
    assert payload["ready_for_recommendation"] is True
    assert payload["criteria_results"]
    assert payload["positive_signals"]
    assert payload["technical_gaps"]
    assert payload["wrapper_dependency_risks"]
    json.dumps(payload)


def test_returns_insufficient_evidence_when_collection_quality_is_not_ready() -> None:
    profile = _profile("Resumo: Startup brasileira. Setor: dados.")

    assessment = assess_ai_native_maturity(
        profile,
        _groups(profile),
        _blocked_quality(),
        run_id="run-weak",
    )

    assert assessment.classification == "insufficient_evidence"
    assert assessment.confidence == 0.0
    assert assessment.nvidia_opportunity_urgency == "human_review"
    assert assessment.ready_for_recommendation is False
    assert "collection_quality" in assessment.insufficient_evidence_fields
    assert assessment.criteria_results[0].status == "unknown"


def test_classifies_generic_ai_as_ai_enabled_at_most() -> None:
    profile = _profile(
        "Resumo: Plataforma SaaS para atendimento ao cliente. "
        "Setor: dados. Produto: Chatbot com IA generativa para suporte. "
        "Sinais de IA: usa ChatGPT API para responder perguntas. "
        "Tecnologias: OpenAI API. Clientes: varejo. Founders: Joao Lima. "
        "Localizacao: Sao Paulo, SP."
    )

    assessment = assess_ai_native_maturity(profile, _groups(profile), _ready_quality(), run_id="run-ai")

    assert assessment.classification == "ai_enabled"
    assert assessment.confidence < 0.8
    assert any(risk.risk_type == "external_api_only" for risk in assessment.wrapper_dependency_risks)
    assert _risk(assessment, "external_api_only").severity == "high"
    assert assessment.ready_for_recommendation is False


def test_classifies_non_ai_when_profile_has_no_ai_signal() -> None:
    profile = _profile(
        "Resumo: Marketplace brasileiro para compras corporativas. "
        "Setor: fintech. Produto: Software de gestao de fornecedores. "
        "Clientes: industrias. Founders: Maria Souza. Localizacao: Curitiba, PR."
    )

    assessment = assess_ai_native_maturity(profile, _groups(profile), _ready_quality(), run_id="run-non-ai")

    assert assessment.classification == "non_ai"
    assert assessment.nvidia_opportunity_urgency == "low"
    assert assessment.ready_for_recommendation is False
    assert assessment.technical_gaps[0].gap_type == "unknown"


def test_detects_wrapper_dependency_risk_severities() -> None:
    high_risk_profile = _profile(
        "Resumo: Copilot juridico com IA. Setor: dados. Produto: assistente com IA. "
        "Sinais de IA: usa GPT API e API externa de LLM. Tecnologias: OpenAI API. "
        "Clientes: escritorios. Founders: Lia Alves. Localizacao: Rio de Janeiro, RJ."
    )
    low_risk_profile = _profile(
        "Resumo: Plataforma AI-native. Setor: dados. Produto: IA para documentos. "
        "Sinais de IA: modelos proprietarios e fine-tuning. "
        "Tecnologias: inferencia em producao, MLOps, dados proprietarios e feedback loop. "
        "Clientes: bancos. Founders: Lia Alves. Localizacao: Rio de Janeiro, RJ."
    )
    unknown_profile = _profile(
        "Resumo: Empresa brasileira. Setor: dados. Produto: software B2B. "
        "Clientes: bancos. Founders: Lia Alves. Localizacao: Rio de Janeiro, RJ."
    )

    high = assess_ai_native_maturity(high_risk_profile, _groups(high_risk_profile), _ready_quality(), run_id="1")
    low = assess_ai_native_maturity(low_risk_profile, _groups(low_risk_profile), _ready_quality(), run_id="2")
    unknown = assess_ai_native_maturity(unknown_profile, _groups(unknown_profile), _ready_quality(), run_id="3")

    assert _risk(high, "external_api_only").severity == "high"
    assert _risk(high, "no_proprietary_data_evidence").severity == "medium"
    assert _risk(low, "external_api_only").severity == "low"
    assert _risk(low, "no_production_inference_evidence").severity == "low"
    assert _risk(unknown, "unknown").severity == "unknown"


def test_maps_initial_technical_gap_vocabulary_without_recommendations() -> None:
    profile = _profile(
        "Resumo: Healthtech AI-native com visao computacional para exames. "
        "Setor: healthtech. Produto: triagem clinica por computer vision. "
        "Sinais de IA: modelos proprietarios de computer vision. "
        "Tecnologias: inference em producao, grandes volumes de dados clinicos, latencia baixa. "
        "Clientes: hospitais. Founders: Bia Costa. Localizacao: Sao Paulo, SP."
    )

    assessment = assess_ai_native_maturity(profile, _groups(profile), _ready_quality(), run_id="run-gaps")

    gap_types = {gap.gap_type for gap in assessment.technical_gaps}
    assert {"computer_vision", "healthcare_ai", "model_serving", "data_acceleration"} <= gap_types
    assert all("NVIDIA" not in gap.description for gap in assessment.technical_gaps)


def test_conflicting_evidence_triggers_human_review() -> None:
    profile = _profile(
        "Resumo: Plataforma AI-native. Setor: dados. Produto: IA para documentos. "
        "Sinais de IA: modelos proprietarios. Tecnologias: MLOps e inferencia em producao. "
        "Clientes: bancos. Founders: Ana Silva. Localizacao: Campinas, SP."
    )
    groups = structure_evidence_by_field(
        (
            *claims_from_profile(profile),
            claims_from_profile(profile)[9].__class__(
                field_name="ai_signals",
                value="nao usa inteligencia artificial",
                evidences=profile.ai_signals.evidences,
            ),
        )
    )

    assessment = assess_ai_native_maturity(profile, groups, _ready_quality(), run_id="run-conflict")

    assert assessment.nvidia_opportunity_urgency == "human_review"
    assert assessment.ready_for_recommendation is False
    assert "conflicting_ai_signals" in assessment.insufficient_evidence_fields


def _profile(text: str):
    return extract_startup_profile(
        (
            CollectedPage(
                url="https://deepdocs.ai/",
                title="DeepDocs",
                main_text=text,
                collected_at=COLLECTED_AT,
                status_code=200,
            ),
        )
    )


def _groups(profile):
    return structure_evidence_by_field(claims_from_profile(profile))


def _ready_quality() -> CollectionQualitySummary:
    return CollectionQualitySummary(
        candidate_count=1,
        official_site_found_count=1,
        official_site_found_rate=1.0,
        minimum_profile_complete_count=1,
        minimum_profile_complete_rate=1.0,
        average_evidences_per_startup=6.0,
        unknown_fields=(),
        source_success_rates=(),
        ready_for_evaluation=True,
        readiness_reasons=("ready_for_ai_native_evaluation",),
    )


def _blocked_quality() -> CollectionQualitySummary:
    return CollectionQualitySummary(
        candidate_count=1,
        official_site_found_count=0,
        official_site_found_rate=0.0,
        minimum_profile_complete_count=0,
        minimum_profile_complete_rate=0.0,
        average_evidences_per_startup=1.0,
        unknown_fields=(("product", 1), ("ai_signals", 1)),
        source_success_rates=(),
        ready_for_evaluation=False,
        readiness_reasons=("minimum_profile_coverage_below_threshold",),
    )


def _risk(assessment, risk_type: str):
    return next(risk for risk in assessment.wrapper_dependency_risks if risk.risk_type == risk_type)
