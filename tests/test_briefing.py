from __future__ import annotations

import json
from pathlib import Path
import unittest

from nvidia_startup_intel.ai_native_assessment import (
    AINativeAssessment,
    DiagnosticQuality,
    TechnicalGap,
    WrapperDependencyRisk,
)
from nvidia_startup_intel.briefing import (
    briefing_narrative_to_dict,
    executive_briefing_to_dict,
    generate_briefing_narrative,
    generate_executive_briefing,
    generate_human_review_briefing,
    human_review_briefing_to_dict,
)
from nvidia_startup_intel.collection_quality import CollectionQualitySummary
from nvidia_startup_intel.evidence import FieldEvidenceGroup
from nvidia_startup_intel.framework_adapters import (
    DeterministicFakeLLMClient,
    LLMGenerationRequest,
    LLMGenerationResponse,
)
from nvidia_startup_intel.nvidia_knowledge import (
    load_nvidia_knowledge_corpus,
    retrieve_nvidia_knowledge_by_gap,
)
from nvidia_startup_intel.nvidia_recommendation import build_nvidia_recommendations
from nvidia_startup_intel.search_params import UNKNOWN
from nvidia_startup_intel.startup_profile import ClaimSource, FieldEvidence, ProfileField, StartupProfile


class ExecutiveBriefingTests(unittest.TestCase):
    def test_supported_recommendation_becomes_typed_executive_briefing(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        profile = _profile(startup_evidence)
        evidence_groups = (
            FieldEvidenceGroup(
                field_name="ai_signals",
                value="inferencia em producao",
                evidences=(startup_evidence,),
                has_conflict=False,
                conflicting_values=(),
            ),
        )
        assessment = _assessment(_model_serving_gap(startup_evidence))
        recommendation_set = _supported_recommendation_set(profile, evidence_groups, assessment)

        briefing = generate_executive_briefing(
            profile=profile,
            evidence_groups=evidence_groups,
            collection_quality=_collection_quality(),
            assessment=assessment,
            recommendation_set=recommendation_set,
        )

        self.assertEqual(briefing.schema_version, "executive_briefing.v1")
        self.assertEqual(briefing.run_id, "run-briefing-001")
        self.assertEqual(briefing.startup_identifier, "VetAI")
        self.assertEqual(briefing.status, "ready_for_use")
        self.assertEqual(briefing.next_action, "prepare_technical_outreach")
        self.assertIn("VetAI", briefing.executive_summary)
        self.assertIn("NVIDIA NIM for Developers", briefing.executive_summary)
        self.assertEqual(briefing.opportunity, "urgent")

        claim_types = {claim.claim_type for claim in briefing.claims}
        self.assertTrue({"observed", "inferred", "recommended", "unknown"} <= claim_types)

        recommended_claims = [claim for claim in briefing.claims if claim.claim_type == "recommended"]
        self.assertEqual(len(recommended_claims), 1)
        self.assertEqual(recommended_claims[0].section, "recommendations")
        self.assertEqual(recommended_claims[0].evidence_references, (startup_evidence,))
        self.assertEqual(recommended_claims[0].citation_references[0].document_id, "nvidia-nim-developers")

        unknown_claims = [claim for claim in briefing.claims if claim.claim_type == "unknown"]
        self.assertTrue(any("funding" in claim.text for claim in unknown_claims))
        self.assertTrue(any("customers" in claim.text for claim in unknown_claims))
        self.assertTrue(any("founders" in claim.text for claim in unknown_claims))
        self.assertTrue(any("technologies_used" in claim.text for claim in unknown_claims))
        self.assertTrue(any(question.field_name == "funding" for question in briefing.pending_questions))

        self.assertEqual(briefing.evidence_references, (startup_evidence,))
        self.assertEqual(briefing.citation_references[0].chunk_id, "nvidia-nim-developers:0")

    def test_executive_briefing_serializes_sources_without_losing_claim_types(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        profile = _profile(startup_evidence)
        evidence_groups = (
            FieldEvidenceGroup(
                field_name="ai_signals",
                value="inferencia em producao",
                evidences=(startup_evidence,),
                has_conflict=False,
                conflicting_values=(),
            ),
        )
        assessment = _assessment(_model_serving_gap(startup_evidence))
        recommendation_set = _supported_recommendation_set(profile, evidence_groups, assessment)
        briefing = generate_executive_briefing(
            profile=profile,
            evidence_groups=evidence_groups,
            collection_quality=_collection_quality(),
            assessment=assessment,
            recommendation_set=recommendation_set,
        )

        serialized = executive_briefing_to_dict(briefing)

        json.dumps(serialized)
        self.assertEqual(serialized["schema_version"], "executive_briefing.v1")
        self.assertEqual(serialized["claims"][0]["claim_type"], "observed")
        self.assertEqual(serialized["citation_references"][0]["document_id"], "nvidia-nim-developers")
        self.assertEqual(serialized["evidence_references"][0]["url"], "https://vetai.example/product")

    def test_llm_ready_narrative_preserves_executive_briefing_contract(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        profile = _profile(startup_evidence)
        evidence_groups = (
            FieldEvidenceGroup(
                field_name="ai_signals",
                value="inferencia em producao",
                evidences=(startup_evidence,),
                has_conflict=False,
                conflicting_values=(),
            ),
        )
        assessment = _assessment(_model_serving_gap(startup_evidence))
        recommendation_set = _supported_recommendation_set(profile, evidence_groups, assessment)
        briefing = generate_executive_briefing(
            profile=profile,
            evidence_groups=evidence_groups,
            collection_quality=_collection_quality(),
            assessment=assessment,
            recommendation_set=recommendation_set,
        )

        narrative = generate_briefing_narrative(
            briefing=briefing,
            llm_client=DeterministicFakeLLMClient(),
        )

        self.assertEqual(narrative.schema_version, "briefing_narrative.v1")
        self.assertEqual(narrative.run_id, briefing.run_id)
        self.assertEqual(narrative.startup_identifier, briefing.startup_identifier)
        self.assertEqual(narrative.source_briefing_schema_version, "executive_briefing.v1")
        self.assertEqual(narrative.source_briefing_status, "ready_for_use")
        self.assertEqual(narrative.next_action, "prepare_technical_outreach")
        self.assertEqual(narrative.claims, briefing.claims)
        self.assertEqual(narrative.evidence_references, briefing.evidence_references)
        self.assertEqual(narrative.citation_references, briefing.citation_references)
        self.assertTrue(any("funding" in unknown for unknown in narrative.unknowns))
        self.assertEqual(narrative.llm_response.request_purpose, "briefing_narrative")
        self.assertEqual(narrative.llm_request.structured_output_schema, "briefing_narrative.v1")
        self.assertEqual(narrative.llm_request.metadata["source_briefing_schema_version"], "executive_briefing.v1")
        self.assertNotIn("Series A", narrative.llm_request.user_prompt)
        self.assertNotIn("Fortune 500", narrative.llm_request.user_prompt)

        serialized = briefing_narrative_to_dict(narrative)
        json.dumps(serialized)
        self.assertEqual(serialized["claims"][0]["claim_type"], "observed")
        self.assertEqual(serialized["citation_references"][0]["document_id"], "nvidia-nim-developers")
        self.assertEqual(serialized["llm_response"]["provider"], "local_fake")

    def test_llm_ready_narrative_rejects_unsupported_llm_facts(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        profile = _profile(startup_evidence)
        evidence_groups = (
            FieldEvidenceGroup(
                field_name="ai_signals",
                value="inferencia em producao",
                evidences=(startup_evidence,),
                has_conflict=False,
                conflicting_values=(),
            ),
        )
        assessment = _assessment(_model_serving_gap(startup_evidence))
        recommendation_set = _supported_recommendation_set(profile, evidence_groups, assessment)
        briefing = generate_executive_briefing(
            profile=profile,
            evidence_groups=evidence_groups,
            collection_quality=_collection_quality(),
            assessment=assessment,
            recommendation_set=recommendation_set,
        )

        narrative = generate_briefing_narrative(
            briefing=briefing,
            llm_client=_UnsupportedFactLLMClient(),
        )

        self.assertNotIn("Series A", narrative.narrative_text)
        self.assertNotIn("Fortune 500", narrative.narrative_text)
        self.assertNotIn("Series A", narrative.llm_response.content)
        self.assertNotIn("Fortune 500", narrative.llm_response.content)
        self.assertIn("funding is unknown", narrative.narrative_text)
        self.assertIn("llm_narrative_rejected_unsupported_terms", narrative.audit_reasons)
        self.assertEqual(narrative.claims, briefing.claims)

    def test_blocked_recommendation_generates_human_review_briefing(self) -> None:
        profile_evidence = _startup_evidence(
            snippet="A VetAI usa inteligencia artificial no produto."
        )
        profile = _profile(profile_evidence)
        blocked_gap = TechnicalGap(
            gap_type="model_serving",
            description="Needs lower latency inference and production model serving.",
            severity="high",
            confidence=0.86,
            evidences=(),
        )
        assessment = _assessment(blocked_gap)
        recommendation_set = _recommendation_set_for_gap(
            profile=profile,
            gap=blocked_gap,
            evidence_groups=(),
            assessment=assessment,
        )

        briefing = generate_human_review_briefing(
            profile=profile,
            evidence_groups=(),
            collection_quality=_collection_quality(),
            assessment=assessment,
            recommendation_set=recommendation_set,
        )

        self.assertEqual(briefing.schema_version, "human_review_briefing.v1")
        self.assertEqual(briefing.run_id, "run-briefing-001")
        self.assertEqual(briefing.startup_identifier, "VetAI")
        self.assertEqual(briefing.status, "ready_for_human_review")
        self.assertEqual(briefing.area_of_operation, "healthtech")
        self.assertEqual(briefing.supported_recommendations, ())
        self.assertEqual(briefing.blocked_recommendations, recommendation_set.blocked_recommendations)
        self.assertIn("blocked_recommendation_requires_human_review", briefing.review_reasons)
        self.assertTrue(any(question.priority == "critical" for question in briefing.pending_questions))
        self.assertTrue(any(question.priority == "complementary" for question in briefing.pending_questions))
        self.assertEqual(len(briefing.audit_reasons), len(set(briefing.audit_reasons)))
        self.assertEqual(briefing.evidence_references, (profile_evidence,))
        self.assertEqual(briefing.citation_references[0].document_id, "nvidia-nim-developers")
        self.assertEqual(briefing.next_action, "resolve_blocking_evidence")

    def test_missing_nvidia_citation_keeps_hypothesis_out_of_supported_recommendations(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        profile = _profile(startup_evidence)
        gap = _model_serving_gap(startup_evidence)
        assessment = _assessment(gap)
        corpus = load_nvidia_knowledge_corpus(_fixture_path())
        retrieval = retrieve_nvidia_knowledge_by_gap(
            corpus,
            run_id="run-briefing-001",
            gap_type="quantum_billing",
            description="Need tax invoicing workflow support.",
            startup_signals=("accounts payable",),
            top_k=1,
        )
        recommendation_set = build_nvidia_recommendations(
            profile=profile,
            evidence_groups=(),
            collection_quality=_collection_quality(),
            assessment=assessment,
            retrievals=(retrieval,),
        )

        briefing = generate_human_review_briefing(
            profile=profile,
            evidence_groups=(),
            collection_quality=_collection_quality(),
            assessment=assessment,
            recommendation_set=recommendation_set,
        )

        self.assertEqual(briefing.supported_recommendations, ())
        self.assertEqual(briefing.hypothesis_recommendations, recommendation_set.hypotheses)
        self.assertIn("recommendation_hypothesis_requires_human_review", briefing.review_reasons)
        self.assertTrue(
            any(
                question.reason == "recommendation_hypothesis_requires_validation"
                for question in briefing.pending_questions
            )
        )
        self.assertEqual(briefing.citation_references, ())

    def test_high_wrapper_risk_becomes_human_review_reason_and_question(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI usa OpenAI API sem evidencias de dados proprietarios."
        )
        profile = _profile(startup_evidence)
        gap = _model_serving_gap(startup_evidence)
        risk = WrapperDependencyRisk(
            risk_type="external_api_dependency",
            severity="high",
            confidence=0.81,
            rationale="Evidence suggests dependency on an external API without proprietary data.",
            evidences=(startup_evidence,),
        )
        assessment = _assessment(gap, wrapper_dependency_risks=(risk,))
        recommendation_set = _recommendation_set_for_gap(
            profile=profile,
            gap=gap,
            evidence_groups=(),
            assessment=assessment,
        )

        briefing = generate_human_review_briefing(
            profile=profile,
            evidence_groups=(),
            collection_quality=_collection_quality(),
            assessment=assessment,
            recommendation_set=recommendation_set,
        )

        self.assertEqual(briefing.wrapper_risks, (risk,))
        self.assertIn("high_wrapper_risk_requires_human_review", briefing.review_reasons)
        self.assertTrue(
            any(question.field_name == "external_api_dependency" for question in briefing.pending_questions)
        )
        self.assertEqual(briefing.evidence_references, (startup_evidence,))

    def test_low_signal_collection_quality_is_carried_into_human_review(self) -> None:
        startup_evidence = _startup_evidence(snippet="A VetAI menciona inteligencia artificial.")
        profile = _profile(startup_evidence)
        gap = _model_serving_gap(startup_evidence)
        assessment = _assessment(
            gap,
            confidence=0.42,
            ready_for_recommendation=False,
            diagnostic_reasons=("low_ai_native_signal",),
        )
        collection_quality = CollectionQualitySummary(
            candidate_count=1,
            official_site_found_count=0,
            official_site_found_rate=0.0,
            minimum_profile_complete_count=0,
            minimum_profile_complete_rate=0.0,
            average_evidences_per_startup=1.0,
            unknown_fields=("technologies_used",),
            source_success_rates=(),
            ready_for_evaluation=False,
            readiness_reasons=("insufficient_public_evidence",),
        )
        recommendation_set = _recommendation_set_for_gap(
            profile=profile,
            gap=gap,
            evidence_groups=(),
            assessment=assessment,
            collection_quality=collection_quality,
        )

        briefing = generate_human_review_briefing(
            profile=profile,
            evidence_groups=(),
            collection_quality=collection_quality,
            assessment=assessment,
            recommendation_set=recommendation_set,
        )

        self.assertIn("low_signal_requires_human_review", briefing.review_reasons)
        self.assertIn("insufficient_public_evidence", briefing.audit_reasons)
        self.assertTrue(any(question.field_name == "collection_quality" for question in briefing.pending_questions))

    def test_conflicts_are_visible_in_human_review_briefing(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI se descreve como healthtech."
        )
        conflicting_evidence = FieldEvidence(
            url="https://directory.example/vetai",
            title="VetAI Directory",
            snippet="A VetAI aparece como fintech no diretorio.",
            collected_at="2026-06-23T00:00:00Z",
            source_type="directory",
        )
        profile = _profile(startup_evidence)
        gap = _model_serving_gap(startup_evidence)
        evidence_groups = (
            FieldEvidenceGroup(
                field_name="sector",
                value="healthtech",
                evidences=(startup_evidence, conflicting_evidence),
                has_conflict=True,
                conflicting_values=("healthtech", "fintech"),
            ),
        )
        assessment = _assessment(gap)
        recommendation_set = _recommendation_set_for_gap(
            profile=profile,
            gap=gap,
            evidence_groups=evidence_groups,
            assessment=assessment,
        )

        briefing = generate_human_review_briefing(
            profile=profile,
            evidence_groups=evidence_groups,
            collection_quality=_collection_quality(),
            assessment=assessment,
            recommendation_set=recommendation_set,
        )

        self.assertEqual(briefing.conflicts, evidence_groups)
        self.assertIn("conflicting_startup_evidence", briefing.review_reasons)
        self.assertTrue(any(question.field_name == "sector" for question in briefing.pending_questions))
        self.assertEqual(briefing.evidence_references, (startup_evidence, conflicting_evidence))

    def test_human_review_briefing_serializes_review_context(self) -> None:
        profile_evidence = _startup_evidence(snippet="A VetAI usa inteligencia artificial no produto.")
        profile = _profile(profile_evidence)
        blocked_gap = TechnicalGap(
            gap_type="model_serving",
            description="Needs lower latency inference and production model serving.",
            severity="high",
            confidence=0.86,
            evidences=(),
        )
        assessment = _assessment(blocked_gap)
        recommendation_set = _recommendation_set_for_gap(
            profile=profile,
            gap=blocked_gap,
            evidence_groups=(),
            assessment=assessment,
        )
        briefing = generate_human_review_briefing(
            profile=profile,
            evidence_groups=(),
            collection_quality=_collection_quality(),
            assessment=assessment,
            recommendation_set=recommendation_set,
        )

        serialized = human_review_briefing_to_dict(briefing)

        json.dumps(serialized)
        self.assertEqual(serialized["schema_version"], "human_review_briefing.v1")
        self.assertEqual(serialized["status"], "ready_for_human_review")
        self.assertEqual(serialized["blocked_recommendations"][0]["state"], "blocked")
        self.assertEqual(serialized["citation_references"][0]["document_id"], "nvidia-nim-developers")

    def test_llm_ready_narrative_preserves_human_review_context(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI usa OpenAI API sem evidencias de dados proprietarios."
        )
        profile = _profile(startup_evidence)
        gap = _model_serving_gap(startup_evidence)
        risk = WrapperDependencyRisk(
            risk_type="external_api_dependency",
            severity="high",
            confidence=0.81,
            rationale="Evidence suggests dependency on an external API without proprietary data.",
            evidences=(startup_evidence,),
        )
        assessment = _assessment(gap, wrapper_dependency_risks=(risk,))
        recommendation_set = _recommendation_set_for_gap(
            profile=profile,
            gap=gap,
            evidence_groups=(),
            assessment=assessment,
        )
        briefing = generate_human_review_briefing(
            profile=profile,
            evidence_groups=(),
            collection_quality=_collection_quality(),
            assessment=assessment,
            recommendation_set=recommendation_set,
        )

        narrative = generate_briefing_narrative(
            briefing=briefing,
            llm_client=DeterministicFakeLLMClient(),
        )

        self.assertEqual(narrative.source_briefing_schema_version, "human_review_briefing.v1")
        self.assertEqual(narrative.source_briefing_status, "ready_for_human_review")
        self.assertEqual(narrative.claims, briefing.discoveries)
        self.assertEqual(narrative.review_reasons, briefing.review_reasons)
        self.assertEqual(narrative.unknowns, briefing.unknowns)
        self.assertTrue(any("external_api_dependency" in risk_text for risk_text in narrative.risks))
        self.assertEqual(narrative.evidence_references, briefing.evidence_references)
        self.assertEqual(narrative.citation_references, briefing.citation_references)
        self.assertEqual(narrative.next_action, briefing.next_action)
        self.assertIn("high_wrapper_risk_requires_human_review", narrative.llm_request.user_prompt)

def _fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "nvidia_knowledge_official_fixture.json"


class _UnsupportedFactLLMClient:
    def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        return LLMGenerationResponse(
            schema_version="llm_generation_response.v1",
            request_purpose=request.purpose,
            provider="local_fake",
            model="unsupported-fact-fixture",
            model_version="v1",
            content="VetAI raised a Series A and serves Fortune 500 customers.",
            structured_output_schema=request.structured_output_schema,
            finish_reason="stop",
            metadata={"attempted_unsupported_fact": True},
        )


def _supported_recommendation_set(
    profile: StartupProfile,
    evidence_groups: tuple[FieldEvidenceGroup, ...],
    assessment: AINativeAssessment,
):
    gap = assessment.technical_gaps[0]
    corpus = load_nvidia_knowledge_corpus(_fixture_path())
    retrieval = retrieve_nvidia_knowledge_by_gap(
        corpus,
        run_id="run-briefing-001",
        gap_type=gap.gap_type,
        description=gap.description,
        startup_signals=("inference", "latency"),
        top_k=1,
    )
    return build_nvidia_recommendations(
        profile=profile,
        evidence_groups=evidence_groups,
        collection_quality=_collection_quality(),
        assessment=assessment,
        retrievals=(retrieval,),
    )


def _recommendation_set_for_gap(
    *,
    profile: StartupProfile,
    gap: TechnicalGap,
    evidence_groups: tuple[FieldEvidenceGroup, ...],
    assessment: AINativeAssessment,
    collection_quality: CollectionQualitySummary | None = None,
):
    corpus = load_nvidia_knowledge_corpus(_fixture_path())
    retrieval = retrieve_nvidia_knowledge_by_gap(
        corpus,
        run_id="run-briefing-001",
        gap_type=gap.gap_type,
        description=gap.description,
        startup_signals=("inference", "latency"),
        top_k=1,
    )
    return build_nvidia_recommendations(
        profile=profile,
        evidence_groups=evidence_groups,
        collection_quality=collection_quality or _collection_quality(),
        assessment=assessment,
        retrievals=(retrieval,),
    )


def _model_serving_gap(evidence: FieldEvidence) -> TechnicalGap:
    return TechnicalGap(
        gap_type="model_serving",
        description="Needs lower latency inference and production model serving.",
        severity="high",
        confidence=0.86,
        evidences=(evidence,),
    )


def _startup_evidence(*, snippet: str) -> FieldEvidence:
    return FieldEvidence(
        url="https://vetai.example/product",
        title="VetAI Product",
        snippet=snippet,
        collected_at="2026-06-23T00:00:00Z",
        source_type="official_site",
    )


def _assessment(
    gap: TechnicalGap,
    *,
    wrapper_dependency_risks: tuple[WrapperDependencyRisk, ...] = (),
    confidence: float = 0.82,
    ready_for_recommendation: bool = True,
    diagnostic_reasons: tuple[str, ...] = ("ready_for_recommendation",),
) -> AINativeAssessment:
    return AINativeAssessment(
        schema_version="ai_native_assessment.v1",
        run_id="run-briefing-001",
        company_name="VetAI",
        classification="ai_native",
        confidence=confidence,
        nvidia_opportunity_urgency="urgent",
        criteria_results=(),
        positive_signals=(),
        technical_gaps=(gap,),
        wrapper_dependency_risks=wrapper_dependency_risks,
        insufficient_evidence_fields=(),
        evidences=tuple(
            dict.fromkeys(
                (
                    *gap.evidences,
                    *(evidence for risk in wrapper_dependency_risks for evidence in risk.evidences),
                )
            )
        ),
        diagnostic_quality=DiagnosticQuality(
            ready_for_recommendation=ready_for_recommendation,
            requires_human_review=not ready_for_recommendation,
            reasons=diagnostic_reasons,
        ),
        ready_for_recommendation=ready_for_recommendation,
    )


def _collection_quality() -> CollectionQualitySummary:
    return CollectionQualitySummary(
        candidate_count=1,
        official_site_found_count=1,
        official_site_found_rate=1.0,
        minimum_profile_complete_count=1,
        minimum_profile_complete_rate=1.0,
        average_evidences_per_startup=4.0,
        unknown_fields=(),
        source_success_rates=(),
        ready_for_evaluation=True,
        readiness_reasons=("ready_for_ai_native_evaluation",),
    )


def _profile(evidence: FieldEvidence) -> StartupProfile:
    unknown = ProfileField(value=UNKNOWN, claim_source=ClaimSource.UNKNOWN, evidences=())
    return StartupProfile(
        schema_version="startup_profile.v1",
        company_name=ProfileField(value="VetAI", claim_source=ClaimSource.OBSERVED, evidences=(evidence,)),
        official_site=ProfileField(
            value="https://vetai.example",
            claim_source=ClaimSource.OBSERVED,
            evidences=(evidence,),
        ),
        company_summary=ProfileField(
            value="AI-native veterinary triage platform.",
            claim_source=ClaimSource.OBSERVED,
            evidences=(evidence,),
        ),
        sector=ProfileField(value="healthtech", claim_source=ClaimSource.INFERRED, evidences=(evidence,)),
        product=ProfileField(value="AI triage product", claim_source=ClaimSource.OBSERVED, evidences=(evidence,)),
        customers=unknown,
        funding=unknown,
        founders=unknown,
        technologies_used=unknown,
        ai_signals=ProfileField(
            value="inferencia em producao",
            claim_source=ClaimSource.OBSERVED,
            evidences=(evidence,),
        ),
        location=unknown,
    )


if __name__ == "__main__":
    unittest.main()
