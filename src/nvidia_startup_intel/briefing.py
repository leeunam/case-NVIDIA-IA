"""Deterministic executive briefing contracts.

The first briefing slice summarizes existing structured artifacts. It does not
call LLMs, retrievers, network services, or workflow frameworks.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass

from nvidia_startup_intel.ai_native_assessment import AINativeAssessment, TechnicalGap, WrapperDependencyRisk
from nvidia_startup_intel.collection_quality import CollectionQualitySummary
from nvidia_startup_intel.evidence import FieldEvidenceGroup
from nvidia_startup_intel.nvidia_knowledge import NVIDIACitation
from nvidia_startup_intel.nvidia_recommendation import NVIDIARecommendationSet, NVIDIATechnicalRecommendation
from nvidia_startup_intel.search_params import UNKNOWN
from nvidia_startup_intel.startup_profile import FieldEvidence, ProfileField, StartupProfile


SCHEMA_VERSION = "executive_briefing.v1"
HUMAN_REVIEW_SCHEMA_VERSION = "human_review_briefing.v1"
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
        audit_reasons=(
            *recommendation_set.quality.reasons,
            *_collection_audit_reasons(collection_quality),
            *_conflict_audit_reasons(evidence_groups),
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
        audit_reasons=(
            *review_reasons,
            *_collection_audit_reasons(collection_quality),
            *_conflict_audit_reasons(evidence_groups),
            *recommendation_set.audit_reasons,
        ),
    )


def executive_briefing_to_dict(briefing: ExecutiveBriefing) -> dict[str, object]:
    """Convert an executive briefing to JSON-serializable data."""

    return _to_plain_data(briefing)


def human_review_briefing_to_dict(briefing: HumanReviewBriefing) -> dict[str, object]:
    """Convert a human review briefing to JSON-serializable data."""

    return _to_plain_data(briefing)


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


def _to_plain_data(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _to_plain_data(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {key: _to_plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain_data(item) for item in value]
    return value
