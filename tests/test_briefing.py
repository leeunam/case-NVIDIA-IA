from __future__ import annotations

import json
from pathlib import Path
import unittest

from nvidia_startup_intel.ai_native_assessment import (
    AINativeAssessment,
    DiagnosticQuality,
    TechnicalGap,
)
from nvidia_startup_intel.briefing import executive_briefing_to_dict, generate_executive_briefing
from nvidia_startup_intel.collection_quality import CollectionQualitySummary
from nvidia_startup_intel.evidence import FieldEvidenceGroup
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


def _fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "nvidia_knowledge_official_fixture.json"


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


def _assessment(gap: TechnicalGap) -> AINativeAssessment:
    return AINativeAssessment(
        schema_version="ai_native_assessment.v1",
        run_id="run-briefing-001",
        company_name="VetAI",
        classification="ai_native",
        confidence=0.82,
        nvidia_opportunity_urgency="urgent",
        criteria_results=(),
        positive_signals=(),
        technical_gaps=(gap,),
        wrapper_dependency_risks=(),
        insufficient_evidence_fields=(),
        evidences=gap.evidences,
        diagnostic_quality=DiagnosticQuality(
            ready_for_recommendation=True,
            requires_human_review=False,
            reasons=("ready_for_recommendation",),
        ),
        ready_for_recommendation=True,
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
