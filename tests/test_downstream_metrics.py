from __future__ import annotations

import json
from pathlib import Path
import unittest

from nvidia_startup_intel.ai_native_assessment import AINativeAssessment, DiagnosticQuality, TechnicalGap
from nvidia_startup_intel.collection_quality import CollectionQualitySummary
from nvidia_startup_intel.downstream_metrics import (
    RetrievalMetricExpectation,
    build_downstream_quality_report,
    downstream_quality_report_to_dict,
)
from nvidia_startup_intel.nvidia_knowledge import (
    NVIDIAKnowledgeRetrieval,
    load_nvidia_knowledge_corpus,
    retrieve_nvidia_knowledge_by_gap,
)
from nvidia_startup_intel.nvidia_recommendation import build_nvidia_recommendations
from nvidia_startup_intel.search_params import UNKNOWN
from nvidia_startup_intel.startup_profile import ClaimSource, FieldEvidence, ProfileField, StartupProfile


class DownstreamMetricsTests(unittest.TestCase):
    def test_supported_downstream_path_reports_retrieval_and_recommendation_metrics(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao."
        )
        gap = _model_serving_gap(startup_evidence)
        corpus = load_nvidia_knowledge_corpus(_fixture_path())
        retrieval = retrieve_nvidia_knowledge_by_gap(
            corpus,
            run_id="run-metrics-001",
            gap_type=gap.gap_type,
            description=gap.description,
            startup_signals=("inference", "latency"),
            top_k=1,
        )
        recommendation_set = build_nvidia_recommendations(
            profile=_profile(startup_evidence),
            evidence_groups=(),
            collection_quality=_collection_quality(),
            assessment=_assessment(gap, run_id="run-metrics-001"),
            retrievals=(retrieval,),
        )

        report = build_downstream_quality_report(
            run_id="run-metrics-001",
            startup_identifier="VetAI",
            retrievals=(retrieval,),
            retrieval_expectations=(
                RetrievalMetricExpectation(
                    expectation_id="model-serving-nim",
                    target_type="technical_gap",
                    target="model_serving",
                    expected_chunk_ids=("nvidia-nim-developers:0",),
                ),
            ),
            recommendation_set=recommendation_set,
        )

        self.assertEqual(report.schema_version, "downstream_metrics.v1")
        self.assertEqual(report.run_id, "run-metrics-001")
        self.assertEqual(report.startup_identifier, "VetAI")
        self.assertEqual(report.corpus_version, "official-nvidia-fixture.v1")
        self.assertEqual(report.retrieval_metrics.retrieval_strategy, "bm25_lexical")
        self.assertEqual(report.retrieval_metrics.recall, 1.0)
        self.assertEqual(report.retrieval_metrics.precision, 1.0)
        self.assertEqual(report.retrieval_metrics.coverage, 1.0)
        self.assertEqual(report.retrieval_metrics.matched_expected_citation_count, 1)
        self.assertEqual(report.retrieval_metrics.failure_reasons, ())
        self.assertEqual(report.retrieval_metrics.improvement_targets, ())
        self.assertEqual(
            report.retrieval_metrics.framework_change_assessment,
            ("framework_change_not_indicated",),
        )
        self.assertEqual(report.recommendation_metrics.supported_recommendation_count, 1)
        self.assertEqual(report.recommendation_metrics.hypothesis_recommendation_count, 0)
        self.assertEqual(report.recommendation_metrics.blocked_recommendation_count, 0)
        self.assertEqual(report.recommendation_metrics.gaps_without_recommendation, ())
        self.assertEqual(report.recommendation_metrics.human_review_reason_counts, ())

        serialized = downstream_quality_report_to_dict(report)
        json.dumps(serialized)
        self.assertEqual(serialized["retrieval_metrics"]["cases"][0]["target"], "model_serving")
        self.assertEqual(
            serialized["recommendation_metrics"]["recommendations_with_official_nvidia_citation_count"],
            1,
        )

    def test_missing_citation_path_reports_retrieval_failure_and_human_review_metrics(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao."
        )
        gap = _model_serving_gap(startup_evidence)
        retrieval = NVIDIAKnowledgeRetrieval(
            schema_version="nvidia_knowledge.v1",
            run_id="run-metrics-002",
            corpus_version="official-nvidia-fixture.v1",
            query="model serving lower latency inference",
            results=(),
            documents=(),
        )
        recommendation_set = build_nvidia_recommendations(
            profile=_profile(startup_evidence),
            evidence_groups=(),
            collection_quality=_collection_quality(),
            assessment=_assessment(gap, run_id="run-metrics-002"),
            retrievals=(retrieval,),
        )

        report = build_downstream_quality_report(
            run_id="run-metrics-002",
            startup_identifier="VetAI",
            retrievals=(retrieval,),
            retrieval_expectations=(
                RetrievalMetricExpectation(
                    expectation_id="model-serving-nim",
                    target_type="technical_gap",
                    target="model_serving",
                    expected_chunk_ids=("nvidia-nim-developers:0",),
                ),
            ),
            recommendation_set=recommendation_set,
        )

        self.assertEqual(report.retrieval_metrics.retrieval_strategy, "no_results")
        self.assertEqual(report.retrieval_metrics.recall, 0.0)
        self.assertEqual(report.retrieval_metrics.precision, 0.0)
        self.assertEqual(report.retrieval_metrics.coverage, 0.0)
        self.assertEqual(
            report.retrieval_metrics.failure_reasons,
            ("no_retrieved_citation", "expected_citation_not_retrieved"),
        )
        self.assertEqual(
            report.retrieval_metrics.improvement_targets,
            ("expand_corpus_or_fix_query_for:model_serving",),
        )
        self.assertEqual(
            report.retrieval_metrics.framework_change_assessment,
            ("framework_change_not_indicated:expand_corpus_or_fix_query_first:model_serving",),
        )
        self.assertFalse(report.recommendation_metrics.ready_for_briefing)
        self.assertTrue(report.recommendation_metrics.human_review_requested)
        self.assertEqual(report.recommendation_metrics.hypothesis_recommendation_count, 1)
        self.assertEqual(report.recommendation_metrics.gaps_without_recommendation, ("model_serving",))
        self.assertEqual(report.recommendation_metrics.corpus_expansion_targets, ("model_serving",))
        self.assertEqual(
            report.recommendation_metrics.human_review_reason_counts,
            (
                ("recommendation_hypothesis_requires_human_review", 1),
                ("missing_official_nvidia_citation", 1),
            ),
        )


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


def _assessment(*gaps: TechnicalGap, run_id: str) -> AINativeAssessment:
    return AINativeAssessment(
        schema_version="ai_native_assessment.v1",
        run_id=run_id,
        company_name="VetAI",
        classification="ai_native",
        confidence=0.82,
        nvidia_opportunity_urgency="urgent",
        criteria_results=(),
        positive_signals=(),
        technical_gaps=gaps,
        wrapper_dependency_risks=(),
        insufficient_evidence_fields=(),
        evidences=tuple(evidence for gap in gaps for evidence in gap.evidences),
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
    observed_company = ProfileField(
        value="VetAI",
        claim_source=ClaimSource.OBSERVED,
        evidences=(evidence,),
    )
    unknown = ProfileField(value=UNKNOWN, claim_source=ClaimSource.UNKNOWN, evidences=())
    return StartupProfile(
        schema_version="startup_profile.v1",
        company_name=observed_company,
        official_site=ProfileField(
            value="https://vetai.example",
            claim_source=ClaimSource.OBSERVED,
            evidences=(evidence,),
        ),
        company_summary=unknown,
        sector=unknown,
        product=unknown,
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
