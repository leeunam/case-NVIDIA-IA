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
from nvidia_startup_intel.framework_adapters import (
    LLMClient,
    LLMGenerationRequest,
    LLMGenerationResponse,
    LLM_REQUEST_SCHEMA_VERSION,
)
from nvidia_startup_intel.nvidia_knowledge import NVIDIACitation
from nvidia_startup_intel.nvidia_recommendation import NVIDIARecommendationSet, NVIDIATechnicalRecommendation
from nvidia_startup_intel.search_params import UNKNOWN
from nvidia_startup_intel.startup_profile import FieldEvidence, ProfileField, StartupProfile


SCHEMA_VERSION = "executive_briefing.v1"
HUMAN_REVIEW_SCHEMA_VERSION = "human_review_briefing.v1"
BRIEFING_NARRATIVE_SCHEMA_VERSION = "briefing_narrative.v1"
UNKNOWN_PROFILE_FIELDS = ("funding", "customers", "founders", "technologies_used")


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
    supported_recommendations: tuple[NVIDIATechnicalRecommendation, ...]
    hypothesis_recommendations: tuple[NVIDIATechnicalRecommendation, ...]
    blocked_recommendations: tuple[NVIDIATechnicalRecommendation, ...]
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
        supported_recommendations=recommendation_set.technical_recommendations,
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
        user_prompt=_briefing_narrative_prompt(briefing, claims),
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
    narrative_text, safe_response, narrative_audit_reasons = _safe_narrative_output(
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
                field_name=recommendation.gap.gap_type,
                question=(
                    "Validate whether the suspected "
                    f"{recommendation.gap.gap_type} gap is real and which NVIDIA fit is supportable."
                ),
                priority="critical",
                reason="recommendation_hypothesis_requires_validation",
            )
        )

    for recommendation in recommendation_set.blocked_recommendations:
        questions.append(
            PendingQuestion(
                field_name=recommendation.gap.gap_type,
                question=(
                    "Collect or validate startup-side evidence for the "
                    f"{recommendation.gap.gap_type} gap before outreach."
                ),
                priority="critical",
                reason="blocked_recommendation_requires_validation",
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
    unknowns.extend(collection_quality.unknown_fields)
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
) -> str:
    lines = [
        f"source_schema: {briefing.schema_version}",
        f"source_status: {briefing.status}",
        f"startup_identifier: {briefing.startup_identifier}",
        f"next_action: {briefing.next_action}",
        "claims:",
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
) -> tuple[str, LLMGenerationResponse, tuple[str, ...]]:
    unsupported_terms = _unsupported_narrative_terms(response.content, prompt)
    if unsupported_terms:
        return (
            _fallback_narrative_text(briefing, claims),
            _llm_response_without_unsafe_content(
                response,
                rejection_reason="unsupported_terms",
                unsupported_terms=unsupported_terms,
            ),
            ("llm_narrative_rejected_unsupported_terms",),
        )
    if not response.content.strip():
        return (
            _fallback_narrative_text(briefing, claims),
            _llm_response_without_unsafe_content(
                response,
                rejection_reason="empty_response",
                unsupported_terms=(),
            ),
            ("llm_narrative_rejected_empty_response",),
        )
    return response.content, response, ("llm_narrative_accepted",)


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
    lines.append(f"next_action: {briefing.next_action}")
    return " ".join(lines)


def _to_plain_data(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _to_plain_data(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {key: _to_plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain_data(item) for item in value]
    return value
