"""Deterministic downstream quality metrics.

This module measures NVIDIA Knowledge retrieval and Recommendation outputs
against fixture expectations. It does not retrieve knowledge, build
recommendations, generate briefings, call providers, or touch persistence.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, fields, is_dataclass

from nvidia_startup_intel.gap_space_assessment import GapSpaceAssessment, GapSpaceMapping
from nvidia_startup_intel.nvidia_reranking import NVIDIARerankResult
from nvidia_startup_intel.normalization import normalize_text
from nvidia_startup_intel.nvidia_knowledge import NVIDIAKnowledgeRetrieval, RetrievedNVIDIAKnowledge
from nvidia_startup_intel.nvidia_recommendation import NVIDIARecommendationSet
from nvidia_startup_intel.search_params import UNKNOWN


SCHEMA_VERSION = "downstream_metrics.v1"
GAP_SPACE_METRICS_SCHEMA_VERSION = "gap_space_metrics.v1"


@dataclass(frozen=True)
class RetrievalMetricExpectation:
    expectation_id: str
    target_type: str
    target: str
    expected_chunk_ids: tuple[str, ...] = ()
    expected_document_ids: tuple[str, ...] = ()
    retrieval_query_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class RetrievalMetricCase:
    expectation_id: str
    target_type: str
    target: str
    retrieval_strategy: str
    expected_chunk_ids: tuple[str, ...]
    expected_document_ids: tuple[str, ...]
    retrieved_chunk_ids: tuple[str, ...]
    retrieved_document_ids: tuple[str, ...]
    matched_expected_chunk_ids: tuple[str, ...]
    matched_expected_document_ids: tuple[str, ...]
    expected_citation_count: int
    retrieved_citation_count: int
    matched_expected_citation_count: int
    recall: float
    precision: float
    f1: float
    top_1_expected: bool
    covered: bool
    failure_reasons: tuple[str, ...]
    improvement_targets: tuple[str, ...]


@dataclass(frozen=True)
class DownstreamRetrievalMetrics:
    schema_version: str
    run_id: str
    corpus_version: str
    retrieval_strategy: str
    case_count: int
    covered_case_count: int
    expected_citation_count: int
    retrieved_citation_count: int
    matched_expected_citation_count: int
    recall: float
    precision: float
    f1: float
    coverage: float
    top_1_expected_count: int
    cases: tuple[RetrievalMetricCase, ...]
    failure_reasons: tuple[str, ...]
    improvement_targets: tuple[str, ...]
    framework_change_assessment: tuple[str, ...]


@dataclass(frozen=True)
class RetrievalStrategyQualityComparison:
    schema_version: str
    run_id: str
    corpus_version: str
    compared_retrieval_strategies: tuple[str, ...]
    metrics_by_strategy: tuple[DownstreamRetrievalMetrics, ...]
    best_f1_retrieval_strategy: str
    best_top_1_retrieval_strategy: str


@dataclass(frozen=True)
class DownstreamRecommendationMetrics:
    schema_version: str
    run_id: str
    startup_identifier: str
    corpus_version: str
    ready_for_briefing: bool
    human_review_requested: bool
    final_nvidia_opportunity_priority: str
    next_action: str
    supported_recommendation_count: int
    hypothesis_recommendation_count: int
    blocked_recommendation_count: int
    recommendations_with_official_nvidia_citation_count: int
    recommendations_with_startup_evidence_count: int
    gaps_without_recommendation: tuple[str, ...]
    blocked_briefing_count: int
    human_review_reason_counts: tuple[tuple[str, int], ...]
    corpus_expansion_targets: tuple[str, ...]
    evidence_collection_targets: tuple[str, ...]


@dataclass(frozen=True)
class DownstreamQualityReport:
    schema_version: str
    run_id: str
    startup_identifier: str
    corpus_version: str
    retrieval_metrics: DownstreamRetrievalMetrics
    recommendation_metrics: DownstreamRecommendationMetrics


@dataclass(frozen=True)
class GapSpaceMetrics:
    schema_version: str
    run_id: str
    startup_identifier: str
    corpus_version: str
    technical_gap_count: int
    taxonomy_supported_gap_count: int
    unsupported_gap_count: int
    commercial_opportunity_count: int
    taxonomy_supported_commercial_opportunity_count: int
    gap_coverage: float
    false_or_weak_gap_targets: tuple[str, ...]
    human_review_reason_counts: tuple[tuple[str, int], ...]
    evidence_collection_targets: tuple[str, ...]
    retrieval_query_count: int


@dataclass(frozen=True)
class RerankQualityComparison:
    schema_version: str
    run_id: str
    corpus_version: str
    baseline_retrieval_strategy: str
    rerank_ranking_strategy: str
    before: DownstreamRetrievalMetrics
    after: DownstreamRetrievalMetrics
    recall_delta: float
    precision_delta: float
    f1_delta: float
    coverage_delta: float
    before_top_1_expected_count: int
    after_top_1_expected_count: int
    top_1_expected_delta: int


def build_downstream_quality_report(
    *,
    run_id: str,
    startup_identifier: str,
    retrievals: tuple[NVIDIAKnowledgeRetrieval, ...],
    retrieval_expectations: tuple[RetrievalMetricExpectation, ...],
    recommendation_set: NVIDIARecommendationSet,
) -> DownstreamQualityReport:
    """Build a serializable metrics report for downstream quality checks."""

    corpus_version = _corpus_version(retrievals, recommendation_set)
    retrieval_metrics = summarize_downstream_retrieval_metrics(
        run_id=run_id,
        corpus_version=corpus_version,
        retrievals=retrievals,
        expectations=retrieval_expectations,
    )
    recommendation_metrics = summarize_downstream_recommendation_metrics(recommendation_set)
    return DownstreamQualityReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        startup_identifier=startup_identifier,
        corpus_version=corpus_version,
        retrieval_metrics=retrieval_metrics,
        recommendation_metrics=recommendation_metrics,
    )


def summarize_downstream_retrieval_metrics(
    *,
    run_id: str,
    corpus_version: str,
    retrievals: tuple[NVIDIAKnowledgeRetrieval, ...],
    expectations: tuple[RetrievalMetricExpectation, ...],
) -> DownstreamRetrievalMetrics:
    """Measure retrieval recall, precision, and coverage against fixture expectations."""

    cases = tuple(_retrieval_metric_case(expectation, retrievals) for expectation in expectations)
    expected_count = sum(case.expected_citation_count for case in cases)
    retrieved_count = sum(case.retrieved_citation_count for case in cases)
    matched_count = sum(case.matched_expected_citation_count for case in cases)
    covered_count = sum(1 for case in cases if case.covered)
    top_1_expected_count = sum(1 for case in cases if case.top_1_expected)
    recall = _ratio(matched_count, expected_count)
    precision = _ratio(matched_count, retrieved_count)
    return DownstreamRetrievalMetrics(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        corpus_version=corpus_version,
        retrieval_strategy=_aggregate_retrieval_strategy(cases),
        case_count=len(cases),
        covered_case_count=covered_count,
        expected_citation_count=expected_count,
        retrieved_citation_count=retrieved_count,
        matched_expected_citation_count=matched_count,
        recall=recall,
        precision=precision,
        f1=_f1(precision=precision, recall=recall),
        coverage=_ratio(covered_count, len(cases)),
        top_1_expected_count=top_1_expected_count,
        cases=cases,
        failure_reasons=_deduplicate(reason for case in cases for reason in case.failure_reasons),
        improvement_targets=_deduplicate(target for case in cases for target in case.improvement_targets),
        framework_change_assessment=_framework_change_assessment(cases),
    )


def compare_downstream_retrieval_strategy_metrics(
    *,
    run_id: str,
    corpus_version: str,
    retrievals_by_strategy: tuple[tuple[NVIDIAKnowledgeRetrieval, ...], ...],
    expectations: tuple[RetrievalMetricExpectation, ...],
) -> RetrievalStrategyQualityComparison:
    """Compare retrieval quality across independently executed retrieval strategies."""

    metrics_by_strategy = tuple(
        summarize_downstream_retrieval_metrics(
            run_id=run_id,
            corpus_version=corpus_version,
            retrievals=retrievals,
            expectations=expectations,
        )
        for retrievals in retrievals_by_strategy
    )
    return RetrievalStrategyQualityComparison(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        corpus_version=corpus_version,
        compared_retrieval_strategies=tuple(
            metrics.retrieval_strategy for metrics in metrics_by_strategy
        ),
        metrics_by_strategy=metrics_by_strategy,
        best_f1_retrieval_strategy=_best_retrieval_strategy_by_f1(metrics_by_strategy),
        best_top_1_retrieval_strategy=_best_retrieval_strategy_by_top_1(metrics_by_strategy),
    )


def summarize_downstream_recommendation_metrics(
    recommendation_set: NVIDIARecommendationSet,
) -> DownstreamRecommendationMetrics:
    """Copy Recommendation quality counters into a versioned downstream metrics payload."""

    metrics = recommendation_set.quality.metrics
    return DownstreamRecommendationMetrics(
        schema_version=SCHEMA_VERSION,
        run_id=recommendation_set.run_id,
        startup_identifier=recommendation_set.startup_identifier,
        corpus_version=recommendation_set.corpus_version,
        ready_for_briefing=recommendation_set.quality.ready_for_briefing,
        human_review_requested=recommendation_set.quality.human_review_requested,
        final_nvidia_opportunity_priority=recommendation_set.final_nvidia_opportunity_priority,
        next_action=recommendation_set.next_action,
        supported_recommendation_count=metrics.supported_recommendation_count,
        hypothesis_recommendation_count=metrics.hypothesis_recommendation_count,
        blocked_recommendation_count=metrics.blocked_recommendation_count,
        recommendations_with_official_nvidia_citation_count=(
            metrics.recommendations_with_official_nvidia_citation_count
        ),
        recommendations_with_startup_evidence_count=(
            metrics.recommendations_with_startup_evidence_count
        ),
        gaps_without_recommendation=metrics.gaps_without_recommendation,
        blocked_briefing_count=metrics.blocked_briefing_count,
        human_review_reason_counts=metrics.human_review_reason_counts,
        corpus_expansion_targets=metrics.corpus_expansion_targets,
        evidence_collection_targets=metrics.evidence_collection_targets,
    )


def summarize_gap_space_metrics(gap_space_assessment: GapSpaceAssessment) -> GapSpaceMetrics:
    """Summarize deterministic gap-space coverage and review targets."""

    mappings = gap_space_assessment.mappings
    commercial_mappings = gap_space_assessment.commercial_mappings
    taxonomy_supported_gap_count = sum(1 for mapping in mappings if mapping.taxonomy_targets)
    unsupported_gap_count = sum(1 for mapping in mappings if mapping.support_status == "unsupported")
    commercial_supported_count = sum(1 for mapping in commercial_mappings if mapping.taxonomy_targets)
    return GapSpaceMetrics(
        schema_version=GAP_SPACE_METRICS_SCHEMA_VERSION,
        run_id=gap_space_assessment.run_id,
        startup_identifier=gap_space_assessment.startup_identifier,
        corpus_version=gap_space_assessment.corpus_version,
        technical_gap_count=len(mappings),
        taxonomy_supported_gap_count=taxonomy_supported_gap_count,
        unsupported_gap_count=unsupported_gap_count,
        commercial_opportunity_count=len(commercial_mappings),
        taxonomy_supported_commercial_opportunity_count=commercial_supported_count,
        gap_coverage=_ratio(taxonomy_supported_gap_count, len(mappings)),
        false_or_weak_gap_targets=_false_or_weak_gap_targets(mappings),
        human_review_reason_counts=_reason_counts(_human_review_reasons(gap_space_assessment)),
        evidence_collection_targets=_gap_space_evidence_collection_targets(gap_space_assessment),
        retrieval_query_count=len(gap_space_assessment.retrieval_queries),
    )


def compare_rerank_retrieval_quality(
    *,
    run_id: str,
    baseline_retrievals: tuple[NVIDIAKnowledgeRetrieval, ...],
    rerank_results: tuple[NVIDIARerankResult, ...],
    expectations: tuple[RetrievalMetricExpectation, ...],
) -> RerankQualityComparison:
    """Compare retrieval metrics before and after reranking the supplied Top K."""

    corpus_version = _rerank_comparison_corpus_version(baseline_retrievals, rerank_results)
    after_retrievals = tuple(_retrieval_from_rerank_result(result) for result in rerank_results)
    before = summarize_downstream_retrieval_metrics(
        run_id=run_id,
        corpus_version=corpus_version,
        retrievals=baseline_retrievals,
        expectations=expectations,
    )
    after = summarize_downstream_retrieval_metrics(
        run_id=run_id,
        corpus_version=corpus_version,
        retrievals=after_retrievals,
        expectations=expectations,
    )
    before_top_1 = _top_1_expected_count(expectations, baseline_retrievals)
    after_top_1 = _top_1_expected_count(expectations, after_retrievals)
    return RerankQualityComparison(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        corpus_version=corpus_version,
        baseline_retrieval_strategy=before.retrieval_strategy,
        rerank_ranking_strategy=_aggregate_rerank_ranking_strategy(rerank_results),
        before=before,
        after=after,
        recall_delta=_metric_delta(after.recall, before.recall),
        precision_delta=_metric_delta(after.precision, before.precision),
        f1_delta=_metric_delta(after.f1, before.f1),
        coverage_delta=_metric_delta(after.coverage, before.coverage),
        before_top_1_expected_count=before_top_1,
        after_top_1_expected_count=after_top_1,
        top_1_expected_delta=after_top_1 - before_top_1,
    )


def downstream_quality_report_to_dict(report: DownstreamQualityReport) -> dict[str, object]:
    """Convert a downstream metrics report to JSON-serializable dictionaries."""

    return _to_plain_data(report)


def retrieval_strategy_comparison_to_dict(
    comparison: RetrievalStrategyQualityComparison,
) -> dict[str, object]:
    """Convert a retrieval strategy comparison to JSON-serializable dictionaries."""

    return _to_plain_data(comparison)


def rerank_quality_comparison_to_dict(comparison: RerankQualityComparison) -> dict[str, object]:
    """Convert a rerank quality comparison to JSON-serializable dictionaries."""

    return _to_plain_data(comparison)


def gap_space_metrics_to_dict(metrics: GapSpaceMetrics) -> dict[str, object]:
    """Convert gap-space metrics to JSON-serializable dictionaries."""

    return _to_plain_data(metrics)


def _retrieval_metric_case(
    expectation: RetrievalMetricExpectation,
    retrievals: tuple[NVIDIAKnowledgeRetrieval, ...],
) -> RetrievalMetricCase:
    retrieval = _matching_retrieval(expectation, retrievals)
    retrieved_chunk_ids = _retrieved_chunk_ids(retrieval)
    retrieved_document_ids = _retrieved_document_ids(retrieval)
    matched_chunk_ids = tuple(
        chunk_id for chunk_id in expectation.expected_chunk_ids if chunk_id in retrieved_chunk_ids
    )
    matched_document_ids = tuple(
        document_id
        for document_id in expectation.expected_document_ids
        if document_id in retrieved_document_ids
    )
    expected_count = len(expectation.expected_chunk_ids) + len(expectation.expected_document_ids)
    retrieved_count = len(retrieved_chunk_ids)
    matched_count = len(matched_chunk_ids) + len(matched_document_ids)
    recall = _ratio(matched_count, expected_count)
    precision = _ratio(matched_count, retrieved_count)
    top_1_expected = _top_1_matches_expectation(expectation, retrieval)
    covered = expected_count > 0 and matched_count == expected_count
    failure_reasons = _case_failure_reasons(
        retrieval=retrieval,
        recall=recall,
        precision=precision,
        expected_count=expected_count,
        retrieved_count=retrieved_count,
    )
    return RetrievalMetricCase(
        expectation_id=expectation.expectation_id,
        target_type=expectation.target_type,
        target=expectation.target,
        retrieval_strategy=_retrieval_strategy(retrieval),
        expected_chunk_ids=expectation.expected_chunk_ids,
        expected_document_ids=expectation.expected_document_ids,
        retrieved_chunk_ids=retrieved_chunk_ids,
        retrieved_document_ids=retrieved_document_ids,
        matched_expected_chunk_ids=matched_chunk_ids,
        matched_expected_document_ids=matched_document_ids,
        expected_citation_count=expected_count,
        retrieved_citation_count=retrieved_count,
        matched_expected_citation_count=matched_count,
        recall=recall,
        precision=precision,
        f1=_f1(precision=precision, recall=recall),
        top_1_expected=top_1_expected,
        covered=covered,
        failure_reasons=failure_reasons,
        improvement_targets=_case_improvement_targets(
            expectation.target,
            failure_reasons=failure_reasons,
            retrieved_count=retrieved_count,
        ),
    )


def _matching_retrieval(
    expectation: RetrievalMetricExpectation,
    retrievals: tuple[NVIDIAKnowledgeRetrieval, ...],
) -> NVIDIAKnowledgeRetrieval | None:
    for retrieval in retrievals:
        if _retrieval_matches_query_terms(expectation, retrieval):
            return retrieval
    for retrieval in retrievals:
        if _retrieval_matches_target(expectation, retrieval):
            return retrieval
    if len(retrievals) == 1:
        return retrievals[0]
    return None


def _retrieval_from_rerank_result(result: NVIDIARerankResult) -> NVIDIAKnowledgeRetrieval:
    return NVIDIAKnowledgeRetrieval(
        schema_version="nvidia_knowledge.v1",
        run_id=result.run_id,
        corpus_version=result.corpus_version,
        query=result.query,
        results=tuple(
            RetrievedNVIDIAKnowledge(
                chunk=item.chunk,
                citation=item.citation,
                score=item.original_score,
                retrieval_strategy=result.ranking_strategy,
                rationale=item.rerank_rationale,
                rank=item.rerank_rank,
                bm25_score=item.original_bm25_score,
                vector_score=item.original_vector_score,
                hybrid_score=item.original_hybrid_score,
            )
            for item in result.results
        ),
        documents=(),
    )


def _top_1_expected_count(
    expectations: tuple[RetrievalMetricExpectation, ...],
    retrievals: tuple[NVIDIAKnowledgeRetrieval, ...],
) -> int:
    return sum(
        1
        for expectation in expectations
        if _top_1_matches_expectation(expectation, _matching_retrieval(expectation, retrievals))
    )


def _top_1_matches_expectation(
    expectation: RetrievalMetricExpectation,
    retrieval: NVIDIAKnowledgeRetrieval | None,
) -> bool:
    if retrieval is None or not retrieval.results:
        return False
    top_result = retrieval.results[0]
    return (
        top_result.chunk.chunk_id in expectation.expected_chunk_ids
        or top_result.citation.document_id in expectation.expected_document_ids
    )


def _retrieval_matches_query_terms(
    expectation: RetrievalMetricExpectation,
    retrieval: NVIDIAKnowledgeRetrieval,
) -> bool:
    if not expectation.retrieval_query_terms:
        return False
    query = normalize_text(retrieval.query)
    return all(normalize_text(term) in query for term in expectation.retrieval_query_terms)


def _retrieval_matches_target(
    expectation: RetrievalMetricExpectation,
    retrieval: NVIDIAKnowledgeRetrieval,
) -> bool:
    normalized_target = normalize_text(expectation.target.replace("_", " "))
    if normalized_target and normalized_target in normalize_text(retrieval.query):
        return True
    return any(
        result.chunk.topic == expectation.target
        or result.chunk.chunk_id in expectation.expected_chunk_ids
        or result.citation.document_id in expectation.expected_document_ids
        for result in retrieval.results
    )


def _retrieved_chunk_ids(retrieval: NVIDIAKnowledgeRetrieval | None) -> tuple[str, ...]:
    if retrieval is None:
        return ()
    return tuple(result.chunk.chunk_id for result in retrieval.results)


def _retrieved_document_ids(retrieval: NVIDIAKnowledgeRetrieval | None) -> tuple[str, ...]:
    if retrieval is None:
        return ()
    return tuple(result.citation.document_id for result in retrieval.results)


def _case_failure_reasons(
    *,
    retrieval: NVIDIAKnowledgeRetrieval | None,
    recall: float,
    precision: float,
    expected_count: int,
    retrieved_count: int,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if retrieval is None:
        reasons.append("no_matching_retrieval")
    if expected_count > 0 and retrieved_count == 0:
        reasons.append("no_retrieved_citation")
    if expected_count > 0 and recall < 1.0:
        reasons.append("expected_citation_not_retrieved")
    if retrieved_count > 0 and precision < 1.0:
        reasons.append("unexpected_retrieved_citation")
    return tuple(reasons)


def _case_improvement_targets(
    target: str,
    *,
    failure_reasons: tuple[str, ...],
    retrieved_count: int,
) -> tuple[str, ...]:
    if not failure_reasons:
        return ()
    if "no_matching_retrieval" in failure_reasons:
        return (f"add_retrieval_fixture_for:{target}",)
    if "no_retrieved_citation" in failure_reasons:
        return (f"expand_corpus_or_fix_query_for:{target}",)
    if "expected_citation_not_retrieved" in failure_reasons and retrieved_count > 0:
        return (f"inspect_query_or_ranking_for:{target}",)
    return (f"measure_before_framework_change_for:{target}",)


def _false_or_weak_gap_targets(mappings: tuple[GapSpaceMapping, ...]) -> tuple[str, ...]:
    weak_reasons = {
        "unsupported_gap_type",
        "missing_observed_gap_evidence",
        "low_gap_confidence",
        "upstream_gap_is_hypothesis",
    }
    return _deduplicate(
        mapping.gap_type
        for mapping in mappings
        if any(reason in weak_reasons for reason in mapping.review_reasons)
    )


def _human_review_reasons(gap_space_assessment: GapSpaceAssessment) -> tuple[str, ...]:
    if not gap_space_assessment.quality.requires_human_review:
        return ()
    return tuple(
        reason
        for reason in gap_space_assessment.quality.reasons
        if reason != "gap_space_ready_for_recommendation"
    )


def _reason_counts(reasons: tuple[str, ...]) -> tuple[tuple[str, int], ...]:
    counts = Counter(reasons)
    return tuple((reason, counts[reason]) for reason in dict.fromkeys(reasons))


def _gap_space_evidence_collection_targets(
    gap_space_assessment: GapSpaceAssessment,
) -> tuple[str, ...]:
    targets: list[str] = []
    for reason in gap_space_assessment.quality.reasons:
        if reason.startswith("unknown_field:"):
            targets.append(reason.split(":", maxsplit=1)[1])
        elif reason == "collection_quality_not_ready":
            targets.append("collection_quality")

    for mapping in gap_space_assessment.mappings:
        if "missing_observed_gap_evidence" in mapping.review_reasons:
            targets.append(mapping.gap_type)
    for mapping in gap_space_assessment.commercial_mappings:
        if "missing_observed_opportunity_evidence" in mapping.review_reasons:
            targets.append(mapping.opportunity_type)
    return _deduplicate(targets)


def _framework_change_assessment(cases: tuple[RetrievalMetricCase, ...]) -> tuple[str, ...]:
    if not cases or not any(case.failure_reasons for case in cases):
        return ("framework_change_not_indicated",)

    assessments: list[str] = []
    for case in cases:
        if not case.failure_reasons:
            continue
        if "no_matching_retrieval" in case.failure_reasons:
            assessments.append(f"framework_change_not_indicated:add_fixture_first:{case.target}")
            continue
        if "no_retrieved_citation" in case.failure_reasons:
            assessments.append(
                f"framework_change_not_indicated:expand_corpus_or_fix_query_first:{case.target}"
            )
            continue
        assessments.append(f"framework_change_candidate_after_query_review:{case.target}")
    return _deduplicate(assessments)


def _retrieval_strategy(retrieval: NVIDIAKnowledgeRetrieval | None) -> str:
    if retrieval is None:
        return UNKNOWN
    if not retrieval.results:
        return "no_results"
    return retrieval.results[0].retrieval_strategy


def _aggregate_retrieval_strategy(cases: tuple[RetrievalMetricCase, ...]) -> str:
    strategies = tuple(dict.fromkeys(case.retrieval_strategy for case in cases))
    if not strategies:
        return UNKNOWN
    if len(strategies) == 1:
        return strategies[0]
    return "mixed"


def _aggregate_rerank_ranking_strategy(rerank_results: tuple[NVIDIARerankResult, ...]) -> str:
    strategies = tuple(dict.fromkeys(result.ranking_strategy for result in rerank_results))
    if not strategies:
        return UNKNOWN
    if len(strategies) == 1:
        return strategies[0]
    return "mixed"


def _best_retrieval_strategy_by_f1(metrics_by_strategy: tuple[DownstreamRetrievalMetrics, ...]) -> str:
    if not metrics_by_strategy:
        return UNKNOWN
    return max(
        enumerate(metrics_by_strategy),
        key=lambda item: (
            item[1].f1,
            item[1].coverage,
            item[1].precision,
            item[1].top_1_expected_count,
            -item[0],
        ),
    )[1].retrieval_strategy


def _best_retrieval_strategy_by_top_1(
    metrics_by_strategy: tuple[DownstreamRetrievalMetrics, ...],
) -> str:
    if not metrics_by_strategy:
        return UNKNOWN
    return max(
        enumerate(metrics_by_strategy),
        key=lambda item: (
            item[1].top_1_expected_count,
            item[1].f1,
            item[1].coverage,
            item[1].precision,
            -item[0],
        ),
    )[1].retrieval_strategy


def _rerank_comparison_corpus_version(
    baseline_retrievals: tuple[NVIDIAKnowledgeRetrieval, ...],
    rerank_results: tuple[NVIDIARerankResult, ...],
) -> str:
    if baseline_retrievals:
        return baseline_retrievals[0].corpus_version
    if rerank_results:
        return rerank_results[0].corpus_version
    return UNKNOWN


def _corpus_version(
    retrievals: tuple[NVIDIAKnowledgeRetrieval, ...],
    recommendation_set: NVIDIARecommendationSet,
) -> str:
    if retrievals:
        return retrievals[0].corpus_version
    return recommendation_set.corpus_version


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 6)


def _f1(*, precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return round((2 * precision * recall) / (precision + recall), 6)


def _metric_delta(after: float, before: float) -> float:
    return round(after - before, 6)


def _deduplicate(values: Iterable[object]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values))


def _to_plain_data(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _to_plain_data(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {key: _to_plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain_data(item) for item in value]
    return value
