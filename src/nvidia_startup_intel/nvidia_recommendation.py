"""Deterministic NVIDIA recommendation contracts.

This module consumes upstream assessment artifacts and citable NVIDIA
Knowledge retrievals. It does not discover, scrape, extract, classify, retrieve
knowledge, call LLMs, or touch the network.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
import re

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
    supported: list[NVIDIATechnicalRecommendation] = []
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

        supported.append(
            _supported_recommendation(
                run_id=assessment.run_id,
                startup_identifier=startup_identifier,
                gap=gap,
                retrieval=retrieval,
                startup_evidences=startup_evidences,
                rank=_next_rank_for_gap(gap.gap_type, supported),
            )
        )

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
        alternatives=(),
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
    retrieval: NVIDIAKnowledgeRetrieval,
    startup_evidences: tuple[FieldEvidence, ...],
    rank: int,
) -> NVIDIATechnicalRecommendation:
    result = retrieval.results[0]
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
        ),
    )


def _hypothesis_recommendation(
    *,
    run_id: str,
    startup_identifier: str,
    gap: TechnicalGap,
    retrieval: NVIDIAKnowledgeRetrieval | None,
    startup_evidences: tuple[FieldEvidence, ...],
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
            "missing_official_nvidia_citation",
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


def _next_rank_for_gap(
    gap_type: str,
    recommendations: list[NVIDIATechnicalRecommendation],
) -> int:
    return 1 + sum(1 for recommendation in recommendations if recommendation.gap.gap_type == gap_type)


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
