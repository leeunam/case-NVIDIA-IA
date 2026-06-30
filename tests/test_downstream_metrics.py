from __future__ import annotations

import json
from pathlib import Path
import unittest

from nvidia_startup_intel.ai_native_assessment import AINativeAssessment, DiagnosticQuality, TechnicalGap
from nvidia_startup_intel.collection_quality import CollectionQualitySummary
from nvidia_startup_intel.downstream_metrics import (
    RetrievalMetricExpectation,
    build_downstream_quality_report,
    compare_downstream_retrieval_strategy_metrics,
    downstream_quality_report_to_dict,
    gap_space_metrics_to_dict,
    retrieval_strategy_comparison_to_dict,
    summarize_gap_space_metrics,
)
from nvidia_startup_intel.gap_space_assessment import assess_gap_space
from nvidia_startup_intel.nvidia_embeddings import (
    DeterministicFakeEmbeddingClient,
    build_nvidia_embedding_index,
    retrieve_nvidia_knowledge_by_vector,
    retrieve_nvidia_knowledge_hybrid,
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
        self.assertEqual(report.retrieval_metrics.f1, 1.0)
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
        self.assertEqual(serialized["retrieval_metrics"]["cases"][0]["f1"], 1.0)
        self.assertEqual(serialized["retrieval_metrics"]["f1"], 1.0)
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
        self.assertEqual(report.retrieval_metrics.f1, 0.0)
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

    def test_retrieval_metrics_report_f1_when_precision_and_recall_diverge(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao."
        )
        gap = _model_serving_gap(startup_evidence)
        corpus = load_nvidia_knowledge_corpus(_fixture_path())
        retrieval = retrieve_nvidia_knowledge_by_gap(
            corpus,
            run_id="run-metrics-003",
            gap_type=gap.gap_type,
            description=gap.description,
            startup_signals=("inference", "latency"),
            top_k=2,
        )
        recommendation_set = build_nvidia_recommendations(
            profile=_profile(startup_evidence),
            evidence_groups=(),
            collection_quality=_collection_quality(),
            assessment=_assessment(gap, run_id="run-metrics-003"),
            retrievals=(retrieval,),
        )

        report = build_downstream_quality_report(
            run_id="run-metrics-003",
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

        self.assertEqual(report.retrieval_metrics.recall, 1.0)
        self.assertEqual(report.retrieval_metrics.precision, 0.5)
        self.assertEqual(report.retrieval_metrics.f1, 0.666667)
        self.assertEqual(report.retrieval_metrics.cases[0].f1, 0.666667)

    def test_hybrid_retrieval_metrics_report_quality_and_improvement_targets(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao."
        )
        gap = _model_serving_gap(startup_evidence)
        corpus = load_nvidia_knowledge_corpus(_fixture_path())
        embedding_client = DeterministicFakeEmbeddingClient(dimension=6)
        embedding_index = build_nvidia_embedding_index(corpus, embedding_client)
        retrieval = retrieve_nvidia_knowledge_hybrid(
            corpus,
            embedding_index,
            embedding_client,
            run_id="run-metrics-004",
            gap_type=gap.gap_type,
            description=gap.description,
            startup_signals=("inference", "latency"),
            lexical_top_k=2,
            vector_top_k=2,
            top_k=2,
        )
        recommendation_set = build_nvidia_recommendations(
            profile=_profile(startup_evidence),
            evidence_groups=(),
            collection_quality=_collection_quality(),
            assessment=_assessment(gap, run_id="run-metrics-004"),
            retrievals=(retrieval,),
        )

        report = build_downstream_quality_report(
            run_id="run-metrics-004",
            startup_identifier="VetAI",
            retrievals=(retrieval,),
            retrieval_expectations=(
                RetrievalMetricExpectation(
                    expectation_id="hybrid-model-serving-nim",
                    target_type="technical_gap",
                    target="model_serving",
                    expected_chunk_ids=("nvidia-nim-developers:0",),
                ),
            ),
            recommendation_set=recommendation_set,
        )

        self.assertEqual(report.retrieval_metrics.retrieval_strategy, "hybrid_bm25_vector")
        self.assertEqual(report.retrieval_metrics.recall, 1.0)
        self.assertEqual(report.retrieval_metrics.precision, 0.5)
        self.assertEqual(report.retrieval_metrics.f1, 0.666667)
        self.assertEqual(report.retrieval_metrics.coverage, 1.0)
        self.assertEqual(report.retrieval_metrics.failure_reasons, ("unexpected_retrieved_citation",))
        self.assertEqual(
            report.retrieval_metrics.improvement_targets,
            ("measure_before_framework_change_for:model_serving",),
        )
        self.assertEqual(
            report.retrieval_metrics.framework_change_assessment,
            ("framework_change_candidate_after_query_review:model_serving",),
        )

    def test_retrieval_strategy_comparison_reports_top_1_for_bm25_vector_hybrid_and_no_results(
        self,
    ) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao."
        )
        gap = _model_serving_gap(startup_evidence)
        corpus = load_nvidia_knowledge_corpus(_fixture_path())
        embedding_client = DeterministicFakeEmbeddingClient(dimension=6)
        embedding_index = build_nvidia_embedding_index(corpus, embedding_client)
        bm25_retrieval = retrieve_nvidia_knowledge_by_gap(
            corpus,
            run_id="run-metrics-005",
            gap_type=gap.gap_type,
            description=gap.description,
            startup_signals=("inference", "latency"),
            top_k=2,
        )
        vector_retrieval = retrieve_nvidia_knowledge_by_vector(
            corpus,
            embedding_index,
            embedding_client,
            run_id="run-metrics-005",
            gap_type=gap.gap_type,
            description=gap.description,
            startup_signals=("inference", "latency"),
            top_k=2,
        )
        hybrid_retrieval = retrieve_nvidia_knowledge_hybrid(
            corpus,
            embedding_index,
            embedding_client,
            run_id="run-metrics-005",
            gap_type=gap.gap_type,
            description=gap.description,
            startup_signals=("inference", "latency"),
            lexical_top_k=2,
            vector_top_k=2,
            top_k=2,
        )
        no_result_retrieval = NVIDIAKnowledgeRetrieval(
            schema_version="nvidia_knowledge.v1",
            run_id="run-metrics-005",
            corpus_version=corpus.corpus_version,
            query="model serving lower latency inference",
            results=(),
            documents=(),
        )

        comparison = compare_downstream_retrieval_strategy_metrics(
            run_id="run-metrics-005",
            corpus_version=corpus.corpus_version,
            retrievals_by_strategy=(
                (bm25_retrieval,),
                (vector_retrieval,),
                (hybrid_retrieval,),
                (no_result_retrieval,),
            ),
            expectations=(
                RetrievalMetricExpectation(
                    expectation_id="model-serving-nim",
                    target_type="technical_gap",
                    target="model_serving",
                    expected_chunk_ids=("nvidia-nim-developers:0",),
                ),
            ),
        )

        self.assertEqual(comparison.schema_version, "downstream_metrics.v1")
        self.assertEqual(
            comparison.compared_retrieval_strategies,
            ("bm25_lexical", "vector_semantic", "hybrid_bm25_vector", "no_results"),
        )
        metrics_by_strategy = {
            metrics.retrieval_strategy: metrics for metrics in comparison.metrics_by_strategy
        }
        self.assertEqual(metrics_by_strategy["bm25_lexical"].precision, 0.5)
        self.assertEqual(metrics_by_strategy["bm25_lexical"].recall, 1.0)
        self.assertEqual(metrics_by_strategy["bm25_lexical"].f1, 0.666667)
        self.assertEqual(metrics_by_strategy["bm25_lexical"].coverage, 1.0)
        self.assertEqual(metrics_by_strategy["bm25_lexical"].top_1_expected_count, 1)
        self.assertTrue(metrics_by_strategy["bm25_lexical"].cases[0].top_1_expected)

        self.assertEqual(metrics_by_strategy["vector_semantic"].top_1_expected_count, 0)
        self.assertFalse(metrics_by_strategy["vector_semantic"].cases[0].top_1_expected)
        self.assertEqual(metrics_by_strategy["hybrid_bm25_vector"].top_1_expected_count, 1)
        self.assertEqual(metrics_by_strategy["no_results"].recall, 0.0)
        self.assertEqual(metrics_by_strategy["no_results"].precision, 0.0)
        self.assertEqual(metrics_by_strategy["no_results"].coverage, 0.0)
        self.assertEqual(metrics_by_strategy["no_results"].top_1_expected_count, 0)
        self.assertEqual(comparison.best_top_1_retrieval_strategy, "bm25_lexical")

        serialized = retrieval_strategy_comparison_to_dict(comparison)
        json.dumps(serialized)
        self.assertEqual(serialized["metrics_by_strategy"][1]["cases"][0]["top_1_expected"], False)

    def test_gap_space_metrics_report_coverage_weak_targets_and_collection_targets(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao."
        )
        unsupported_evidence = _startup_evidence(
            snippet="A VetAI talvez precise automatizar billing quantico para clientes enterprise."
        )
        supported_gap = _model_serving_gap(startup_evidence)
        weak_gap = TechnicalGap(
            gap_type="quantum_billing",
            description="May need quantum billing workflow acceleration.",
            severity="medium",
            confidence=0.42,
            evidences=(unsupported_evidence,),
        )
        corpus = load_nvidia_knowledge_corpus(_fixture_path())
        gap_space = assess_gap_space(
            profile=_profile(startup_evidence),
            collection_quality=_collection_quality(unknown_fields=(("technologies_used", 1),)),
            assessment=_assessment(supported_gap, weak_gap, run_id="run-metrics-006"),
            evidence_groups=(),
            corpus=corpus,
            run_id="run-metrics-006",
        )

        metrics = summarize_gap_space_metrics(gap_space)

        self.assertEqual(metrics.schema_version, "gap_space_metrics.v1")
        self.assertEqual(metrics.run_id, "run-metrics-006")
        self.assertEqual(metrics.technical_gap_count, 2)
        self.assertEqual(metrics.taxonomy_supported_gap_count, 1)
        self.assertEqual(metrics.unsupported_gap_count, 1)
        self.assertEqual(metrics.gap_coverage, 0.5)
        self.assertEqual(metrics.false_or_weak_gap_targets, ("quantum_billing",))
        self.assertIn(("unsupported_gap_type", 1), metrics.human_review_reason_counts)
        self.assertIn(("low_gap_confidence", 1), metrics.human_review_reason_counts)
        self.assertIn(("unknown_field:technologies_used", 1), metrics.human_review_reason_counts)
        self.assertEqual(metrics.evidence_collection_targets, ("technologies_used",))
        self.assertEqual(metrics.retrieval_query_count, 2)

        serialized = gap_space_metrics_to_dict(metrics)
        json.dumps(serialized)
        self.assertEqual(serialized["gap_coverage"], 0.5)


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


def _collection_quality(
    *,
    unknown_fields: tuple[tuple[str, int], ...] = (),
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
