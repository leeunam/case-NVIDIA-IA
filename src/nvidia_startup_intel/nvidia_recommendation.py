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
from nvidia_startup_intel.gap_space_assessment import GapSpaceAssessment
from nvidia_startup_intel.normalization import normalize_text
from nvidia_startup_intel.nvidia_knowledge import (
    NVIDIACitation,
    NVIDIAKnowledgeRetrieval,
    RetrievedNVIDIAKnowledge,
    summarize_nvidia_retrieval_quality,
)
from nvidia_startup_intel.nvidia_source_policy import is_official_nvidia_source_url
from nvidia_startup_intel.search_params import UNKNOWN
from nvidia_startup_intel.startup_profile import FieldEvidence, StartupProfile


SCHEMA_VERSION = "nvidia_recommendation.v1"
MIN_SUPPORTED_GAP_CONFIDENCE = 0.60
MIN_SUPPORTED_OPPORTUNITY_CONFIDENCE = 0.60
EXCESSIVE_UNKNOWN_FIELD_COUNT = 3
CLOSE_ALTERNATIVE_RELATIVE_DELTA = 0.15
SUPPORTED_TECHNICAL_GAP_TYPES = frozenset(
    {
        "model_serving",
        "llm_customization",
        "data_acceleration",
        "computer_vision",
    }
)
SUPPORTED_PROGRAM_OPPORTUNITY_TYPES = frozenset(
    {"inception_program_fit", "partner_ecosystem"}
)


@dataclass(frozen=True)
class RecommendationMetrics:
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
class RecommendationQuality:
    ready_for_briefing: bool
    human_review_requested: bool
    states: tuple[str, ...]
    reasons: tuple[str, ...]
    metrics: RecommendationMetrics


