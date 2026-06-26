"""Deterministic downstream quality metrics.

This module measures NVIDIA Knowledge retrieval and Recommendation outputs
against fixture expectations. It does not retrieve knowledge, build
recommendations, generate briefings, call providers, or touch persistence.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, fields, is_dataclass

from nvidia_startup_intel.normalization import normalize_text
from nvidia_startup_intel.nvidia_knowledge import NVIDIAKnowledgeRetrieval
from nvidia_startup_intel.nvidia_recommendation import NVIDIARecommendationSet
from nvidia_startup_intel.search_params import UNKNOWN


SCHEMA_VERSION = "downstream_metrics.v1"


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
    coverage: float
    cases: tuple[RetrievalMetricCase, ...]
    failure_reasons: tuple[str, ...]
    improvement_targets: tuple[str, ...]
    framework_change_assessment: tuple[str, ...]


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
        recall=_ratio(matched_count, expected_count),
        precision=_ratio(matched_count, retrieved_count),
        coverage=_ratio(covered_count, len(cases)),
        cases=cases,
        failure_reasons=_deduplicate(reason for case in cases for reason in case.failure_reasons),
        improvement_targets=_deduplicate(target for case in cases for target in case.improvement_targets),
        framework_change_assessment=_framework_change_assessment(cases),
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


def downstream_quality_report_to_dict(report: DownstreamQualityReport) -> dict[str, object]:
    """Convert a downstream metrics report to JSON-serializable dictionaries."""

    return _to_plain_data(report)


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
