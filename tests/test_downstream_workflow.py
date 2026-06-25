from __future__ import annotations

from pathlib import Path
import unittest

from nvidia_startup_intel.ai_native_assessment import AINativeAssessment, DiagnosticQuality, TechnicalGap
from nvidia_startup_intel.collection_quality import CollectionQualitySummary
from nvidia_startup_intel.evidence import FieldEvidenceGroup
from nvidia_startup_intel.nvidia_knowledge import NVIDIAKnowledgeRetrieval, load_nvidia_knowledge_corpus
from nvidia_startup_intel.search_params import UNKNOWN
from nvidia_startup_intel.startup_profile import ClaimSource, FieldEvidence, ProfileField, StartupProfile
from nvidia_startup_intel.workflow_graph import DownstreamWorkflowRuntime, build_local_downstream_workflow


class DownstreamWorkflowTests(unittest.TestCase):
    def test_supported_gap_generates_executive_briefing_without_langgraph(self) -> None:
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
        gap = _model_serving_gap(startup_evidence)
        assessment = _assessment(gap)
        runtime = DownstreamWorkflowRuntime(corpus=load_nvidia_knowledge_corpus(_fixture_path()))
        workflow = build_local_downstream_workflow(runtime)

        state = workflow.invoke(
            {
                "run_id": "run-issue-10",
                "profile": profile,
                "evidence_groups": evidence_groups,
                "collection_quality": _collection_quality(),
                "assessment": assessment,
            }
        )

        self.assertEqual(state["next_action"], "briefing_generated")
        self.assertEqual(state["errors"], ())
        self.assertEqual(state["retrievals"][0].schema_version, "nvidia_knowledge.v1")
        self.assertEqual(state["recommendation_set"].schema_version, "nvidia_recommendation.v1")
        self.assertEqual(state["executive_briefing"].schema_version, "executive_briefing.v1")
        self.assertEqual(state["executive_briefing"].status, "ready_for_use")
        self.assertEqual(state["executive_briefing"].next_action, "prepare_technical_outreach")
        self.assertNotIn("human_review_briefing", state)

        branches = state["branch_decisions"]
        self.assertEqual(
            tuple(branch.branch_name for branch in branches),
            ("ready_for_recommendation", "ready_for_briefing", "briefing_generated"),
        )
        self.assertTrue(all(branch.audit_reason for branch in branches))

    def test_missing_citation_fixture_requests_human_review(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        profile = _profile(startup_evidence)
        assessment = _assessment(_model_serving_gap(startup_evidence))
        retrieval_without_citation = NVIDIAKnowledgeRetrieval(
            schema_version="nvidia_knowledge.v1",
            run_id="run-issue-10",
            corpus_version="official-nvidia-fixture.v1",
            query="unrelated commercial billing workflow",
            results=(),
            documents=(),
        )
        workflow = build_local_downstream_workflow(
            DownstreamWorkflowRuntime(retrievals=(retrieval_without_citation,))
        )

        state = workflow.invoke(
            {
                "run_id": "run-issue-10",
                "profile": profile,
                "evidence_groups": (),
                "collection_quality": _collection_quality(),
                "assessment": assessment,
            }
        )

        self.assertEqual(state["next_action"], "human_review_requested")
        self.assertNotIn("executive_briefing", state)
        self.assertEqual(state["human_review_briefing"].schema_version, "human_review_briefing.v1")
        self.assertEqual(
            state["human_review_briefing"].hypothesis_recommendations,
            state["recommendation_set"].hypotheses,
        )
        self.assertIn(
            "recommendation_hypothesis_requires_human_review",
            state["human_review_briefing"].review_reasons,
        )
        self.assertEqual(
            tuple(branch.branch_name for branch in state["branch_decisions"]),
            ("ready_for_recommendation", "human_review_requested"),
        )

    def test_missing_retrieval_input_preserves_upstream_evidence(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        profile = _profile(startup_evidence)
        assessment = _assessment(_model_serving_gap(startup_evidence))
        workflow = build_local_downstream_workflow(DownstreamWorkflowRuntime())

        state = workflow.invoke(
            {
                "run_id": "run-issue-10",
                "profile": profile,
                "evidence_groups": (),
                "collection_quality": _collection_quality(),
                "assessment": assessment,
            }
        )

        self.assertEqual(state["next_action"], "human_review_requested")
        self.assertEqual(state["profile"], profile)
        self.assertEqual(state["assessment"].evidences, (startup_evidence,))
        self.assertEqual(state["human_review_briefing"].main_evidence, (startup_evidence,))

        error = state["errors"][0]
        self.assertEqual(error.step, "retrieve_nvidia_knowledge")
        self.assertEqual(error.error_type, "missing_nvidia_knowledge_input")
        self.assertTrue(error.audit_reason)
        self.assertIn(
            "human_review_requested",
            tuple(branch.branch_name for branch in state["branch_decisions"]),
        )

    def test_low_collection_quality_exposes_needs_more_collection_branch(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        profile = _profile(startup_evidence)
        workflow = build_local_downstream_workflow(
            DownstreamWorkflowRuntime(corpus=load_nvidia_knowledge_corpus(_fixture_path()))
        )

        state = workflow.invoke(
            {
                "run_id": "run-issue-10",
                "profile": profile,
                "evidence_groups": (),
                "collection_quality": _low_collection_quality(),
                "assessment": _assessment(_model_serving_gap(startup_evidence)),
            }
        )

        self.assertEqual(state["next_action"], "needs_more_collection_or_human_review")
        self.assertEqual(state["human_review_briefing"].status, "ready_for_human_review")
        needs_more_branch = state["branch_decisions"][0]
        self.assertEqual(needs_more_branch.branch_name, "needs_more_collection_or_human_review")
        self.assertIn("insufficient_public_evidence", needs_more_branch.audit_reason)
        self.assertTrue(all(branch.audit_reason for branch in state["branch_decisions"]))

    def test_storage_error_is_structured_without_discarding_generated_briefing(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        profile = _profile(startup_evidence)
        workflow = build_local_downstream_workflow(
            DownstreamWorkflowRuntime(
                corpus=load_nvidia_knowledge_corpus(_fixture_path()),
                artifact_store=FailingArtifactStore(),
            )
        )

        state = workflow.invoke(
            {
                "run_id": "run-issue-10",
                "profile": profile,
                "evidence_groups": (),
                "collection_quality": _collection_quality(),
                "assessment": _assessment(_model_serving_gap(startup_evidence)),
            }
        )

        self.assertEqual(state["next_action"], "briefing_generated")
        self.assertEqual(state["executive_briefing"].schema_version, "executive_briefing.v1")
        self.assertEqual(state["profile"], profile)
        error = state["errors"][0]
        self.assertEqual(error.step, "persist_downstream_artifacts")
        self.assertEqual(error.error_type, "RuntimeError")
        self.assertEqual(error.audit_reason, "storage_failed_structured_error")


class FailingArtifactStore:
    def save_downstream_state(self, state: dict[str, object]) -> None:
        raise RuntimeError("fixture storage failure")


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


def _model_serving_gap(evidence: FieldEvidence) -> TechnicalGap:
    return TechnicalGap(
        gap_type="model_serving",
        description="Needs lower latency inference and production model serving.",
        severity="high",
        confidence=0.86,
        evidences=(evidence,),
    )


def _assessment(gap: TechnicalGap) -> AINativeAssessment:
    return AINativeAssessment(
        schema_version="ai_native_assessment.v1",
        run_id="run-issue-10",
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


def _low_collection_quality() -> CollectionQualitySummary:
    return CollectionQualitySummary(
        candidate_count=1,
        official_site_found_count=0,
        official_site_found_rate=0.0,
        minimum_profile_complete_count=0,
        minimum_profile_complete_rate=0.0,
        average_evidences_per_startup=1.0,
        unknown_fields=(("technologies_used", 1),),
        source_success_rates=(),
        ready_for_evaluation=False,
        readiness_reasons=("insufficient_public_evidence",),
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
