"""Deterministic briefing contracts and LLM-ready narrative seam.

Structured briefing generation remains deterministic. Optional narrative drafts
consume an existing briefing artifact through the project-owned LLMClient seam
without calling retrievers, network services, or workflow frameworks directly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, is_dataclass

from nvidia_startup_intel.ai_native_assessment import AINativeAssessment, TechnicalGap, WrapperDependencyRisk
from nvidia_startup_intel.collection_quality import CollectionQualitySummary
from nvidia_startup_intel.evidence import FieldEvidenceGroup
from nvidia_startup_intel.llm_adapters import (
    LLMClient,
    LLMGenerationRequest,
    LLMGenerationResponse,
    LLM_REQUEST_SCHEMA_VERSION,
)
from nvidia_startup_intel.nvidia_knowledge import NVIDIACitation
from nvidia_startup_intel.nvidia_knowledge import NVIDIAKnowledgeRetrieval
from nvidia_startup_intel.nvidia_recommendation import (
    NVIDIAProgramRecommendation,
    NVIDIARecommendationSet,
    NVIDIATechnicalRecommendation,
)
from nvidia_startup_intel.search_params import UNKNOWN
from nvidia_startup_intel.startup_profile import FieldEvidence, ProfileField, StartupProfile


SCHEMA_VERSION = "executive_briefing.v1"
HUMAN_REVIEW_SCHEMA_VERSION = "human_review_briefing.v1"
BRIEFING_NARRATIVE_SCHEMA_VERSION = "briefing_narrative.v1"
UNKNOWN_PROFILE_FIELDS = ("funding", "customers", "founders", "technologies_used")
BriefableRecommendation = NVIDIATechnicalRecommendation | NVIDIAProgramRecommendation


@dataclass(frozen=True)
class BriefingClaim:
    text: str
    claim_type: str
    section: str
    confidence: float
    evidence_references: tuple[FieldEvidence, ...]
    citation_references: tuple[NVIDIACitation, ...]
    reason: str = ""


@dataclass(frozen=True)
class PendingQuestion:
    field_name: str
    question: str
    priority: str
    reason: str


@dataclass(frozen=True)
class ExecutiveBriefing:
    schema_version: str
    run_id: str
    startup_identifier: str
    status: str
    executive_summary: str
    diagnosis: str
    opportunity: str
    risks: tuple[str, ...]
    recommendations: tuple[str, ...]
    pending_questions: tuple[PendingQuestion, ...]
    claims: tuple[BriefingClaim, ...]
    evidence_references: tuple[FieldEvidence, ...]
    citation_references: tuple[NVIDIACitation, ...]
    next_action: str
    audit_reasons: tuple[str, ...]


@dataclass(frozen=True)
class HumanReviewBriefing:
    schema_version: str
    run_id: str
    startup_identifier: str
    status: str
    area_of_operation: str
    discoveries: tuple[BriefingClaim, ...]
    main_evidence: tuple[FieldEvidence, ...]
    suspected_gaps: tuple[TechnicalGap, ...]
    commercial_opportunities: tuple[object, ...]
    wrapper_risks: tuple[WrapperDependencyRisk, ...]
    conflicts: tuple[FieldEvidenceGroup, ...]
    unknowns: tuple[str, ...]
    supported_recommendations: tuple[BriefableRecommendation, ...]
    hypothesis_recommendations: tuple[BriefableRecommendation, ...]
    blocked_recommendations: tuple[BriefableRecommendation, ...]
    review_reasons: tuple[str, ...]
    pending_questions: tuple[PendingQuestion, ...]
    evidence_references: tuple[FieldEvidence, ...]
    citation_references: tuple[NVIDIACitation, ...]
    next_action: str
    audit_reasons: tuple[str, ...]


@dataclass(frozen=True)
class BriefingNarrative:
    schema_version: str
    run_id: str
    startup_identifier: str
    source_briefing_schema_version: str
    source_briefing_status: str
    technical_gap_narrative: str
    commercial_approach_narrative: str
    narrative_text: str
    claims: tuple[BriefingClaim, ...]
    unknowns: tuple[str, ...]
    risks: tuple[str, ...]
    review_reasons: tuple[str, ...]
    pending_questions: tuple[PendingQuestion, ...]
    evidence_references: tuple[FieldEvidence, ...]
    citation_references: tuple[NVIDIACitation, ...]
    next_action: str
    llm_request: LLMGenerationRequest
    llm_response: LLMGenerationResponse
    audit_reasons: tuple[str, ...]


def generate_executive_briefing(
    *,
    profile: StartupProfile,
    evidence_groups: tuple[FieldEvidenceGroup, ...],
    collection_quality: CollectionQualitySummary,
    assessment: AINativeAssessment,
    recommendation_set: NVIDIARecommendationSet,
) -> ExecutiveBriefing:
    """Generate a deterministic executive briefing from downstream artifacts."""

    startup_identifier = recommendation_set.startup_identifier
    recommended_claims = _recommended_claims(recommendation_set)
    unknown_claims = _unknown_claims(profile)
    claims = (
        *_profile_claims(profile),
        _diagnosis_claim(assessment),
        _opportunity_claim(recommendation_set),
        *_risk_claims(assessment),
        *recommended_claims,
        *unknown_claims,
    )

    evidence_references = _dedupe_evidences(
        tuple(evidence for claim in claims for evidence in claim.evidence_references)
    )
    citation_references = _dedupe_citations(
        tuple(citation for claim in claims for citation in claim.citation_references)
    )
    recommendations = tuple(claim.text for claim in recommended_claims)
    pending_questions = _pending_questions(profile, assessment)
    status = "ready_for_use" if recommendation_set.quality.ready_for_briefing else "ready_for_human_review"

    return ExecutiveBriefing(
        schema_version=SCHEMA_VERSION,
        run_id=recommendation_set.run_id,
        startup_identifier=startup_identifier,
        status=status,
        executive_summary=_executive_summary(startup_identifier, assessment, recommendation_set),
        diagnosis=_diagnosis_text(assessment),
        opportunity=recommendation_set.final_nvidia_opportunity_priority,
        risks=_risk_texts(assessment),
        recommendations=recommendations,
        pending_questions=pending_questions,
        claims=claims,
        evidence_references=evidence_references,
        citation_references=citation_references,
        next_action=recommendation_set.next_action,
        audit_reasons=_dedupe_reasons(
            recommendation_set.quality.reasons,
            _collection_audit_reasons(collection_quality),
            _conflict_audit_reasons(evidence_groups),
        ),
    )


def generate_human_review_briefing(
    *,
    profile: StartupProfile,
    evidence_groups: tuple[FieldEvidenceGroup, ...],
    collection_quality: CollectionQualitySummary,
    assessment: AINativeAssessment,
    recommendation_set: NVIDIARecommendationSet,
) -> HumanReviewBriefing:
    """Generate actionable review context when recommendations are not safe to use."""

    discoveries = _profile_claims(profile)
    conflicts = tuple(group for group in evidence_groups if group.has_conflict)
    unknowns = _unknown_field_names(profile, collection_quality, assessment)
    review_reasons = _human_review_reasons(
        collection_quality=collection_quality,
        evidence_groups=evidence_groups,
        assessment=assessment,
        recommendation_set=recommendation_set,
    )
    pending_questions = _human_review_pending_questions(
        profile=profile,
        assessment=assessment,
        recommendation_set=recommendation_set,
        conflicts=conflicts,
        collection_quality=collection_quality,
    )
    evidence_references = _dedupe_evidences(
        (
            *(evidence for claim in discoveries for evidence in claim.evidence_references),
            *assessment.evidences,
            *(evidence for gap in assessment.technical_gaps for evidence in gap.evidences),
            *(evidence for risk in assessment.wrapper_dependency_risks for evidence in risk.evidences),
            *(evidence for group in evidence_groups for evidence in group.evidences),
            *(
                evidence
                for recommendation in (
                    *recommendation_set.technical_recommendations,
                    *recommendation_set.program_recommendations,
                    *recommendation_set.hypotheses,
                    *recommendation_set.blocked_recommendations,
                )
                for evidence in recommendation.startup_evidences
            ),
        )
    )
    citation_references = _dedupe_citations(
        tuple(
            citation
            for recommendation in (
                *recommendation_set.technical_recommendations,
                *recommendation_set.program_recommendations,
                *recommendation_set.hypotheses,
                *recommendation_set.blocked_recommendations,
            )
            for citation in recommendation.nvidia_citations
        )
    )

    return HumanReviewBriefing(
        schema_version=HUMAN_REVIEW_SCHEMA_VERSION,
        run_id=recommendation_set.run_id,
        startup_identifier=recommendation_set.startup_identifier,
        status="ready_for_human_review",
        area_of_operation=_area_of_operation(profile),
        discoveries=discoveries,
        main_evidence=evidence_references,
        suspected_gaps=tuple(gap for gap in assessment.technical_gaps if gap.gap_type != UNKNOWN),
        commercial_opportunities=tuple(recommendation_set.program_recommendations),
        wrapper_risks=assessment.wrapper_dependency_risks,
        conflicts=conflicts,
        unknowns=unknowns,
        supported_recommendations=(
            *recommendation_set.technical_recommendations,
            *recommendation_set.program_recommendations,
        ),
        hypothesis_recommendations=recommendation_set.hypotheses,
        blocked_recommendations=recommendation_set.blocked_recommendations,
        review_reasons=review_reasons,
        pending_questions=pending_questions,
        evidence_references=evidence_references,
        citation_references=citation_references,
        next_action=recommendation_set.next_action,
        audit_reasons=_dedupe_reasons(
            review_reasons,
            _collection_audit_reasons(collection_quality),
            _conflict_audit_reasons(evidence_groups),
            recommendation_set.audit_reasons,
        ),
    )


def generate_briefing_narrative(
    *,
    briefing: ExecutiveBriefing | HumanReviewBriefing,
    llm_client: LLMClient,
    user_query: str = "",
    profile: StartupProfile | None = None,
    assessment: AINativeAssessment | None = None,
    recommendation_set: NVIDIARecommendationSet | None = None,
    retrievals: tuple[NVIDIAKnowledgeRetrieval, ...] = (),
) -> BriefingNarrative:
    """Generate an optional narrative draft from an existing briefing contract."""

    claims = _source_briefing_claims(briefing)
    request = LLMGenerationRequest(
        schema_version=LLM_REQUEST_SCHEMA_VERSION,
        purpose="briefing_narrative",
        system_prompt=(
            "Draft a concise narrative only from the supplied validated briefing claims. "
            "Do not add startup facts, NVIDIA facts, technologies, funding, customers, "
            "founders, priorities, or recommendations that are not in the source briefing. "
            "Preserve unknowns, risks, source references, claim types, and next action."
        ),
        user_prompt=_briefing_narrative_prompt(
            briefing,
            claims,
            user_query=user_query,
            profile=profile,
            assessment=assessment,
            recommendation_set=recommendation_set,
            retrievals=retrievals,
        ),
        structured_output_schema=BRIEFING_NARRATIVE_SCHEMA_VERSION,
        metadata={
            "run_id": briefing.run_id,
            "startup_identifier": briefing.startup_identifier,
            "source_briefing_schema_version": briefing.schema_version,
            "source_briefing_status": briefing.status,
            "claim_count": len(claims),
            "evidence_reference_count": len(briefing.evidence_references),
            "citation_reference_count": len(briefing.citation_references),
        },
    )
    response = llm_client.generate(request)
    (
        technical_gap_narrative,
        commercial_approach_narrative,
        narrative_text,
        safe_response,
        narrative_audit_reasons,
    ) = _safe_narrative_output(
        response=response,
        briefing=briefing,
        claims=claims,
        prompt=request.user_prompt,
    )

    return BriefingNarrative(
        schema_version=BRIEFING_NARRATIVE_SCHEMA_VERSION,
        run_id=briefing.run_id,
        startup_identifier=briefing.startup_identifier,
        source_briefing_schema_version=briefing.schema_version,
        source_briefing_status=briefing.status,
        technical_gap_narrative=technical_gap_narrative,
        commercial_approach_narrative=commercial_approach_narrative,
        narrative_text=narrative_text,
        claims=claims,
        unknowns=_source_briefing_unknowns(briefing, claims),
        risks=_source_briefing_risks(briefing),
        review_reasons=_source_briefing_review_reasons(briefing),
        pending_questions=briefing.pending_questions,
        evidence_references=briefing.evidence_references,
        citation_references=briefing.citation_references,
        next_action=briefing.next_action,
        llm_request=request,
        llm_response=safe_response,
        audit_reasons=_dedupe_reasons(
            ("llm_narrative_generated_from_validated_briefing",),
            narrative_audit_reasons,
            briefing.audit_reasons,
        ),
    )


def executive_briefing_to_dict(briefing: ExecutiveBriefing) -> dict[str, object]:
    """Convert an executive briefing to JSON-serializable data."""

    return _to_plain_data(briefing)


def human_review_briefing_to_dict(briefing: HumanReviewBriefing) -> dict[str, object]:
    """Convert a human review briefing to JSON-serializable data."""

    return _to_plain_data(briefing)


def briefing_narrative_to_dict(narrative: BriefingNarrative) -> dict[str, object]:
    """Convert a briefing narrative draft to JSON-serializable data."""

    return _to_plain_data(narrative)


def _profile_claims(profile: StartupProfile) -> tuple[BriefingClaim, ...]:
    claims: list[BriefingClaim] = []
    for field_name in ("company_name", "official_site", "company_summary", "sector", "product", "ai_signals"):
        field_value = getattr(profile, field_name)
        if not isinstance(field_value, ProfileField) or field_value.value == UNKNOWN:
            continue
        claim_type = "inferred" if field_value.claim_source.value == "inferred" else "observed"
        claims.append(
            BriefingClaim(
                text=f"{field_name}: {field_value.value}",
                claim_type=claim_type,
                section="profile",
                confidence=0.8 if claim_type == "inferred" else 1.0,
                evidence_references=field_value.evidences,
                citation_references=(),
            )
        )
    return tuple(claims)


def _diagnosis_claim(assessment: AINativeAssessment) -> BriefingClaim:
    return BriefingClaim(
        text=_diagnosis_text(assessment),
        claim_type="inferred",
        section="diagnosis",
        confidence=assessment.confidence,
        evidence_references=assessment.evidences,
        citation_references=(),
    )


def _opportunity_claim(recommendation_set: NVIDIARecommendationSet) -> BriefingClaim:
    return BriefingClaim(
        text=(
            "Final NVIDIA opportunity priority: "
            f"{recommendation_set.final_nvidia_opportunity_priority}."
        ),
        claim_type="inferred",
        section="opportunity",
        confidence=0.8 if recommendation_set.quality.ready_for_briefing else 0.4,
        evidence_references=(),
        citation_references=(),
        reason="Priority is calculated by Recommendation, not AI-Native Assessment.",
    )


def _risk_claims(assessment: AINativeAssessment) -> tuple[BriefingClaim, ...]:
    claims: list[BriefingClaim] = []
    for risk in assessment.wrapper_dependency_risks:
        claims.append(
            BriefingClaim(
                text=f"{risk.risk_type}: {risk.rationale}",
                claim_type="inferred",
                section="risks",
                confidence=risk.confidence,
                evidence_references=risk.evidences,
                citation_references=(),
                reason=f"severity:{risk.severity}",
            )
        )
    return tuple(claims)


def _recommended_claims(recommendation_set: NVIDIARecommendationSet) -> tuple[BriefingClaim, ...]:
    claims: list[BriefingClaim] = []
    for recommendation in recommendation_set.technical_recommendations:
        claims.append(
            BriefingClaim(
                text=(
                    f"Recommend {recommendation.nvidia_technology} for "
                    f"{recommendation.gap.gap_type}: {recommendation.technical_rationale}"
                ),
                claim_type="recommended",
                section="recommendations",
                confidence=recommendation.gap.confidence,
                evidence_references=recommendation.startup_evidences,
                citation_references=recommendation.nvidia_citations,
                reason="supported_technical_recommendation",
            )
        )
    for recommendation in recommendation_set.program_recommendations:
        claims.append(
            BriefingClaim(
                text=(
                    f"Recommend {recommendation.nvidia_program} for "
                    f"{recommendation.opportunity.opportunity_type}: "
                    f"{recommendation.commercial_rationale}"
                ),
                claim_type="recommended",
                section="recommendations",
                confidence=recommendation.opportunity.confidence,
                evidence_references=recommendation.startup_evidences,
                citation_references=recommendation.nvidia_citations,
                reason="supported_program_recommendation",
            )
        )
    return tuple(claims)


def _unknown_claims(profile: StartupProfile) -> tuple[BriefingClaim, ...]:
    claims: list[BriefingClaim] = []
    for field_name in UNKNOWN_PROFILE_FIELDS:
        field_value = getattr(profile, field_name)
        if isinstance(field_value, ProfileField) and field_value.value == UNKNOWN:
            claims.append(
                BriefingClaim(
                    text=f"{field_name} is unknown from collected public evidence.",
                    claim_type="unknown",
                    section="unknowns",
                    confidence=0.0,
                    evidence_references=(),
                    citation_references=(),
                    reason="missing_startup_profile_field",
                )
            )
    return tuple(claims)


def _pending_questions(
    profile: StartupProfile,
    assessment: AINativeAssessment,
) -> tuple[PendingQuestion, ...]:
    questions: list[PendingQuestion] = []
    for field_name in UNKNOWN_PROFILE_FIELDS:
        field_value = getattr(profile, field_name)
        if isinstance(field_value, ProfileField) and field_value.value == UNKNOWN:
            questions.append(
                PendingQuestion(
                    field_name=field_name,
                    question=_question_for_unknown_field(field_name),
                    priority="complementary",
                    reason="missing_startup_profile_field",
                )
            )
    for field_name in assessment.insufficient_evidence_fields:
        questions.append(
            PendingQuestion(
                field_name=field_name,
                question=f"Validate public evidence for {field_name}.",
                priority="critical",
                reason="insufficient_assessment_evidence",
            )
        )
    return tuple(dict.fromkeys(questions))


def _human_review_pending_questions(
    *,
    profile: StartupProfile,
    assessment: AINativeAssessment,
    recommendation_set: NVIDIARecommendationSet,
    conflicts: tuple[FieldEvidenceGroup, ...],
    collection_quality: CollectionQualitySummary,
) -> tuple[PendingQuestion, ...]:
    questions = list(_pending_questions(profile, assessment))

    if not collection_quality.ready_for_evaluation:
        questions.append(
            PendingQuestion(
                field_name="collection_quality",
                question="Which public sources should be collected before recommendation can be trusted?",
                priority="critical",
                reason="collection_quality_requires_validation",
            )
        )

    for recommendation in recommendation_set.hypotheses:
        questions.append(
            PendingQuestion(
                field_name=_recommendation_target_field_name(recommendation),
                question=_recommendation_validation_question(recommendation, blocked=False),
                priority="critical",
                reason=_recommendation_validation_reason(recommendation, blocked=False),
            )
        )

    for recommendation in recommendation_set.blocked_recommendations:
        questions.append(
            PendingQuestion(
                field_name=_recommendation_target_field_name(recommendation),
                question=_recommendation_validation_question(recommendation, blocked=True),
                priority="critical",
                reason=_recommendation_validation_reason(recommendation, blocked=True),
            )
        )

    for risk in assessment.wrapper_dependency_risks:
        priority = "critical" if risk.severity == "high" else "complementary"
        questions.append(
            PendingQuestion(
                field_name=risk.risk_type,
                question=(
                    "Validate dependency on external APIs, proprietary data, and production inference "
                    "before prioritizing NVIDIA outreach."
                ),
                priority=priority,
                reason="wrapper_risk_requires_validation",
            )
        )

    for conflict in conflicts:
        questions.append(
            PendingQuestion(
                field_name=conflict.field_name,
                question=f"Resolve conflicting public evidence for {conflict.field_name}.",
                priority="critical",
                reason="conflicting_evidence_requires_validation",
            )
        )

    return tuple(dict.fromkeys(questions))


def _human_review_reasons(
    *,
    collection_quality: CollectionQualitySummary,
    evidence_groups: tuple[FieldEvidenceGroup, ...],
    assessment: AINativeAssessment,
    recommendation_set: NVIDIARecommendationSet,
) -> tuple[str, ...]:
    reasons: list[str] = list(recommendation_set.quality.reasons)

    if _is_low_signal(collection_quality, assessment):
        reasons.append("low_signal_requires_human_review")
    if any(risk.severity == "high" for risk in assessment.wrapper_dependency_risks):
        reasons.append("high_wrapper_risk_requires_human_review")
    if any(group.has_conflict for group in evidence_groups):
        reasons.append("conflicting_startup_evidence")

    for recommendation in (*recommendation_set.hypotheses, *recommendation_set.blocked_recommendations):
        reasons.extend(recommendation.selection_reasons)

    return tuple(dict.fromkeys(reasons))


def _is_low_signal(
    collection_quality: CollectionQualitySummary,
    assessment: AINativeAssessment,
) -> bool:
    return (
        not collection_quality.ready_for_evaluation
        or not assessment.ready_for_recommendation
        or assessment.confidence < 0.5
        or assessment.classification == "insufficient_evidence"
    )


def _unknown_field_names(
    profile: StartupProfile,
    collection_quality: CollectionQualitySummary,
    assessment: AINativeAssessment,
) -> tuple[str, ...]:
    unknowns: list[str] = []
    for field_name in UNKNOWN_PROFILE_FIELDS:
        field_value = getattr(profile, field_name)
        if isinstance(field_value, ProfileField) and field_value.value == UNKNOWN:
            unknowns.append(field_name)
    unknowns.extend(_collection_unknown_field_names(collection_quality))
    unknowns.extend(assessment.insufficient_evidence_fields)
    return tuple(dict.fromkeys(unknowns))


def _area_of_operation(profile: StartupProfile) -> str:
    if isinstance(profile.sector, ProfileField) and profile.sector.value != UNKNOWN:
        return profile.sector.value
    return UNKNOWN


def _question_for_unknown_field(field_name: str) -> str:
    questions = {
        "funding": "What is the startup's current funding stage or financing context?",
        "customers": "Which customer segments or named customers can be validated?",
        "founders": "Who are the founders and technical decision makers?",
        "technologies_used": "Which AI infrastructure, model serving, and data stack are used in production?",
    }
    return questions[field_name]


def _executive_summary(
    startup_identifier: str,
    assessment: AINativeAssessment,
    recommendation_set: NVIDIARecommendationSet,
) -> str:
    if recommendation_set.technical_recommendations:
        top_recommendation = recommendation_set.technical_recommendations[0]
        return (
            f"{startup_identifier} is classified as {assessment.classification} "
            f"and has a supported NVIDIA recommendation: "
            f"{top_recommendation.nvidia_technology} for {top_recommendation.gap.gap_type}."
        )
    if recommendation_set.program_recommendations:
        top_recommendation = recommendation_set.program_recommendations[0]
        return (
            f"{startup_identifier} is classified as {assessment.classification} "
            f"and has a supported NVIDIA program recommendation: "
            f"{top_recommendation.nvidia_program} for "
            f"{top_recommendation.opportunity.opportunity_type}."
        )
    return (
        f"{startup_identifier} is classified as {assessment.classification}, "
        "but no supported NVIDIA recommendation is ready for use."
    )


def _diagnosis_text(assessment: AINativeAssessment) -> str:
    return (
        f"AI-native assessment classified the startup as {assessment.classification} "
        f"with confidence {assessment.confidence:.2f}."
    )


def _risk_texts(assessment: AINativeAssessment) -> tuple[str, ...]:
    return tuple(f"{risk.risk_type}: {risk.rationale}" for risk in assessment.wrapper_dependency_risks)


def _collection_audit_reasons(collection_quality: CollectionQualitySummary) -> tuple[str, ...]:
    if collection_quality.ready_for_evaluation:
        return ("collection_quality_ready",)
    return tuple(collection_quality.readiness_reasons)


def _conflict_audit_reasons(evidence_groups: tuple[FieldEvidenceGroup, ...]) -> tuple[str, ...]:
    return tuple(f"conflict:{group.field_name}" for group in evidence_groups if group.has_conflict)


def _dedupe_evidences(evidences: tuple[FieldEvidence, ...]) -> tuple[FieldEvidence, ...]:
    unique: dict[tuple[str, str, str], FieldEvidence] = {}
    for evidence in evidences:
        unique[(evidence.url, evidence.snippet, evidence.source_type)] = evidence
    return tuple(unique.values())


def _dedupe_citations(citations: tuple[NVIDIACitation, ...]) -> tuple[NVIDIACitation, ...]:
    unique: dict[tuple[str, str, str], NVIDIACitation] = {}
    for citation in citations:
        unique[(citation.document_id, citation.chunk_id, citation.source_url)] = citation
    return tuple(unique.values())


def _dedupe_reasons(*reason_groups: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(reason for group in reason_groups for reason in group))


def _recommendation_target_field_name(recommendation: BriefableRecommendation) -> str:
    if isinstance(recommendation, NVIDIATechnicalRecommendation):
        return recommendation.gap.gap_type
    return recommendation.opportunity.opportunity_type


def _recommendation_validation_question(
    recommendation: BriefableRecommendation,
    *,
    blocked: bool,
) -> str:
    if isinstance(recommendation, NVIDIATechnicalRecommendation):
        if blocked:
            return (
                "Collect or validate startup-side evidence for the "
                f"{recommendation.gap.gap_type} gap before outreach."
            )
        return (
            "Validate whether the suspected "
            f"{recommendation.gap.gap_type} gap is real and which NVIDIA fit is supportable."
        )

    if blocked:
        return (
            "Collect or validate startup-side evidence for the "
            f"{recommendation.opportunity.opportunity_type} commercial opportunity before outreach."
        )
    return (
        "Validate whether the suspected "
        f"{recommendation.opportunity.opportunity_type} commercial opportunity is real and "
        "which NVIDIA program fit is supportable."
    )


def _recommendation_validation_reason(
    recommendation: BriefableRecommendation,
    *,
    blocked: bool,
) -> str:
    if isinstance(recommendation, NVIDIATechnicalRecommendation):
        return (
            "blocked_recommendation_requires_validation"
            if blocked
            else "recommendation_hypothesis_requires_validation"
        )
    return (
        "program_recommendation_blocked_requires_validation"
        if blocked
        else "program_recommendation_hypothesis_requires_validation"
    )


def _collection_unknown_field_names(collection_quality: CollectionQualitySummary) -> tuple[str, ...]:
    names: list[str] = []
    for item in collection_quality.unknown_fields:
        if isinstance(item, tuple) and item:
            names.append(str(item[0]))
            continue
        names.append(str(item))
    return tuple(name for name in names if name)


def _source_briefing_claims(
    briefing: ExecutiveBriefing | HumanReviewBriefing,
) -> tuple[BriefingClaim, ...]:
    if isinstance(briefing, ExecutiveBriefing):
        return briefing.claims
    return briefing.discoveries


def _source_briefing_unknowns(
    briefing: ExecutiveBriefing | HumanReviewBriefing,
    claims: tuple[BriefingClaim, ...],
) -> tuple[str, ...]:
    if isinstance(briefing, HumanReviewBriefing):
        return briefing.unknowns
    return tuple(claim.text for claim in claims if claim.claim_type == "unknown")


def _source_briefing_risks(briefing: ExecutiveBriefing | HumanReviewBriefing) -> tuple[str, ...]:
    if isinstance(briefing, ExecutiveBriefing):
        return briefing.risks
    return tuple(f"{risk.risk_type}: {risk.rationale}" for risk in briefing.wrapper_risks)


def _source_briefing_review_reasons(
    briefing: ExecutiveBriefing | HumanReviewBriefing,
) -> tuple[str, ...]:
    if isinstance(briefing, HumanReviewBriefing):
        return briefing.review_reasons
    return ()


def _briefing_narrative_prompt(
    briefing: ExecutiveBriefing | HumanReviewBriefing,
    claims: tuple[BriefingClaim, ...],
    *,
    user_query: str = "",
    profile: StartupProfile | None = None,
    assessment: AINativeAssessment | None = None,
    recommendation_set: NVIDIARecommendationSet | None = None,
    retrievals: tuple[NVIDIAKnowledgeRetrieval, ...] = (),
) -> str:
    lines = [
        f"source_schema: {briefing.schema_version}",
        f"source_status: {briefing.status}",
        f"startup_identifier: {briefing.startup_identifier}",
        f"next_action: {briefing.next_action}",
        f"original_user_query: {user_query.strip() or UNKNOWN}",
        "required_output:",
        "technical_gap_narrative: <technical gap narrative using only the context below>",
        "commercial_approach_narrative: <commercial approach narrative using only the context below>",
        "validated_startup_profile_claims:",
        *_profile_prompt_lines(profile, claims),
        "assessment:",
        *_assessment_prompt_lines(assessment),
        "recommendation_set:",
        *_recommendation_prompt_lines(recommendation_set),
        "nvidia_citation_references:",
        *_citation_prompt_lines(briefing.citation_references),
        "cited_nvidia_rag_chunks:",
        *_cited_rag_chunk_prompt_lines(retrievals, briefing.citation_references),
        "source_briefing_claims:",
    ]
    for index, claim in enumerate(claims, start=1):
        lines.append(
            " | ".join(
                (
                    f"claim_id: claim-{index}",
                    f"type: {claim.claim_type}",
                    f"section: {claim.section}",
                    f"confidence: {claim.confidence:.2f}",
                    f"evidence_refs: {_evidence_reference_text(claim.evidence_references)}",
                    f"citation_refs: {_citation_reference_text(claim.citation_references)}",
                    f"text: {claim.text}",
                )
            )
        )

    unknowns = _source_briefing_unknowns(briefing, claims)
    if unknowns:
        lines.append("unknowns:")
        lines.extend(f"- {unknown}" for unknown in unknowns)

    risks = _source_briefing_risks(briefing)
    if risks:
        lines.append("risks:")
        lines.extend(f"- {risk}" for risk in risks)

    review_reasons = _source_briefing_review_reasons(briefing)
    if review_reasons:
        lines.append("review_reasons:")
        lines.extend(f"- {reason}" for reason in review_reasons)

    if briefing.pending_questions:
        lines.append("pending_questions:")
        lines.extend(
            f"- {question.priority}: {question.field_name}: {question.question}"
            for question in briefing.pending_questions
        )

    return "\n".join(lines)


def _profile_prompt_lines(
    profile: StartupProfile | None,
    claims: tuple[BriefingClaim, ...],
) -> tuple[str, ...]:
    if profile is None:
        profile_claims = tuple(claim for claim in claims if claim.section == "profile")
        if not profile_claims:
            return ("- unknown",)
        return tuple(
            (
                f"- {claim.claim_type}: {claim.text} | "
                f"evidence_refs: {_evidence_reference_text(claim.evidence_references)}"
            )
            for claim in profile_claims
        )

    lines: list[str] = []
    for field_name in (
        "company_name",
        "official_site",
        "company_summary",
        "sector",
        "product",
        "ai_signals",
        "technologies_used",
        "customers",
        "funding",
        "founders",
    ):
        field_value = getattr(profile, field_name)
        if not isinstance(field_value, ProfileField):
            continue
        lines.append(
            (
                f"- {field_name}: {field_value.value} | "
                f"claim_source: {field_value.claim_source.value} | "
                f"evidence_refs: {_evidence_reference_text(field_value.evidences)}"
            )
        )
    return tuple(lines) or ("- unknown",)


def _assessment_prompt_lines(assessment: AINativeAssessment | None) -> tuple[str, ...]:
    if assessment is None:
        return ("- unknown",)

    lines = [
        f"- schema_version: {assessment.schema_version}",
        f"- run_id: {assessment.run_id}",
        f"- classification: {assessment.classification}",
        f"- confidence: {assessment.confidence:.2f}",
        f"- ready_for_recommendation: {assessment.ready_for_recommendation}",
        f"- nvidia_opportunity_urgency: {assessment.nvidia_opportunity_urgency}",
        f"- diagnostic_reasons: {','.join(assessment.diagnostic_quality.reasons) or 'none'}",
    ]
    for gap in assessment.technical_gaps:
        lines.append(
            (
                f"- technical_gap: {gap.gap_type} | severity: {gap.severity} | "
                f"confidence: {gap.confidence:.2f} | description: {gap.description} | "
                f"evidence_refs: {_evidence_reference_text(gap.evidences)}"
            )
        )
    for risk in assessment.wrapper_dependency_risks:
        lines.append(
            (
                f"- wrapper_risk: {risk.risk_type} | severity: {risk.severity} | "
                f"confidence: {risk.confidence:.2f} | rationale: {risk.rationale} | "
                f"evidence_refs: {_evidence_reference_text(risk.evidences)}"
            )
        )
    return tuple(lines)


def _recommendation_prompt_lines(
    recommendation_set: NVIDIARecommendationSet | None,
) -> tuple[str, ...]:
    if recommendation_set is None:
        return ("- unknown",)

    lines = [
        f"- schema_version: {recommendation_set.schema_version}",
        f"- run_id: {recommendation_set.run_id}",
        f"- startup_identifier: {recommendation_set.startup_identifier}",
        f"- corpus_version: {recommendation_set.corpus_version}",
        f"- final_nvidia_opportunity_priority: {recommendation_set.final_nvidia_opportunity_priority}",
        f"- next_action: {recommendation_set.next_action}",
        f"- ready_for_briefing: {recommendation_set.quality.ready_for_briefing}",
        f"- quality_reasons: {','.join(recommendation_set.quality.reasons) or 'none'}",
    ]
    for recommendation in recommendation_set.technical_recommendations:
        lines.append(
            (
                f"- supported_technical_recommendation: {recommendation.nvidia_technology} | "
                f"gap: {recommendation.gap.gap_type} | rationale: {recommendation.technical_rationale} | "
                f"startup_evidence_refs: {_evidence_reference_text(recommendation.startup_evidences)} | "
                f"citation_refs: {_citation_reference_text(recommendation.nvidia_citations)}"
            )
        )
    for recommendation in recommendation_set.program_recommendations:
        lines.append(_program_recommendation_prompt_line("supported_program_recommendation", recommendation))
    for recommendation in recommendation_set.hypotheses:
        lines.append(_recommendation_prompt_line("hypothesis_recommendation", recommendation))
    for recommendation in recommendation_set.blocked_recommendations:
        lines.append(_recommendation_prompt_line("blocked_recommendation", recommendation))
    return tuple(lines)


def _recommendation_prompt_line(prefix: str, recommendation: BriefableRecommendation) -> str:
    if isinstance(recommendation, NVIDIATechnicalRecommendation):
        return (
            f"- {prefix}: {recommendation.nvidia_technology} | "
            f"gap: {recommendation.gap.gap_type} | rationale: {recommendation.technical_rationale} | "
            f"startup_evidence_refs: {_evidence_reference_text(recommendation.startup_evidences)} | "
            f"citation_refs: {_citation_reference_text(recommendation.nvidia_citations)}"
        )
    return _program_recommendation_prompt_line(prefix, recommendation)


def _program_recommendation_prompt_line(
    prefix: str,
    recommendation: NVIDIAProgramRecommendation,
) -> str:
    return (
        f"- {prefix}: {recommendation.nvidia_program} | "
        f"opportunity: {recommendation.opportunity.opportunity_type} | "
        f"rationale: {recommendation.commercial_rationale} | "
        f"startup_evidence_refs: {_evidence_reference_text(recommendation.startup_evidences)} | "
        f"citation_refs: {_citation_reference_text(recommendation.nvidia_citations)}"
    )


def _citation_prompt_lines(citations: tuple[NVIDIACitation, ...]) -> tuple[str, ...]:
    if not citations:
        return ("- none",)
    return tuple(
        (
            f"- document_id: {citation.document_id} | chunk_id: {citation.chunk_id} | "
            f"title: {citation.document_title} | source_url: {citation.source_url}"
        )
        for citation in citations
    )


def _cited_rag_chunk_prompt_lines(
    retrievals: tuple[NVIDIAKnowledgeRetrieval, ...],
    citations: tuple[NVIDIACitation, ...],
) -> tuple[str, ...]:
    cited_chunk_ids = {citation.chunk_id for citation in citations}
    if not retrievals or not cited_chunk_ids:
        return ("- none",)

    lines: list[str] = []
    for retrieval in retrievals:
        for result in retrieval.results:
            if result.citation.chunk_id not in cited_chunk_ids:
                continue
            lines.append(
                (
                    f"- corpus_version: {retrieval.corpus_version} | "
                    f"document_id: {result.citation.document_id} | "
                    f"chunk_id: {result.citation.chunk_id} | "
                    f"source_url: {result.citation.source_url} | "
                    f"text: {result.chunk.text}"
                )
            )
    return tuple(lines) or ("- none",)


def _evidence_reference_text(evidences: tuple[FieldEvidence, ...]) -> str:
    if not evidences:
        return "none"
    return ",".join(f"{evidence.source_type}:{evidence.url}" for evidence in evidences)


def _citation_reference_text(citations: tuple[NVIDIACitation, ...]) -> str:
    if not citations:
        return "none"
    return ",".join(f"{citation.document_id}:{citation.chunk_id}" for citation in citations)


_NARRATIVE_CONNECTIVE_TERMS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "based",
        "briefing",
        "but",
        "by",
        "claim",
        "claims",
        "evidence",
        "for",
        "from",
        "has",
        "have",
        "in",
        "is",
        "it",
        "next",
        "no",
        "of",
        "on",
        "or",
        "public",
        "recommend",
        "recommendation",
        "review",
        "risk",
        "should",
        "source",
        "startup",
        "that",
        "the",
        "this",
        "to",
        "unknown",
        "use",
        "validated",
        "with",
    }
)


def _safe_narrative_output(
    *,
    response: LLMGenerationResponse,
    briefing: ExecutiveBriefing | HumanReviewBriefing,
    claims: tuple[BriefingClaim, ...],
    prompt: str,
) -> tuple[str, str, str, LLMGenerationResponse, tuple[str, ...]]:
    unsupported_terms = _unsupported_narrative_terms(response.content, prompt)
    if unsupported_terms:
        technical_gap_narrative, commercial_approach_narrative = _fallback_narrative_sections(briefing, claims)
        return (
            technical_gap_narrative,
            commercial_approach_narrative,
            _combined_narrative_text(technical_gap_narrative, commercial_approach_narrative),
            _llm_response_without_unsafe_content(
                response,
                rejection_reason="unsupported_terms",
                unsupported_terms=unsupported_terms,
            ),
            ("llm_narrative_rejected_unsupported_terms",),
        )
    if not response.content.strip():
        technical_gap_narrative, commercial_approach_narrative = _fallback_narrative_sections(briefing, claims)
        return (
            technical_gap_narrative,
            commercial_approach_narrative,
            _combined_narrative_text(technical_gap_narrative, commercial_approach_narrative),
            _llm_response_without_unsafe_content(
                response,
                rejection_reason="empty_response",
                unsupported_terms=(),
            ),
            ("llm_narrative_rejected_empty_response",),
        )

    sections = _split_narrative_sections(response.content)
    if sections is None:
        technical_gap_narrative, commercial_approach_narrative = _fallback_narrative_sections(briefing, claims)
        return (
            technical_gap_narrative,
            commercial_approach_narrative,
            _combined_narrative_text(technical_gap_narrative, commercial_approach_narrative),
            _llm_response_without_unsafe_content(
                response,
                rejection_reason="missing_required_sections",
                unsupported_terms=(),
            ),
            ("llm_narrative_rejected_missing_required_sections",),
        )

    technical_gap_narrative, commercial_approach_narrative = sections
    return (
        technical_gap_narrative,
        commercial_approach_narrative,
        _combined_narrative_text(technical_gap_narrative, commercial_approach_narrative),
        response,
        ("llm_narrative_accepted",),
    )


def _split_narrative_sections(content: str) -> tuple[str, str] | None:
    sections: dict[str, list[str]] = {
        "technical_gap_narrative": [],
        "commercial_approach_narrative": [],
    }
    current_section = ""
    for line in content.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if lowered.startswith("technical_gap_narrative:"):
            current_section = "technical_gap_narrative"
            sections[current_section].append(stripped.split(":", 1)[1].strip())
            continue
        if lowered.startswith("commercial_approach_narrative:"):
            current_section = "commercial_approach_narrative"
            sections[current_section].append(stripped.split(":", 1)[1].strip())
            continue
        if current_section and stripped:
            sections[current_section].append(stripped)

    technical_gap_narrative = " ".join(sections["technical_gap_narrative"]).strip()
    commercial_approach_narrative = " ".join(sections["commercial_approach_narrative"]).strip()
    if not technical_gap_narrative or not commercial_approach_narrative:
        return None
    return technical_gap_narrative, commercial_approach_narrative


def _unsupported_narrative_terms(content: str, prompt: str) -> tuple[str, ...]:
    if not content.strip():
        return ()
    allowed_terms = set(_significant_terms(prompt))
    allowed_terms.update(_NARRATIVE_CONNECTIVE_TERMS)
    unsupported = tuple(
        dict.fromkeys(term for term in _significant_terms(content) if term not in allowed_terms)
    )
    return unsupported


def _significant_terms(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9_]+", text.lower()))


def _llm_response_without_unsafe_content(
    response: LLMGenerationResponse,
    *,
    rejection_reason: str,
    unsupported_terms: tuple[str, ...],
) -> LLMGenerationResponse:
    metadata = dict(response.metadata)
    metadata.update(
        {
            "content_rejected": True,
            "rejection_reason": rejection_reason,
            "unsupported_terms": unsupported_terms,
        }
    )
    return LLMGenerationResponse(
        schema_version=response.schema_version,
        request_purpose=response.request_purpose,
        provider=response.provider,
        model=response.model,
        model_version=response.model_version,
        content="",
        structured_output_schema=response.structured_output_schema,
        finish_reason=response.finish_reason,
        usage=dict(response.usage),
        metadata=metadata,
    )


def _fallback_narrative_text(
    briefing: ExecutiveBriefing | HumanReviewBriefing,
    claims: tuple[BriefingClaim, ...],
) -> str:
    technical_gap_narrative, commercial_approach_narrative = _fallback_narrative_sections(briefing, claims)
    return _combined_narrative_text(technical_gap_narrative, commercial_approach_narrative)


def _fallback_narrative_sections(
    briefing: ExecutiveBriefing | HumanReviewBriefing,
    claims: tuple[BriefingClaim, ...],
) -> tuple[str, str]:
    lines: list[str] = []
    if isinstance(briefing, ExecutiveBriefing):
        lines.append(briefing.executive_summary)
    else:
        review_reasons = ", ".join(briefing.review_reasons) or "review required"
        lines.append(
            f"Human review briefing for {briefing.startup_identifier}: {review_reasons}."
        )
    lines.extend(f"{claim.claim_type}: {claim.text}" for claim in claims)
    lines.extend(f"unknown: {unknown}" for unknown in _source_briefing_unknowns(briefing, claims))
    lines.extend(f"risk: {risk}" for risk in _source_briefing_risks(briefing))
    technical_gap_narrative = " ".join(lines)

    commercial_lines: list[str] = []
    if isinstance(briefing, ExecutiveBriefing):
        commercial_lines.append(f"opportunity: {briefing.opportunity}")
    else:
        commercial_lines.extend(f"review_reason: {reason}" for reason in briefing.review_reasons)
    commercial_lines.extend(
        f"pending_question: {question.priority}: {question.field_name}: {question.question}"
        for question in briefing.pending_questions
    )
    commercial_lines.append(f"next_action: {briefing.next_action}")
    return technical_gap_narrative, " ".join(commercial_lines)


def _combined_narrative_text(
    technical_gap_narrative: str,
    commercial_approach_narrative: str,
) -> str:
    return (
        f"technical_gap_narrative: {technical_gap_narrative} "
        f"commercial_approach_narrative: {commercial_approach_narrative}"
    )


def _to_plain_data(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _to_plain_data(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {key: _to_plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain_data(item) for item in value]
    return value
