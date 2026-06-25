"""Deterministic NVIDIA recommendation contracts.

This module consumes upstream assessment artifacts and citable NVIDIA
Knowledge retrievals. It does not discover, scrape, extract, classify, retrieve
knowledge, call LLMs, or touch the network.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
import re
from urllib.parse import urlparse

from nvidia_startup_intel.ai_native_assessment import AINativeAssessment, TechnicalGap
from nvidia_startup_intel.collection_quality import CollectionQualitySummary
from nvidia_startup_intel.evidence import FieldEvidenceGroup
from nvidia_startup_intel.normalization import normalize_text
from nvidia_startup_intel.nvidia_knowledge import (
    NVIDIACitation,
    NVIDIAKnowledgeRetrieval,
    RetrievedNVIDIAKnowledge,
    summarize_nvidia_retrieval_quality,
)
from nvidia_startup_intel.search_params import UNKNOWN
from nvidia_startup_intel.startup_profile import FieldEvidence, StartupProfile


SCHEMA_VERSION = "nvidia_recommendation.v1"
MIN_SUPPORTED_GAP_CONFIDENCE = 0.60
CLOSE_ALTERNATIVE_RELATIVE_DELTA = 0.15
SUPPORTED_TECHNICAL_GAP_TYPES = frozenset(
    {
        "model_serving",
        "llm_customization",
        "data_acceleration",
        "computer_vision",
    }
)


@dataclass(frozen=True)
class RecommendationQuality:
    ready_for_briefing: bool
    human_review_requested: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class NVIDIATechnicalRecommendation:
    recommendation_id: str
    recommendation_type: str
    state: str
    rank: int
    gap: TechnicalGap
    nvidia_technology: str
    technical_rationale: str
    commercial_rationale: str
    complexity: str
    nvidia_opportunity_priority: str
    next_action: str
    startup_evidences: tuple[FieldEvidence, ...]
    nvidia_citations: tuple[NVIDIACitation, ...]
    selection_reasons: tuple[str, ...]


@dataclass(frozen=True)
class NVIDIARecommendationSet:
    schema_version: str
    run_id: str
    startup_identifier: str
    corpus_version: str
    technical_recommendations: tuple[NVIDIATechnicalRecommendation, ...]
    program_recommendations: tuple[object, ...]
    top_recommendations_by_gap: tuple[NVIDIATechnicalRecommendation, ...]
    alternatives: tuple[NVIDIATechnicalRecommendation, ...]
    hypotheses: tuple[NVIDIATechnicalRecommendation, ...]
    blocked_recommendations: tuple[NVIDIATechnicalRecommendation, ...]
    final_nvidia_opportunity_priority: str
    next_action: str
    quality: RecommendationQuality
    audit_reasons: tuple[str, ...] = field(default_factory=tuple)


def build_nvidia_recommendations(
    *,
    profile: StartupProfile,
    evidence_groups: tuple[FieldEvidenceGroup, ...],
    collection_quality: CollectionQualitySummary,
    assessment: AINativeAssessment,
    retrievals: tuple[NVIDIAKnowledgeRetrieval, ...],
) -> NVIDIARecommendationSet:
    """Build a recommendation set from upstream diagnosis and NVIDIA citations."""

    startup_identifier = _startup_identifier(profile, assessment)
    blocked_by_context = _blocking_context_reasons(
        collection_quality=collection_quality,
        assessment=assessment,
        evidence_groups=evidence_groups,
    )
    supported_candidates: list[tuple[float, NVIDIATechnicalRecommendation]] = []
    alternative_candidates: list[tuple[float, NVIDIATechnicalRecommendation]] = []
    hypotheses: list[NVIDIATechnicalRecommendation] = []
    blocked: list[NVIDIATechnicalRecommendation] = []

    for gap in assessment.technical_gaps:
        if gap.gap_type == UNKNOWN:
            continue

        retrieval = _retrieval_for_gap(gap, retrievals)
        startup_evidences = tuple(gap.evidences)
        if blocked_by_context or not startup_evidences:
            blocked.append(
                _blocked_recommendation(
                    run_id=assessment.run_id,
                    startup_identifier=startup_identifier,
                    gap=gap,
                    retrieval=retrieval,
                    startup_evidences=startup_evidences,
                    reasons=blocked_by_context
                    or ("missing_startup_gap_evidence",),
                )
            )
            continue

        if gap.gap_type not in SUPPORTED_TECHNICAL_GAP_TYPES:
            hypotheses.append(
                _hypothesis_recommendation(
                    run_id=assessment.run_id,
                    startup_identifier=startup_identifier,
                    gap=gap,
                    retrieval=retrieval,
                    startup_evidences=startup_evidences,
                    reasons=("gap_type_not_covered_by_recommendation_rules",),
                )
            )
            continue

        if retrieval is None or not summarize_nvidia_retrieval_quality(retrieval).has_sufficient_citation:
            hypotheses.append(
                _hypothesis_recommendation(
                    run_id=assessment.run_id,
                    startup_identifier=startup_identifier,
                    gap=gap,
                    retrieval=retrieval,
                    startup_evidences=startup_evidences,
                )
            )
            continue

        if gap.confidence < MIN_SUPPORTED_GAP_CONFIDENCE:
            hypotheses.append(
                _hypothesis_recommendation(
                    run_id=assessment.run_id,
                    startup_identifier=startup_identifier,
                    gap=gap,
                    retrieval=retrieval,
                    startup_evidences=startup_evidences,
                    reasons=("low_gap_confidence",),
                )
            )
            continue

        ranked_results = _rank_results_for_gap(
            gap=gap,
            retrieval=retrieval,
            assessment_confidence=assessment.confidence,
        )
        recommendation = _supported_recommendation(
            run_id=assessment.run_id,
            startup_identifier=startup_identifier,
            gap=gap,
            result=ranked_results[0],
            startup_evidences=startup_evidences,
            rank=1,
        )
        supported_candidates.append(
            (
                _recommendation_score(
                    gap=gap,
                    result=ranked_results[0],
                    assessment_confidence=assessment.confidence,
                ),
                recommendation,
            )
        )
        for alternative_rank, alternative_result in enumerate(ranked_results[1:], start=2):
            if not _is_close_alternative(ranked_results[0], alternative_result):
                continue
            alternative = _supported_recommendation(
                run_id=assessment.run_id,
                startup_identifier=startup_identifier,
                gap=gap,
                result=alternative_result,
                startup_evidences=startup_evidences,
                rank=alternative_rank,
                extra_selection_reasons=("close_alternative_for_gap",),
            )
            alternative_candidates.append(
                (
                    _recommendation_score(
                        gap=gap,
                        result=alternative_result,
                        assessment_confidence=assessment.confidence,
                    ),
                    alternative,
                )
            )

    supported = _rank_supported_recommendations(supported_candidates)
    alternatives = tuple(_rank_supported_recommendations(alternative_candidates))
    top_recommendations = _top_recommendations_by_gap(tuple(supported))
    final_priority = _final_priority(tuple(supported), tuple(hypotheses), tuple(blocked))
    next_action = _next_action(final_priority, tuple(supported), tuple(hypotheses), tuple(blocked))
    quality = _recommendation_quality(tuple(supported), tuple(hypotheses), tuple(blocked))

    return NVIDIARecommendationSet(
        schema_version=SCHEMA_VERSION,
        run_id=assessment.run_id,
        startup_identifier=startup_identifier,
        corpus_version=_corpus_version(retrievals),
        technical_recommendations=tuple(supported),
        program_recommendations=(),
        top_recommendations_by_gap=top_recommendations,
        alternatives=alternatives,
        hypotheses=tuple(hypotheses),
        blocked_recommendations=tuple(blocked),
        final_nvidia_opportunity_priority=final_priority,
        next_action=next_action,
        quality=quality,
        audit_reasons=quality.reasons,
    )


def nvidia_recommendation_set_to_dict(
    recommendation_set: NVIDIARecommendationSet,
) -> dict[str, object]:
    """Convert a recommendation set to a JSON-serializable dictionary."""

    return _to_plain_data(recommendation_set)


def _supported_recommendation(
    *,
    run_id: str,
    startup_identifier: str,
    gap: TechnicalGap,
    result: RetrievedNVIDIAKnowledge,
    startup_evidences: tuple[FieldEvidence, ...],
    rank: int,
    extra_selection_reasons: tuple[str, ...] = (),
) -> NVIDIATechnicalRecommendation:
    citation = result.citation
    priority = _supported_priority(gap)
    return NVIDIATechnicalRecommendation(
        recommendation_id=_recommendation_id(run_id, startup_identifier, gap, citation.document_id),
        recommendation_type="technical",
        state="supported",
        rank=rank,
        gap=gap,
        nvidia_technology=citation.document_title,
        technical_rationale=(
            f"{citation.document_title} is cited for the {gap.gap_type} gap: {gap.description}"
        ),
        commercial_rationale=(
            f"Official NVIDIA fit is supported for a {gap.severity}-severity {gap.gap_type} gap."
        ),
        complexity=_complexity(gap),
        nvidia_opportunity_priority=priority,
        next_action="prepare_technical_outreach",
        startup_evidences=startup_evidences,
        nvidia_citations=(citation,),
        selection_reasons=(
            f"matched_gap_type:{gap.gap_type}",
            "has_startup_gap_evidence",
            "has_official_nvidia_citation",
            "highest_retrieval_score_for_gap",
            *extra_selection_reasons,
        ),
    )


def _hypothesis_recommendation(
    *,
    run_id: str,
    startup_identifier: str,
    gap: TechnicalGap,
    retrieval: NVIDIAKnowledgeRetrieval | None,
    startup_evidences: tuple[FieldEvidence, ...],
    reasons: tuple[str, ...] = ("missing_official_nvidia_citation",),
) -> NVIDIATechnicalRecommendation:
    result = _top_result(retrieval)
    citations = (result.citation,) if result is not None else ()
    technology = result.citation.document_title if result is not None else UNKNOWN
    return NVIDIATechnicalRecommendation(
        recommendation_id=_recommendation_id(run_id, startup_identifier, gap, technology),
        recommendation_type="technical",
        state="hypothesis",
        rank=0,
        gap=gap,
        nvidia_technology=technology,
        technical_rationale=f"The {gap.gap_type} gap is plausible, but NVIDIA citation support is insufficient.",
        commercial_rationale="Human validation is required before this can become a supported recommendation.",
        complexity=_complexity(gap),
        nvidia_opportunity_priority="human_review",
        next_action="validate_nvidia_fit_with_human",
        startup_evidences=startup_evidences,
        nvidia_citations=citations,
        selection_reasons=(
            f"matched_gap_type:{gap.gap_type}",
            "has_startup_gap_evidence",
            *reasons,
        ),
    )


def _blocked_recommendation(
    *,
    run_id: str,
    startup_identifier: str,
    gap: TechnicalGap,
    retrieval: NVIDIAKnowledgeRetrieval | None,
    startup_evidences: tuple[FieldEvidence, ...],
    reasons: tuple[str, ...],
) -> NVIDIATechnicalRecommendation:
    result = _top_result(retrieval)
    citations = (result.citation,) if result is not None else ()
    technology = result.citation.document_title if result is not None else UNKNOWN
    return NVIDIATechnicalRecommendation(
        recommendation_id=_recommendation_id(run_id, startup_identifier, gap, technology),
        recommendation_type="technical",
        state="blocked",
        rank=0,
        gap=gap,
        nvidia_technology=technology,
        technical_rationale="The gap cannot safely produce a supported recommendation yet.",
        commercial_rationale="Resolve blocking evidence or quality issues before outreach.",
        complexity=_complexity(gap),
        nvidia_opportunity_priority="human_review",
        next_action="resolve_blocking_evidence",
        startup_evidences=startup_evidences,
        nvidia_citations=citations,
        selection_reasons=tuple(dict.fromkeys((f"matched_gap_type:{gap.gap_type}", *reasons))),
    )


def _retrieval_for_gap(
    gap: TechnicalGap,
    retrievals: tuple[NVIDIAKnowledgeRetrieval, ...],
) -> NVIDIAKnowledgeRetrieval | None:
    normalized_gap = gap.gap_type.replace("_", " ")
    for retrieval in retrievals:
        if any(result.chunk.topic == gap.gap_type for result in retrieval.results):
            return retrieval
        if normalized_gap in normalize_text(retrieval.query):
            return retrieval
    return None


def _blocking_context_reasons(
    *,
    collection_quality: CollectionQualitySummary,
    assessment: AINativeAssessment,
    evidence_groups: tuple[FieldEvidenceGroup, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not collection_quality.ready_for_evaluation:
        reasons.append("collection_quality_not_ready")
    if not assessment.ready_for_recommendation:
        reasons.append("assessment_not_ready_for_recommendation")
    if any(group.has_conflict for group in evidence_groups):
        reasons.append("conflicting_startup_evidence")
    return tuple(reasons)


def _top_recommendations_by_gap(
    recommendations: tuple[NVIDIATechnicalRecommendation, ...],
) -> tuple[NVIDIATechnicalRecommendation, ...]:
    top_by_gap: dict[str, NVIDIATechnicalRecommendation] = {}
    for recommendation in recommendations:
        existing = top_by_gap.get(recommendation.gap.gap_type)
        if existing is None or recommendation.rank < existing.rank:
            top_by_gap[recommendation.gap.gap_type] = recommendation
    return tuple(top_by_gap[gap_type] for gap_type in sorted(top_by_gap))


def _rank_supported_recommendations(
    candidates: list[tuple[float, NVIDIATechnicalRecommendation]],
) -> list[NVIDIATechnicalRecommendation]:
    return [
        recommendation
        for _, recommendation in sorted(
            candidates,
            key=lambda item: (
                -item[0],
                item[1].gap.gap_type,
                item[1].nvidia_citations[0].document_id if item[1].nvidia_citations else UNKNOWN,
                item[1].nvidia_citations[0].chunk_index if item[1].nvidia_citations else 0,
            ),
        )
    ]


def _rank_results_for_gap(
    *,
    gap: TechnicalGap,
    retrieval: NVIDIAKnowledgeRetrieval,
    assessment_confidence: float,
) -> tuple[RetrievedNVIDIAKnowledge, ...]:
    official_results = tuple(
        result for result in retrieval.results if _is_official_nvidia_url(result.citation.source_url)
    )
    topic_matches = tuple(result for result in official_results if result.chunk.topic == gap.gap_type)
    candidates = topic_matches or official_results
    return tuple(
        sorted(
            candidates,
            key=lambda result: (
                -_recommendation_score(
                    gap=gap,
                    result=result,
                    assessment_confidence=assessment_confidence,
                ),
                result.citation.document_id,
                result.citation.chunk_index,
            ),
        )
    )


def _is_close_alternative(
    top_result: RetrievedNVIDIAKnowledge,
    candidate_result: RetrievedNVIDIAKnowledge,
) -> bool:
    baseline = max(abs(top_result.score), 1.0)
    return (top_result.score - candidate_result.score) / baseline <= CLOSE_ALTERNATIVE_RELATIVE_DELTA


def _recommendation_score(
    *,
    gap: TechnicalGap,
    result: RetrievedNVIDIAKnowledge,
    assessment_confidence: float,
) -> float:
    severity = _severity_score(gap.severity)
    source_quality = _source_quality_score(result.citation.source_type)
    retrieval_score = min(max(result.score, 0.0), 10.0) / 10.0
    confidence = (gap.confidence + assessment_confidence) / 2
    return round((severity * 100) + (confidence * 10) + (source_quality * 5) + retrieval_score, 6)


def _severity_score(severity: str) -> int:
    if severity == "high":
        return 3
    if severity == "medium":
        return 2
    if severity == "low":
        return 1
    return 0


def _source_quality_score(source_type: str) -> float:
    if "documentation" in source_type:
        return 1.0
    if "developer" in source_type:
        return 0.9
    if "program" in source_type:
        return 0.8
    return 0.5


def _is_official_nvidia_url(source_url: str) -> bool:
    host = urlparse(source_url).hostname or ""
    return host == "nvidia.com" or host.endswith(".nvidia.com")


def _recommendation_quality(
    supported: tuple[NVIDIATechnicalRecommendation, ...],
    hypotheses: tuple[NVIDIATechnicalRecommendation, ...],
    blocked: tuple[NVIDIATechnicalRecommendation, ...],
) -> RecommendationQuality:
    if supported and not hypotheses and not blocked:
        return RecommendationQuality(
            ready_for_briefing=True,
            human_review_requested=False,
            reasons=("supported_recommendation_ready",),
        )

    reasons: list[str] = []
    if hypotheses:
        reasons.append("recommendation_hypothesis_requires_human_review")
    if blocked:
        reasons.append("blocked_recommendation_requires_human_review")
    if not supported and not hypotheses and not blocked:
        reasons.append("no_recommendation_candidate")
    return RecommendationQuality(
        ready_for_briefing=False,
        human_review_requested=True,
        reasons=tuple(reasons),
    )


def _final_priority(
    supported: tuple[NVIDIATechnicalRecommendation, ...],
    hypotheses: tuple[NVIDIATechnicalRecommendation, ...],
    blocked: tuple[NVIDIATechnicalRecommendation, ...],
) -> str:
    if not supported:
        return "human_review" if hypotheses or blocked else "low"
    if any(recommendation.nvidia_opportunity_priority == "urgent" for recommendation in supported):
        return "urgent"
    if any(recommendation.nvidia_opportunity_priority == "medium" for recommendation in supported):
        return "medium"
    return "low"


def _next_action(
    final_priority: str,
    supported: tuple[NVIDIATechnicalRecommendation, ...],
    hypotheses: tuple[NVIDIATechnicalRecommendation, ...],
    blocked: tuple[NVIDIATechnicalRecommendation, ...],
) -> str:
    if supported and final_priority in {"urgent", "medium"}:
        return "prepare_technical_outreach"
    if hypotheses:
        return "validate_nvidia_fit_with_human"
    if blocked:
        return "resolve_blocking_evidence"
    return "deprioritize_for_now"


def _supported_priority(gap: TechnicalGap) -> str:
    if gap.severity == "high" and gap.confidence >= 0.75:
        return "urgent"
    if gap.severity in {"high", "medium"}:
        return "medium"
    return "low"


def _complexity(gap: TechnicalGap) -> str:
    if gap.gap_type in {"robotics_simulation", "healthcare_ai"}:
        return "high"
    if gap.gap_type == UNKNOWN:
        return UNKNOWN
    return "medium"


def _top_result(retrieval: NVIDIAKnowledgeRetrieval | None) -> RetrievedNVIDIAKnowledge | None:
    if retrieval is None or not retrieval.results:
        return None
    return retrieval.results[0]


def _corpus_version(retrievals: tuple[NVIDIAKnowledgeRetrieval, ...]) -> str:
    if not retrievals:
        return UNKNOWN
    return retrievals[0].corpus_version


def _startup_identifier(profile: StartupProfile, assessment: AINativeAssessment) -> str:
    if profile.company_name.value != UNKNOWN:
        return profile.company_name.value
    return assessment.company_name


def _recommendation_id(
    run_id: str,
    startup_identifier: str,
    gap: TechnicalGap,
    technology_or_document: str,
) -> str:
    return ":".join(
        (
            _stable_id_part(run_id),
            _stable_id_part(startup_identifier),
            _stable_id_part(gap.gap_type),
            _stable_id_part(technology_or_document),
        )
    )


def _stable_id_part(value: str) -> str:
    normalized = normalize_text(value)
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-") or UNKNOWN


def _to_plain_data(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _to_plain_data(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {key: _to_plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain_data(item) for item in value]
    return value
