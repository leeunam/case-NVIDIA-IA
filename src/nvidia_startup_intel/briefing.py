"""Deterministic executive briefing contracts.

The first briefing slice summarizes existing structured artifacts. It does not
call LLMs, retrievers, network services, or workflow frameworks.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass

from nvidia_startup_intel.ai_native_assessment import AINativeAssessment
from nvidia_startup_intel.collection_quality import CollectionQualitySummary
from nvidia_startup_intel.evidence import FieldEvidenceGroup
from nvidia_startup_intel.nvidia_knowledge import NVIDIACitation
from nvidia_startup_intel.nvidia_recommendation import NVIDIARecommendationSet
from nvidia_startup_intel.search_params import UNKNOWN
from nvidia_startup_intel.startup_profile import FieldEvidence, ProfileField, StartupProfile


SCHEMA_VERSION = "executive_briefing.v1"
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


def executive_briefing_to_dict(briefing: ExecutiveBriefing) -> dict[str, object]:
    """Convert an executive briefing to JSON-serializable data."""

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
