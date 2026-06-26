from __future__ import annotations

from pathlib import Path
import unittest

from nvidia_startup_intel.ai_native_assessment import (
    AINativeAssessment,
    DiagnosticQuality,
    TechnicalGap,
    WrapperDependencyRisk,
)
from nvidia_startup_intel.collection_quality import CollectionQualitySummary
from nvidia_startup_intel.evidence import FieldEvidenceGroup
from nvidia_startup_intel.gap_space_assessment import assess_gap_space
from nvidia_startup_intel.nvidia_knowledge import (
    build_nvidia_knowledge_query,
    load_nvidia_knowledge_corpus,
)
from nvidia_startup_intel.search_params import UNKNOWN
from nvidia_startup_intel.startup_profile import ClaimSource, FieldEvidence, ProfileField, StartupProfile


class GapSpaceAssessmentTests(unittest.TestCase):
    def test_supported_gap_maps_to_nvidia_taxonomy_with_replayable_query(self) -> None:
        evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        gap = TechnicalGap(
            gap_type="model_serving",
            description="Needs lower latency inference and production model serving.",
            severity="high",
            confidence=0.86,
            evidences=(evidence,),
        )
        corpus = load_nvidia_knowledge_corpus(_fixture_path())

        gap_space = assess_gap_space(
            profile=_profile(evidence),
            collection_quality=_collection_quality(),
            assessment=_assessment(gap),
            evidence_groups=(),
            corpus=corpus,
            run_id="run-issue-61",
        )

        self.assertEqual(gap_space.schema_version, "gap_space_assessment.v1")
        self.assertEqual(gap_space.run_id, "run-issue-61")
        self.assertEqual(gap_space.startup_identifier, "VetAI")
        self.assertEqual(gap_space.corpus_version, "official-nvidia-fixture.v1")
        self.assertTrue(gap_space.quality.ready_for_recommendation)
        self.assertFalse(gap_space.quality.requires_human_review)

        mapping = gap_space.mappings[0]
        self.assertEqual(mapping.gap_type, "model_serving")
        self.assertEqual(mapping.support_status, "supported")
        self.assertFalse(mapping.is_hypothesis)
        self.assertFalse(mapping.requires_human_review)
        self.assertEqual(mapping.observed_evidences, (evidence,))
        self.assertIn("official NVIDIA taxonomy supports model_serving", mapping.inference_rationale)
        self.assertEqual(mapping.confidence, 0.86)
        self.assertIn(
            "NVIDIA NIM",
            tuple(target.stack_name for target in mapping.taxonomy_targets),
        )
        self.assertEqual(
            mapping.retrieval_query,
            build_nvidia_knowledge_query(
                gap_type=mapping.retrieval_gap_type,
                description=mapping.retrieval_description,
                startup_signals=mapping.retrieval_startup_signals,
            ),
        )
        self.assertEqual(gap_space.retrieval_queries, (mapping.retrieval_query,))

    def test_weak_gap_evidence_requires_human_review_before_recommendation(self) -> None:
        evidence = _startup_evidence(
            snippet="A VetAI talvez precise reduzir latencia de inferencia em producao."
        )
        gap = TechnicalGap(
            gap_type="model_serving",
            description="May need lower latency inference and production model serving.",
            severity="high",
            confidence=0.42,
            evidences=(evidence,),
        )
        corpus = load_nvidia_knowledge_corpus(_fixture_path())

        gap_space = assess_gap_space(
            profile=_profile(evidence),
            collection_quality=_collection_quality(),
            assessment=_assessment(gap),
            evidence_groups=(),
            corpus=corpus,
            run_id="run-issue-61",
        )

        self.assertFalse(gap_space.quality.ready_for_recommendation)
        self.assertTrue(gap_space.quality.requires_human_review)
        self.assertIn("low_gap_confidence", gap_space.quality.reasons)

        mapping = gap_space.mappings[0]
        self.assertEqual(mapping.support_status, "hypothesis")
        self.assertTrue(mapping.is_hypothesis)
        self.assertTrue(mapping.requires_human_review)
        self.assertEqual(mapping.observed_evidences, (evidence,))
        self.assertIn("low_gap_confidence", mapping.review_reasons)
        self.assertEqual(gap_space.retrieval_queries, (mapping.retrieval_query,))

    def test_high_wrapper_risk_requires_human_review_even_when_gap_maps_to_taxonomy(self) -> None:
        evidence = _startup_evidence(
            snippet="A VetAI usa OpenAI API sem evidencias de dados proprietarios."
        )
        gap = TechnicalGap(
            gap_type="model_serving",
            description="Needs lower latency inference and production model serving.",
            severity="high",
            confidence=0.86,
            evidences=(evidence,),
        )
        wrapper_risk = WrapperDependencyRisk(
            risk_type="external_api_only",
            severity="high",
            confidence=0.84,
            rationale="Evidence suggests external API dependency without defensibility.",
            evidences=(evidence,),
        )

        gap_space = assess_gap_space(
            profile=_profile(evidence),
            collection_quality=_collection_quality(),
            assessment=_assessment(gap, wrapper_dependency_risks=(wrapper_risk,)),
            evidence_groups=(),
            corpus=load_nvidia_knowledge_corpus(_fixture_path()),
            run_id="run-issue-61",
        )

        self.assertFalse(gap_space.quality.ready_for_recommendation)
        self.assertTrue(gap_space.quality.requires_human_review)
        self.assertIn("high_wrapper_risk", gap_space.quality.reasons)

        mapping = gap_space.mappings[0]
        self.assertEqual(mapping.support_status, "hypothesis")
        self.assertTrue(mapping.requires_human_review)
        self.assertIn("high_wrapper_risk", mapping.review_reasons)

    def test_unknown_stack_field_requires_human_review_with_collection_target(self) -> None:
        evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao."
        )
        gap = TechnicalGap(
            gap_type="model_serving",
            description="Needs lower latency inference and production model serving.",
            severity="high",
            confidence=0.86,
            evidences=(evidence,),
        )

        gap_space = assess_gap_space(
            profile=_profile(evidence),
            collection_quality=_collection_quality(unknown_fields=(("technologies_used", 1),)),
            assessment=_assessment(gap),
            evidence_groups=(),
            corpus=load_nvidia_knowledge_corpus(_fixture_path()),
            run_id="run-issue-61",
        )

        self.assertFalse(gap_space.quality.ready_for_recommendation)
        self.assertIn("unknown_field:technologies_used", gap_space.quality.reasons)

        mapping = gap_space.mappings[0]
        self.assertEqual(mapping.support_status, "hypothesis")
        self.assertTrue(mapping.requires_human_review)
        self.assertIn("unknown_field:technologies_used", mapping.review_reasons)
        self.assertEqual(gap_space.retrieval_queries, (mapping.retrieval_query,))

    def test_conflicting_evidence_requires_human_review_before_gap_mapping_is_supported(self) -> None:
        evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao."
        )
        conflicting_evidence = _startup_evidence(
            snippet="Outra pagina descreve a VetAI como consultoria sem produto de IA."
        )
        gap = TechnicalGap(
            gap_type="model_serving",
            description="Needs lower latency inference and production model serving.",
            severity="high",
            confidence=0.86,
            evidences=(evidence,),
        )
        evidence_groups = (
            FieldEvidenceGroup(
                field_name="product",
                value="AI product",
                evidences=(evidence, conflicting_evidence),
                has_conflict=True,
                conflicting_values=("AI product", "consulting"),
            ),
        )

        gap_space = assess_gap_space(
            profile=_profile(evidence),
            collection_quality=_collection_quality(),
            assessment=_assessment(gap),
            evidence_groups=evidence_groups,
            corpus=load_nvidia_knowledge_corpus(_fixture_path()),
            run_id="run-issue-61",
        )

        self.assertFalse(gap_space.quality.ready_for_recommendation)
        self.assertIn("conflicting_startup_evidence", gap_space.quality.reasons)

        mapping = gap_space.mappings[0]
        self.assertEqual(mapping.support_status, "hypothesis")
        self.assertTrue(mapping.requires_human_review)
        self.assertIn("conflicting_startup_evidence", mapping.review_reasons)

    def test_gap_outside_nvidia_taxonomy_is_unsupported_and_requires_human_review(self) -> None:
        evidence = _startup_evidence(
            snippet="A VetAI precisa automatizar billing quantico para clientes enterprise."
        )
        gap = TechnicalGap(
            gap_type="quantum_billing",
            description="Needs quantum billing workflow acceleration.",
            severity="medium",
            confidence=0.86,
            evidences=(evidence,),
        )

        gap_space = assess_gap_space(
            profile=_profile(evidence),
            collection_quality=_collection_quality(),
            assessment=_assessment(gap),
            evidence_groups=(),
            corpus=load_nvidia_knowledge_corpus(_fixture_path()),
            run_id="run-issue-61",
        )

        self.assertFalse(gap_space.quality.ready_for_recommendation)
        self.assertIn("unsupported_gap_type", gap_space.quality.reasons)

        mapping = gap_space.mappings[0]
        self.assertEqual(mapping.support_status, "unsupported")
        self.assertTrue(mapping.is_hypothesis)
        self.assertTrue(mapping.requires_human_review)
        self.assertEqual(mapping.taxonomy_targets, ())
        self.assertIn("unsupported_gap_type", mapping.review_reasons)


