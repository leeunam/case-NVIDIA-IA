import json

from nvidia_startup_intel.ai_native_assessment import ai_native_assessment_to_dict, assess_ai_native_maturity
from nvidia_startup_intel.collection_quality import summarize_collection_quality
from nvidia_startup_intel.discovery import CandidateStartup, DiscoverySourceType
from nvidia_startup_intel.evidence import claims_from_profile, structure_evidence_by_field
from nvidia_startup_intel.page_collection import CollectedPage
from nvidia_startup_intel.search_params import UNKNOWN
from nvidia_startup_intel.startup_profile import extract_startup_profile


def test_ai_native_assessment_reports_only_technical_gap_vocabulary() -> None:
    profile, evidence_groups, quality = _assessment_inputs(
        "VisionOps AI",
        (
            "Resumo: Plataforma AI-native para inspecao industrial. "
            "Setor: industria. "
            "Produto: Computer vision para controle de qualidade. "
            "Sinais de IA: modelos proprietarios, fine-tuning, MLOps e feedback loop. "
            "Tecnologias: inferencia em producao, model serving, dados proprietarios e computer vision. "
            "Localizacao: Sao Paulo, SP."
        ),
    )

    assessment = assess_ai_native_maturity(profile, evidence_groups, quality, run_id="run-001")

    assert quality.ready_for_evaluation is True
    assert assessment.classification == "ai_native"
    assert assessment.ready_for_recommendation is True
    assert profile.customers.value == UNKNOWN
    assert profile.funding.value == UNKNOWN
    assert {gap.gap_type for gap in assessment.technical_gaps} <= {
        "model_serving",
        "llm_customization",
        "data_acceleration",
        "voice_ai",
        "computer_vision",
        "robotics_simulation",
        "healthcare_ai",
        "cybersecurity_ai",
        UNKNOWN,
    }


def test_generic_ai_mentions_classify_as_ai_enabled_without_recommendation_readiness() -> None:
    profile, evidence_groups, quality = _assessment_inputs(
        "SupportBot AI",
        (
            "Resumo: Plataforma de atendimento com chatbot. "
            "Setor: dados. "
            "Produto: Chatbot para suporte ao cliente. "
            "Sinais de IA: usa IA generativa via OpenAI API. "
            "Tecnologias: ChatGPT e GPT API. "
            "Localizacao: Curitiba, PR."
        ),
    )

    assessment = assess_ai_native_maturity(profile, evidence_groups, quality, run_id="run-002")

    assert quality.ready_for_evaluation is True
    assert assessment.classification == "ai_enabled"
    assert assessment.ready_for_recommendation is False
    assert "classification_confidence_below_threshold" in assessment.diagnostic_quality.reasons
    assert any(risk.risk_type == "external_api_only" and risk.severity == "high" for risk in assessment.wrapper_dependency_risks)


def test_profile_without_ai_evidence_classifies_as_non_ai_with_unknown_gap() -> None:
    profile, evidence_groups, quality = _assessment_inputs(
        "LedgerOps",
        (
            "Resumo: SaaS financeiro para conciliacao. "
            "Setor: fintech. "
            "Produto: Plataforma de gestao financeira para PMEs. "
            "Clientes: varejistas. "
            "Sinais de IA: nenhum uso informado. "
            "Tecnologias: integracoes bancarias e automacao de relatorios. "
            "Localizacao: Belo Horizonte, MG."
        ),
    )

    assessment = assess_ai_native_maturity(profile, evidence_groups, quality, run_id="run-003")

    assert quality.ready_for_evaluation is True
    assert assessment.classification == "non_ai"
    assert assessment.ready_for_recommendation is False
    assert assessment.technical_gaps[0].gap_type == UNKNOWN
    assert assessment.wrapper_dependency_risks[0].risk_type == UNKNOWN


def test_weak_collection_quality_returns_insufficient_evidence_assessment() -> None:
    profile = extract_startup_profile((), fallback_company_name="Unknown AI")
    quality = summarize_collection_quality((), ())

    assessment = assess_ai_native_maturity(profile, (), quality, run_id="run-004")

    assert quality.ready_for_evaluation is False
    assert assessment.classification == "insufficient_evidence"
    assert assessment.ready_for_recommendation is False
    assert assessment.nvidia_opportunity_urgency == "human_review"
    assert "collection_quality" in assessment.insufficient_evidence_fields
    assert assessment.diagnostic_quality.requires_human_review is True


def test_assessment_serializes_to_plain_json_payload() -> None:
    profile, evidence_groups, quality = _assessment_inputs(
        "DataForge AI",
        (
            "Resumo: Plataforma AI-native para dados proprietarios. "
            "Setor: dados. "
            "Produto: Copiloto analitico com NLP. "
            "Sinais de IA: modelos proprietarios, fine-tuning e feedback loop. "
            "Tecnologias: inferencia em producao, model serving e dados proprietarios. "
            "Localizacao: Recife, PE."
        ),
    )
    assessment = assess_ai_native_maturity(profile, evidence_groups, quality, run_id="run-005")

    payload = ai_native_assessment_to_dict(assessment)

    assert payload["schema_version"] == "ai_native_assessment.v1"
    assert payload["run_id"] == "run-005"
    assert payload["classification"] == "ai_native"
    assert payload["ready_for_recommendation"] is True
    assert json.loads(json.dumps(payload))["diagnostic_quality"]["ready_for_recommendation"] is True


def _assessment_inputs(company_name: str, page_text: str):
    site = f"https://{company_name.lower().replace(' ', '')}.ai"
    profile = extract_startup_profile(
        (
            CollectedPage(
                url=site,
                title=company_name,
                main_text=page_text,
                collected_at="2026-06-26T12:00:00+00:00",
                status_code=200,
            ),
        ),
        official_site=site,
    )
    candidate = CandidateStartup(
        name=company_name,
        normalized_name=company_name.lower(),
        primary_url=site,
        discovery_source="fixture",
        evidence_snippet=f"{company_name} fixture.",
        confidence_score=0.9,
        source_types=(DiscoverySourceType.COMPANY,),
        evidences=(),
    )
    quality = summarize_collection_quality((candidate,), (profile,))
    evidence_groups = structure_evidence_by_field(claims_from_profile(profile))
    return profile, evidence_groups, quality