@dataclass(frozen=True)
class CommercialOpportunity:
    opportunity_type: str
    description: str
    confidence: float
    evidences: tuple[FieldEvidence, ...]
    is_hypothesis: bool = False


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
class NVIDIAProgramRecommendation:
    recommendation_id: str
    recommendation_type: str
    state: str
    rank: int
    opportunity: CommercialOpportunity
    supporting_gap: TechnicalGap | None
    nvidia_program: str
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
    program_recommendations: tuple[NVIDIAProgramRecommendation, ...]
    top_recommendations_by_gap: tuple[NVIDIATechnicalRecommendation, ...]
    alternatives: tuple[NVIDIATechnicalRecommendation, ...]
    hypotheses: tuple[NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation, ...]
    blocked_recommendations: tuple[NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation, ...]
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
    commercial_opportunities: tuple[CommercialOpportunity, ...] = (),
    gap_space_assessment: GapSpaceAssessment | None = None,
) -> NVIDIARecommendationSet:
    """Build a recommendation set from upstream diagnosis and NVIDIA citations."""

    startup_identifier = _startup_identifier(profile, assessment)
    blocked_by_context = _blocking_context_reasons(
        collection_quality=collection_quality,
        assessment=assessment,
        evidence_groups=evidence_groups,
        gap_space_assessment=gap_space_assessment,
    )
    supported_candidates: list[tuple[float, NVIDIATechnicalRecommendation]] = []
    alternative_candidates: list[tuple[float, NVIDIATechnicalRecommendation]] = []
    program_candidates: list[tuple[float, NVIDIAProgramRecommendation]] = []
    hypotheses: list[NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation] = []
    blocked: list[NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation] = []

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

        retrieval_quality = summarize_nvidia_retrieval_quality(retrieval) if retrieval else None
        if retrieval_quality is None or not retrieval_quality.has_sufficient_citation:
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

    program_inputs = (
        *((opportunity, None) for opportunity in commercial_opportunities),
        *_program_opportunities_from_gaps(
            assessment=assessment,
            retrievals=retrievals,
            commercial_opportunities=commercial_opportunities,
        ),
    )
    for opportunity, supporting_gap in program_inputs:
        if opportunity.opportunity_type == UNKNOWN:
            continue

        retrieval = _retrieval_for_opportunity(opportunity, retrievals)
        startup_evidences = tuple(opportunity.evidences)
        if blocked_by_context or not startup_evidences:
            blocked.append(
                _blocked_program_recommendation(
                    run_id=assessment.run_id,
                    startup_identifier=startup_identifier,
                    opportunity=opportunity,
                    supporting_gap=supporting_gap,
                    retrieval=retrieval,
                    startup_evidences=startup_evidences,
                    reasons=blocked_by_context
                    or ("missing_startup_opportunity_evidence",),
                )
            )
            continue

        if opportunity.opportunity_type not in SUPPORTED_PROGRAM_OPPORTUNITY_TYPES:
            hypotheses.append(
                _hypothesis_program_recommendation(
                    run_id=assessment.run_id,
                    startup_identifier=startup_identifier,
                    opportunity=opportunity,
                    supporting_gap=supporting_gap,
                    retrieval=retrieval,
                    startup_evidences=startup_evidences,
                    reasons=("opportunity_type_not_covered_by_program_rules",),
                )
            )
            continue

        if retrieval is None or not summarize_nvidia_retrieval_quality(retrieval).has_sufficient_citation:
            hypotheses.append(
                _hypothesis_program_recommendation(
                    run_id=assessment.run_id,
                    startup_identifier=startup_identifier,
                    opportunity=opportunity,
                    supporting_gap=supporting_gap,
                    retrieval=retrieval,
                    startup_evidences=startup_evidences,
                )
            )
            continue

        if opportunity.confidence < MIN_SUPPORTED_OPPORTUNITY_CONFIDENCE:
            hypotheses.append(
                _hypothesis_program_recommendation(
                    run_id=assessment.run_id,
                    startup_identifier=startup_identifier,
                    opportunity=opportunity,
                    supporting_gap=supporting_gap,
                    retrieval=retrieval,
                    startup_evidences=startup_evidences,
                    reasons=("low_opportunity_confidence",),
                )
            )
            continue

        ranked_results = _rank_results_for_opportunity(opportunity=opportunity, retrieval=retrieval)
        recommendation = _supported_program_recommendation(
            run_id=assessment.run_id,
            startup_identifier=startup_identifier,
            opportunity=opportunity,
            supporting_gap=supporting_gap,
            result=ranked_results[0],
            startup_evidences=startup_evidences,
            rank=1,
        )
        program_candidates.append(
            (
                _program_recommendation_score(opportunity=opportunity, result=ranked_results[0]),
                recommendation,
            )
        )

    if (
        not _has_supporting_gap_or_opportunity(assessment, commercial_opportunities)
        and not hypotheses
        and not blocked
    ):
        generic_inception_retrieval = _generic_inception_retrieval(retrievals)
        if generic_inception_retrieval is not None:
            blocked.append(
                _blocked_program_recommendation(
                    run_id=assessment.run_id,
                    startup_identifier=startup_identifier,
                    opportunity=CommercialOpportunity(
                        opportunity_type=UNKNOWN,
                        description=UNKNOWN,
                        confidence=0.0,
                        evidences=(),
                    ),
                    supporting_gap=None,
                    retrieval=generic_inception_retrieval,
                    startup_evidences=(),
                    reasons=("generic_inception_without_specific_gap_or_opportunity",),
                )
            )

    supported = _rank_supported_recommendations(supported_candidates)
    supported_programs = _rank_supported_program_recommendations(program_candidates)
    alternatives = tuple(_rank_supported_recommendations(alternative_candidates))
    top_recommendations = _top_recommendations_by_gap(tuple(supported))
    final_priority = _final_priority(
        tuple(supported),
        tuple(supported_programs),
        tuple(hypotheses),
        tuple(blocked),
    )
    next_action = _next_action(
        final_priority,
        tuple(supported),
        tuple(supported_programs),
        tuple(hypotheses),
        tuple(blocked),
    )
    quality = _recommendation_quality(
        tuple((*supported, *supported_programs)),
        tuple(hypotheses),
        tuple(blocked),
    )

    return NVIDIARecommendationSet(
        schema_version=SCHEMA_VERSION,
        run_id=assessment.run_id,
        startup_identifier=startup_identifier,
        corpus_version=_corpus_version(retrievals),
        technical_recommendations=tuple(supported),
        program_recommendations=tuple(supported_programs),
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
            "ranked_by_recommendation_score",
            "top_recommendation_for_gap" if rank == 1 else "alternative_recommendation_for_gap",
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
        technical_rationale=_hypothesis_technical_rationale(gap, reasons),
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


def _hypothesis_technical_rationale(gap: TechnicalGap, reasons: tuple[str, ...]) -> str:
    if "low_gap_confidence" in reasons:
        return (
            f"The {gap.gap_type} gap has startup evidence and possible NVIDIA citation support, "
            "but gap confidence is below the supported recommendation threshold."
        )
    if "gap_type_not_covered_by_recommendation_rules" in reasons:
        return (
            f"The {gap.gap_type} gap is plausible, but it is not covered by "
            "deterministic recommendation rules in this slice."
        )
    if "missing_official_nvidia_citation" in reasons:
        return f"The {gap.gap_type} gap is plausible, but NVIDIA citation support is insufficient."
    return f"The {gap.gap_type} gap is plausible, but human validation is required before recommendation."


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


def _supported_program_recommendation(
    *,
    run_id: str,
    startup_identifier: str,
    opportunity: CommercialOpportunity,
    supporting_gap: TechnicalGap | None,
    result: RetrievedNVIDIAKnowledge,
    startup_evidences: tuple[FieldEvidence, ...],
    rank: int,
) -> NVIDIAProgramRecommendation:
    citation = result.citation
    return NVIDIAProgramRecommendation(
        recommendation_id=_program_recommendation_id(
            run_id,
            startup_identifier,
            opportunity,
            citation.document_id,
        ),
        recommendation_type="program",
        state="supported",
        rank=rank,
        opportunity=opportunity,
        supporting_gap=supporting_gap,
        nvidia_program=citation.document_title,
        technical_rationale=_program_technical_rationale(opportunity, supporting_gap),
        commercial_rationale=(
            f"{citation.document_title} is cited for the {opportunity.opportunity_type} "
            f"commercial opportunity: {opportunity.description}"
        ),
        complexity="low",
        nvidia_opportunity_priority=_supported_program_priority(opportunity),
        next_action="prepare_program_outreach",
        startup_evidences=startup_evidences,
        nvidia_citations=(citation,),
        selection_reasons=(
            f"matched_opportunity_type:{opportunity.opportunity_type}",
            "has_startup_opportunity_evidence",
            "has_official_nvidia_citation",
            _program_gate_reason(opportunity, supporting_gap),
            "ranked_by_program_recommendation_score",
            (
                "top_recommendation_for_opportunity"
                if rank == 1
                else "alternative_recommendation_for_opportunity"
            ),
        ),
    )


def _hypothesis_program_recommendation(
    *,
    run_id: str,
    startup_identifier: str,
    opportunity: CommercialOpportunity,
    supporting_gap: TechnicalGap | None,
    retrieval: NVIDIAKnowledgeRetrieval | None,
    startup_evidences: tuple[FieldEvidence, ...],
    reasons: tuple[str, ...] = ("missing_official_nvidia_citation",),
) -> NVIDIAProgramRecommendation:
    result = _top_official_result(retrieval)
    citations = (result.citation,) if result is not None else ()
    program = result.citation.document_title if result is not None else UNKNOWN
    return NVIDIAProgramRecommendation(
        recommendation_id=_program_recommendation_id(
            run_id,
            startup_identifier,
            opportunity,
            program,
        ),
        recommendation_type="program",
        state="hypothesis",
        rank=0,
        opportunity=opportunity,
        supporting_gap=supporting_gap,
        nvidia_program=program,
        technical_rationale=_program_technical_rationale(opportunity, supporting_gap),
        commercial_rationale=_hypothesis_program_commercial_rationale(opportunity, reasons),
        complexity="low",
        nvidia_opportunity_priority="human_review",
        next_action="validate_nvidia_program_fit_with_human",
        startup_evidences=startup_evidences,
        nvidia_citations=citations,
        selection_reasons=(
            f"matched_opportunity_type:{opportunity.opportunity_type}",
            "has_startup_opportunity_evidence",
            *reasons,
        ),
    )


def _hypothesis_program_commercial_rationale(
    opportunity: CommercialOpportunity,
    reasons: tuple[str, ...],
) -> str:
    if "low_opportunity_confidence" in reasons:
        return (
            f"The {opportunity.opportunity_type} opportunity has startup evidence and possible "
            "NVIDIA program support, but opportunity confidence is below the supported threshold."
        )
    if "opportunity_type_not_covered_by_program_rules" in reasons:
        return (
            f"The {opportunity.opportunity_type} opportunity is plausible, but it is not covered "
            "by deterministic program recommendation rules in this slice."
        )
    if "missing_official_nvidia_citation" in reasons:
        return (
            f"The {opportunity.opportunity_type} opportunity is plausible, but NVIDIA program "
            "citation support is insufficient."
        )
    return (
        f"The {opportunity.opportunity_type} opportunity is plausible, but human validation is "
        "required before recommendation."
    )


def _blocked_program_recommendation(
    *,
    run_id: str,
    startup_identifier: str,
    opportunity: CommercialOpportunity,
    supporting_gap: TechnicalGap | None,
    retrieval: NVIDIAKnowledgeRetrieval | None,
    startup_evidences: tuple[FieldEvidence, ...],
    reasons: tuple[str, ...],
) -> NVIDIAProgramRecommendation:
    result = _top_result(retrieval)
    citations = (result.citation,) if result is not None else ()
    program = result.citation.document_title if result is not None else UNKNOWN
    return NVIDIAProgramRecommendation(
        recommendation_id=_program_recommendation_id(
            run_id,
            startup_identifier,
            opportunity,
            program,
        ),
        recommendation_type="program",
        state="blocked",
        rank=0,
        opportunity=opportunity,
        supporting_gap=supporting_gap,
        nvidia_program=program,
        technical_rationale=_program_technical_rationale(opportunity, supporting_gap),
        commercial_rationale="Resolve blocking opportunity evidence or quality issues before outreach.",
        complexity="low",
        nvidia_opportunity_priority="human_review",
        next_action="resolve_blocking_evidence",
        startup_evidences=startup_evidences,
        nvidia_citations=citations,
        selection_reasons=tuple(
            dict.fromkeys((f"matched_opportunity_type:{opportunity.opportunity_type}", *reasons))
        ),
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


def _retrieval_for_opportunity(
    opportunity: CommercialOpportunity,
    retrievals: tuple[NVIDIAKnowledgeRetrieval, ...],
) -> NVIDIAKnowledgeRetrieval | None:
    normalized_opportunity = opportunity.opportunity_type.replace("_", " ")
    for retrieval in retrievals:
        if normalized_opportunity in normalize_text(retrieval.query):
            return retrieval
        if any(_program_result_matches_opportunity(opportunity, result) for result in retrieval.results):
            return retrieval
    return None


def _program_opportunities_from_gaps(
    *,
    assessment: AINativeAssessment,
    retrievals: tuple[NVIDIAKnowledgeRetrieval, ...],
    commercial_opportunities: tuple[CommercialOpportunity, ...],
) -> tuple[tuple[CommercialOpportunity, TechnicalGap], ...]:
    if any(opportunity.opportunity_type == "inception_program_fit" for opportunity in commercial_opportunities):
        return ()
    if _generic_inception_retrieval(retrievals) is None:
        return ()

    opportunities: list[tuple[CommercialOpportunity, TechnicalGap]] = []
    for gap in assessment.technical_gaps:
        if gap.gap_type == UNKNOWN or not gap.evidences:
            continue
        opportunities.append(
            (
                CommercialOpportunity(
                    opportunity_type="inception_program_fit",
                    description=f"Program support for {gap.gap_type}: {gap.description}",
                    confidence=gap.confidence,
                    evidences=gap.evidences,
                    is_hypothesis=gap.is_hypothesis,
                ),
                gap,
            )
        )
    return tuple(opportunities)


def _has_supporting_gap_or_opportunity(
    assessment: AINativeAssessment,
    commercial_opportunities: tuple[CommercialOpportunity, ...],
) -> bool:
    has_gap = any(gap.gap_type != UNKNOWN and gap.evidences for gap in assessment.technical_gaps)
    has_opportunity = any(
        opportunity.opportunity_type != UNKNOWN and opportunity.evidences
        for opportunity in commercial_opportunities
    )
    return has_gap or has_opportunity


def _generic_inception_retrieval(
    retrievals: tuple[NVIDIAKnowledgeRetrieval, ...],
) -> NVIDIAKnowledgeRetrieval | None:
    for retrieval in retrievals:
        if any(_is_inception_result(result) for result in retrieval.results):
            return retrieval
    return None


def _blocking_context_reasons(
    *,
    collection_quality: CollectionQualitySummary,
    assessment: AINativeAssessment,
    evidence_groups: tuple[FieldEvidenceGroup, ...],
    gap_space_assessment: GapSpaceAssessment | None = None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not collection_quality.ready_for_evaluation:
        reasons.append("collection_quality_not_ready")
    if not assessment.ready_for_recommendation:
        reasons.append("assessment_not_ready_for_recommendation")
    if any(group.has_conflict for group in evidence_groups):
        reasons.append("conflicting_startup_evidence")
    if any(risk.severity == "high" for risk in assessment.wrapper_dependency_risks):
        reasons.append("high_wrapper_risk")
    if _has_excessive_unknown_fields(collection_quality):
        reasons.append("excessive_unknown_fields")
        reasons.extend(f"unknown_field:{field_name}" for field_name in _unknown_field_names(collection_quality))
    if gap_space_assessment is not None and not gap_space_assessment.quality.ready_for_recommendation:
        reasons.append("gap_space_not_ready_for_recommendation")
        reasons.extend(reason for reason in gap_space_assessment.quality.reasons if reason != "gap_space_ready_for_recommendation")
    return tuple(reasons)


def _has_excessive_unknown_fields(collection_quality: CollectionQualitySummary) -> bool:
    return sum(count for _, count in _unknown_field_entries(collection_quality)) >= EXCESSIVE_UNKNOWN_FIELD_COUNT


def _unknown_field_names(collection_quality: CollectionQualitySummary) -> tuple[str, ...]:
    return tuple(field_name for field_name, count in _unknown_field_entries(collection_quality) if count > 0)


def _unknown_field_entries(collection_quality: CollectionQualitySummary) -> tuple[tuple[str, int], ...]:
    entries: list[tuple[str, int]] = []
    for item in collection_quality.unknown_fields:
        if isinstance(item, tuple) and len(item) == 2:
            field_name, count = item
            entries.append((str(field_name), int(count)))
            continue
        entries.append((str(item), 1))
    return tuple(entries)


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


def _rank_supported_program_recommendations(
    candidates: list[tuple[float, NVIDIAProgramRecommendation]],
) -> list[NVIDIAProgramRecommendation]:
    return [
        recommendation
        for _, recommendation in sorted(
            candidates,
            key=lambda item: (
                -item[0],
                item[1].opportunity.opportunity_type,
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
        result for result in retrieval.results if is_official_nvidia_source_url(result.citation.source_url)
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


def _rank_results_for_opportunity(
    *,
    opportunity: CommercialOpportunity,
    retrieval: NVIDIAKnowledgeRetrieval,
) -> tuple[RetrievedNVIDIAKnowledge, ...]:
    official_results = tuple(
        result for result in retrieval.results if is_official_nvidia_source_url(result.citation.source_url)
    )
    program_matches = tuple(
        result for result in official_results if _program_result_matches_opportunity(opportunity, result)
    )
    candidates = program_matches or official_results
    return tuple(
        sorted(
            candidates,
            key=lambda result: (
                -_program_recommendation_score(opportunity=opportunity, result=result),
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


def _program_recommendation_score(
    *,
    opportunity: CommercialOpportunity,
    result: RetrievedNVIDIAKnowledge,
) -> float:
    source_quality = _source_quality_score(result.citation.source_type)
    retrieval_score = min(max(result.score, 0.0), 10.0) / 10.0
    return round((opportunity.confidence * 10) + (source_quality * 5) + retrieval_score, 6)


def _program_result_matches_opportunity(
    opportunity: CommercialOpportunity,
    result: RetrievedNVIDIAKnowledge,
) -> bool:
    citation_text = normalize_text(
        " ".join(
            (
                result.citation.document_id,
                result.citation.document_title,
                result.citation.excerpt,
                result.chunk.topic,
            )
        )
    )
    if opportunity.opportunity_type == "inception_program_fit":
        return "inception" in citation_text or result.chunk.topic == "startup_program"
    return opportunity.opportunity_type.replace("_", " ") in citation_text


def _program_technical_rationale(
    opportunity: CommercialOpportunity,
    supporting_gap: TechnicalGap | None,
) -> str:
    if supporting_gap is not None:
        return (
            f"Program fit is tied to the {supporting_gap.gap_type} technical gap, "
            "but this is not a replacement for a technical architecture recommendation."
        )
    return "This is a program recommendation, not a technical architecture recommendation."


def _program_gate_reason(
    opportunity: CommercialOpportunity,
    supporting_gap: TechnicalGap | None,
) -> str:
    if opportunity.opportunity_type == "inception_program_fit":
        if supporting_gap is not None:
            return "inception_gate_specific_technical_gap"
        return "inception_gate_specific_opportunity"
    return "program_gate_specific_opportunity"


def _is_inception_result(result: RetrievedNVIDIAKnowledge) -> bool:
    citation_text = normalize_text(
        " ".join(
            (
                result.citation.document_id,
                result.citation.document_title,
                result.citation.excerpt,
            )
        )
    )
    return "inception" in citation_text


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


def _recommendation_quality(
    supported: tuple[NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation, ...],
    hypotheses: tuple[NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation, ...],
    blocked: tuple[NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation, ...],
) -> RecommendationQuality:
    if supported and not hypotheses and not blocked:
        reasons = ("supported_recommendation_ready",)
        return RecommendationQuality(
            ready_for_briefing=True,
            human_review_requested=False,
            states=("supported", "ready_for_briefing"),
            reasons=reasons,
            metrics=_recommendation_metrics(
                supported=supported,
                hypotheses=hypotheses,
                blocked=blocked,
                reasons=reasons,
                ready_for_briefing=True,
            ),
        )

    reasons: list[str] = []
    if hypotheses:
        reasons.append("recommendation_hypothesis_requires_human_review")
    if blocked:
        reasons.append("blocked_recommendation_requires_human_review")
    if not supported and not hypotheses and not blocked:
        reasons.append("no_recommendation_candidate")
    reason_tuple = tuple(dict.fromkeys((*reasons, *_quality_gate_reasons(hypotheses, blocked))))
    return RecommendationQuality(
        ready_for_briefing=False,
        human_review_requested=True,
        states=_quality_states(
            supported=supported,
            hypotheses=hypotheses,
            blocked=blocked,
            ready_for_briefing=False,
            human_review_requested=True,
        ),
        reasons=reason_tuple,
        metrics=_recommendation_metrics(
            supported=supported,
            hypotheses=hypotheses,
            blocked=blocked,
            reasons=reason_tuple,
            ready_for_briefing=False,
        ),
    )


def _quality_states(
    *,
    supported: tuple[NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation, ...],
    hypotheses: tuple[NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation, ...],
    blocked: tuple[NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation, ...],
    ready_for_briefing: bool,
    human_review_requested: bool,
) -> tuple[str, ...]:
    states: list[str] = []
    if supported:
        states.append("supported")
    if hypotheses:
        states.append("hypothesis")
    if blocked:
        states.append("blocked")
    if ready_for_briefing:
        states.append("ready_for_briefing")
    if human_review_requested:
        states.append("human_review_requested")
    return tuple(states)


def _recommendation_metrics(
    *,
    supported: tuple[NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation, ...],
    hypotheses: tuple[NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation, ...],
    blocked: tuple[NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation, ...],
    reasons: tuple[str, ...],
    ready_for_briefing: bool,
) -> RecommendationMetrics:
    recommendations = (*supported, *hypotheses, *blocked)
    return RecommendationMetrics(
        supported_recommendation_count=len(supported),
        hypothesis_recommendation_count=len(hypotheses),
        blocked_recommendation_count=len(blocked),
        recommendations_with_official_nvidia_citation_count=sum(
            1 for recommendation in recommendations if _has_official_citation(recommendation)
        ),
        recommendations_with_startup_evidence_count=sum(
            1 for recommendation in recommendations if recommendation.startup_evidences
        ),
        gaps_without_recommendation=_gaps_without_recommendation(hypotheses, blocked),
        blocked_briefing_count=0 if ready_for_briefing else 1,
        human_review_reason_counts=(
            () if ready_for_briefing else tuple((reason, reasons.count(reason)) for reason in dict.fromkeys(reasons))
        ),
        corpus_expansion_targets=_corpus_expansion_targets(hypotheses, blocked),
        evidence_collection_targets=_evidence_collection_targets(hypotheses, blocked),
    )


def _has_official_citation(
    recommendation: NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation,
) -> bool:
    return any(
        is_official_nvidia_source_url(citation.source_url)
        for citation in recommendation.nvidia_citations
    )


def _quality_gate_reasons(
    hypotheses: tuple[NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation, ...],
    blocked: tuple[NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation, ...],
) -> tuple[str, ...]:
    gate_reasons: list[str] = []
    for recommendation in (*hypotheses, *blocked):
        for reason in recommendation.selection_reasons:
            if _is_quality_gate_reason(reason):
                gate_reasons.append(reason)
    return tuple(dict.fromkeys(gate_reasons))


def _is_quality_gate_reason(reason: str) -> bool:
    return (
        reason.startswith("missing_")
        or reason.startswith("low_")
        or reason.startswith("unknown_field:")
        or reason.endswith("_not_ready")
        or reason.endswith("_not_covered_by_recommendation_rules")
        or reason.endswith("_not_covered_by_program_rules")
        or reason in {
            "assessment_not_ready_for_recommendation",
            "collection_quality_not_ready",
            "conflicting_startup_evidence",
            "excessive_unknown_fields",
            "generic_inception_without_specific_gap_or_opportunity",
            "gap_space_not_ready_for_recommendation",
            "high_wrapper_risk",
        }
    )


def _gaps_without_recommendation(
    hypotheses: tuple[NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation, ...],
    blocked: tuple[NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation, ...],
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            recommendation.gap.gap_type
            for recommendation in (*hypotheses, *blocked)
            if isinstance(recommendation, NVIDIATechnicalRecommendation)
            and recommendation.gap.gap_type != UNKNOWN
        )
    )


def _corpus_expansion_targets(
    hypotheses: tuple[NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation, ...],
    blocked: tuple[NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation, ...],
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            _recommendation_target(recommendation)
            for recommendation in (*hypotheses, *blocked)
            if "missing_official_nvidia_citation" in recommendation.selection_reasons
        )
    )


def _evidence_collection_targets(
    hypotheses: tuple[NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation, ...],
    blocked: tuple[NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation, ...],
) -> tuple[str, ...]:
    missing_startup_targets = tuple(
        dict.fromkeys(
            _recommendation_target(recommendation)
            for recommendation in (*hypotheses, *blocked)
            if any(reason.startswith("missing_startup") for reason in recommendation.selection_reasons)
        )
    )
    unknown_field_targets = tuple(
        dict.fromkeys(
            reason.removeprefix("unknown_field:")
            for recommendation in (*hypotheses, *blocked)
            for reason in recommendation.selection_reasons
            if reason.startswith("unknown_field:")
        )
    )
    return (*missing_startup_targets, *unknown_field_targets)


def _recommendation_target(
    recommendation: NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation,
) -> str:
    if isinstance(recommendation, NVIDIATechnicalRecommendation):
        return recommendation.gap.gap_type
    return recommendation.opportunity.opportunity_type


def _final_priority(
    supported: tuple[NVIDIATechnicalRecommendation, ...],
    supported_programs: tuple[NVIDIAProgramRecommendation, ...],
    hypotheses: tuple[NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation, ...],
    blocked: tuple[NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation, ...],
) -> str:
    supported_recommendations = (*supported, *supported_programs)
    if not supported_recommendations:
        return "human_review" if hypotheses or blocked else "low"
    if any(recommendation.nvidia_opportunity_priority == "urgent" for recommendation in supported_recommendations):
        return "urgent"
    if any(recommendation.nvidia_opportunity_priority == "medium" for recommendation in supported_recommendations):
        return "medium"
    return "low"


def _next_action(
    final_priority: str,
    supported: tuple[NVIDIATechnicalRecommendation, ...],
    supported_programs: tuple[NVIDIAProgramRecommendation, ...],
    hypotheses: tuple[NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation, ...],
    blocked: tuple[NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation, ...],
) -> str:
    if supported and final_priority in {"urgent", "medium"}:
        return "prepare_technical_outreach"
    if supported_programs and final_priority in {"urgent", "medium", "low"}:
        return "prepare_program_outreach"
    if hypotheses:
        if any(recommendation.recommendation_type == "program" for recommendation in hypotheses):
            return "validate_nvidia_program_fit_with_human"
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


def _supported_program_priority(opportunity: CommercialOpportunity) -> str:
    if opportunity.confidence >= 0.75:
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


def _top_official_result(retrieval: NVIDIAKnowledgeRetrieval | None) -> RetrievedNVIDIAKnowledge | None:
    if retrieval is None:
        return None
    for result in retrieval.results:
        if is_official_nvidia_source_url(result.citation.source_url):
            return result
    return None


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


def _program_recommendation_id(
    run_id: str,
    startup_identifier: str,
    opportunity: CommercialOpportunity,
    program_or_document: str,
) -> str:
    return ":".join(
        (
            _stable_id_part(run_id),
            _stable_id_part(startup_identifier),
            _stable_id_part(opportunity.opportunity_type),
            _stable_id_part(program_or_document),
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