def _fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "nvidia_knowledge_official_fixture.json"


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
) -> AINativeAssessment:
    return AINativeAssessment(
        schema_version="ai_native_assessment.v1",
        run_id="run-issue-61",
        company_name="VetAI",
        classification="ai_native",
        confidence=0.82,
        nvidia_opportunity_urgency="urgent",
        criteria_results=(),
        positive_signals=(),
        technical_gaps=(gap,),
        wrapper_dependency_risks=wrapper_dependency_risks,
        insufficient_evidence_fields=(),
        evidences=gap.evidences,
        diagnostic_quality=DiagnosticQuality(
            ready_for_recommendation=True,
            requires_human_review=False,
            reasons=("ready_for_recommendation",),
        ),
        ready_for_recommendation=True,
    )


def _collection_quality(
    *,
    unknown_fields: tuple[tuple[str, int], ...] = (),
    ready_for_evaluation: bool = True,
) -> CollectionQualitySummary:
    return CollectionQualitySummary(
        candidate_count=1,
        official_site_found_count=1,
        official_site_found_rate=1.0,
        minimum_profile_complete_count=1,
        minimum_profile_complete_rate=1.0,
        average_evidences_per_startup=4.0,
        unknown_fields=unknown_fields,
        source_success_rates=(),
        ready_for_evaluation=ready_for_evaluation,
        readiness_reasons=("ready_for_ai_native_evaluation",)
        if ready_for_evaluation
        else ("insufficient_public_evidence",),
    )


def _profile(evidence: FieldEvidence) -> StartupProfile:
    unknown = ProfileField(value=UNKNOWN, claim_source=ClaimSource.UNKNOWN, evidences=())
    return StartupProfile(
        schema_version="startup_profile.v1",
        company_name=ProfileField(value="VetAI", claim_source=ClaimSource.OBSERVED, evidences=(evidence,)),
        official_site=ProfileField(value="https://vetai.example", claim_source=ClaimSource.OBSERVED, evidences=(evidence,)),
        company_summary=ProfileField(value="AI-native veterinary triage platform.", claim_source=ClaimSource.OBSERVED, evidences=(evidence,)),
        sector=ProfileField(value="healthtech", claim_source=ClaimSource.INFERRED, evidences=(evidence,)),
        product=ProfileField(value="AI triage product", claim_source=ClaimSource.OBSERVED, evidences=(evidence,)),
        customers=unknown,
        funding=unknown,
        founders=unknown,
        technologies_used=unknown,
        ai_signals=ProfileField(value="inferencia em producao", claim_source=ClaimSource.OBSERVED, evidences=(evidence,)),
        location=unknown,
    )


if __name__ == "__main__":
    unittest.main()
