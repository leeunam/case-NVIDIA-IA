"""Deterministic AI-native maturity assessment.

This module consumes the scraping MVP contracts and produces an auditable
diagnostic without calling search, scraping, LLMs, RAG, or external services.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum

from nvidia_startup_intel.collection_quality import CollectionQualitySummary
from nvidia_startup_intel.evidence import FieldEvidenceGroup
from nvidia_startup_intel.normalization import normalize_text
from nvidia_startup_intel.search_params import UNKNOWN
from nvidia_startup_intel.startup_profile import FieldEvidence, ProfileField, StartupProfile


SCHEMA_VERSION = "ai_native_assessment.v1"


class Classification(StrEnum):
    AI_NATIVE = "ai_native"
    AI_ENABLED = "ai_enabled"
    NON_AI = "non_ai"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class OpportunityUrgency(StrEnum):
    URGENT = "urgent"
    MEDIUM = "medium"
    LOW = "low"
    HUMAN_REVIEW = "human_review"


class AssessmentStatus(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    UNKNOWN = UNKNOWN
    CONFLICT = "conflict"


class Severity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = UNKNOWN


@dataclass(frozen=True)
class CriterionResult:
    criterion: str
    status: str
    confidence: float
    rationale: str
    evidences: tuple[FieldEvidence, ...]


@dataclass(frozen=True)
class PositiveSignal:
    signal_type: str
    description: str
    confidence: float
    evidences: tuple[FieldEvidence, ...]


@dataclass(frozen=True)
class TechnicalGap:
    gap_type: str
    description: str
    severity: str
    confidence: float
    evidences: tuple[FieldEvidence, ...]
    is_hypothesis: bool = False


@dataclass(frozen=True)
class WrapperDependencyRisk:
    risk_type: str
    severity: str
    confidence: float
    rationale: str
    evidences: tuple[FieldEvidence, ...]
    is_hypothesis: bool = False


@dataclass(frozen=True)
class DiagnosticQuality:
    ready_for_recommendation: bool
    requires_human_review: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class AINativeAssessment:
    schema_version: str
    run_id: str
    company_name: str
    classification: str
    confidence: float
    nvidia_opportunity_urgency: str
    criteria_results: tuple[CriterionResult, ...]
    positive_signals: tuple[PositiveSignal, ...]
    technical_gaps: tuple[TechnicalGap, ...]
    wrapper_dependency_risks: tuple[WrapperDependencyRisk, ...]
    insufficient_evidence_fields: tuple[str, ...]
    evidences: tuple[FieldEvidence, ...]
    diagnostic_quality: DiagnosticQuality
    ready_for_recommendation: bool


AI_TERMS = (
    "ai-native",
    "ai native",
    "agente de ia",
    "agentes autonomos",
    "automacao com ia",
    "computer vision",
    "fine-tuning",
    "ia generativa",
    "inferencia",
    "inteligencia artificial",
    "machine learning",
    "mlops",
    "modelos proprietarios",
    "modelo proprietario",
    "nlp",
    "visao computacional",
)
GENERIC_AI_TERMS = ("chatbot", "chatgpt", "gpt api", "ia generativa", "openai api", "usa ia")
DEEP_STACK_TERMS = (
    "avaliacao de modelos",
    "dados proprietarios",
    "feedback loop",
    "fine-tuning",
    "inferencia em producao",
    "mlops",
    "model serving",
    "modelos proprietarios",
    "modelo proprietario",
)
PRODUCTION_TERMS = ("inferencia em producao", "model serving", "mlops", "producao", "latencia")
EXTERNAL_API_TERMS = ("api externa", "chatgpt", "gpt api", "openai api")
PROPRIETARY_DATA_TERMS = ("dados proprietarios", "dataset proprietario", "feedback loop")
NEGATIVE_AI_SIGNAL_TERMS = (
    "nenhum",
    "nenhum uso",
    "no ai",
    "no artificial intelligence",
    "none",
    "sem ia",
    "sem uso",
)


def assess_ai_native_maturity(
    profile: StartupProfile,
    evidence_groups: tuple[FieldEvidenceGroup, ...],
    collection_quality: CollectionQualitySummary,
    *,
    run_id: str,
) -> AINativeAssessment:
    """Assess AI-native maturity from profile, evidence groups, and quality only."""

    if not collection_quality.ready_for_evaluation:
        criteria = (
            CriterionResult(
                criterion="evidence_quality",
                status=AssessmentStatus.UNKNOWN.value,
                confidence=0.0,
                rationale="Collection quality is not ready for AI-native evaluation.",
                evidences=(),
            ),
        )
        quality = DiagnosticQuality(
            ready_for_recommendation=False,
            requires_human_review=True,
            reasons=tuple(collection_quality.readiness_reasons),
        )
        return AINativeAssessment(
            schema_version=SCHEMA_VERSION,
            run_id=run_id,
            company_name=profile.company_name.value,
            classification=Classification.INSUFFICIENT_EVIDENCE.value,
            confidence=0.0,
            nvidia_opportunity_urgency=OpportunityUrgency.HUMAN_REVIEW.value,
            criteria_results=criteria,
            positive_signals=(),
            technical_gaps=(_unknown_gap(),),
            wrapper_dependency_risks=(_unknown_risk(),),
            insufficient_evidence_fields=("collection_quality", *_unknown_quality_fields(collection_quality)),
            evidences=(),
            diagnostic_quality=quality,
            ready_for_recommendation=False,
        )

    context = _AssessmentContext(profile=profile, evidence_groups=evidence_groups)
    criteria = _criteria_results(context)
    classification, confidence = _classification(criteria)
    conflicts = _critical_conflicts(evidence_groups)
    signals = _positive_signals(context, criteria)
    gaps = _technical_gaps(context, classification)
    risks = _wrapper_risks(context, classification)
    insufficient_fields = _insufficient_fields(profile, conflicts)
    diagnostic_quality = _diagnostic_quality(classification, confidence, criteria, gaps, risks, conflicts)
    urgency = _opportunity_urgency(classification, confidence, gaps, diagnostic_quality)

    return AINativeAssessment(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        company_name=profile.company_name.value,
        classification=classification.value,
        confidence=confidence,
        nvidia_opportunity_urgency=urgency.value,
        criteria_results=criteria,
        positive_signals=signals,
        technical_gaps=gaps,
        wrapper_dependency_risks=risks,
        insufficient_evidence_fields=insufficient_fields,
        evidences=_assessment_evidences(criteria, gaps, risks),
        diagnostic_quality=diagnostic_quality,
        ready_for_recommendation=diagnostic_quality.ready_for_recommendation,
    )


def ai_native_assessment_to_dict(assessment: AINativeAssessment) -> dict[str, object]:
    """Convert an assessment to a JSON-serializable dictionary."""

    return _enum_values(asdict(assessment))


@dataclass(frozen=True)
class _AssessmentContext:
    profile: StartupProfile
    evidence_groups: tuple[FieldEvidenceGroup, ...]

    @property
    def text(self) -> str:
        values: list[str] = []
        for field in self.profile.__dict__.values():
            if isinstance(field, ProfileField) and field.value != UNKNOWN:
                values.append(field.value)
                values.extend(evidence.snippet for evidence in field.evidences if evidence.snippet != UNKNOWN)
        return normalize_text(" ".join(values))

    def evidences_for(self, *field_names: str) -> tuple[FieldEvidence, ...]:
        evidences: list[FieldEvidence] = []
        for field_name in field_names:
            field = getattr(self.profile, field_name)
            if isinstance(field, ProfileField):
                evidences.extend(field.evidences)
        return _dedupe_evidences(tuple(evidences))


def _criteria_results(context: _AssessmentContext) -> tuple[CriterionResult, ...]:
    text = context.text
    has_ai = (
        _has_any(text, AI_TERMS)
        or _has_any(text, GENERIC_AI_TERMS)
        or _has_positive_ai_signal_field(context.profile.ai_signals.value)
    )
    has_generic_only = _has_any(text, GENERIC_AI_TERMS) and not _has_any(text, DEEP_STACK_TERMS)
    has_deep_stack = _has_any(text, DEEP_STACK_TERMS)
    has_proprietary_data = _has_any(text, PROPRIETARY_DATA_TERMS)
    has_production = _has_any(text, PRODUCTION_TERMS)
    has_scale_need = _has_any(text, ("escala", "latencia", "custo", "governanca", "seguranca"))

    return (
        _criterion(
            "ai_product_centrality",
            has_ai and not has_generic_only,
            "AI appears central to product positioning.",
            "No strong evidence that AI is central to the product.",
            context.evidences_for("product", "ai_signals", "company_summary"),
            unknown=not has_ai,
        ),
        _criterion(
            "ai_architecture_depth",
            has_deep_stack,
            "Evidence mentions proprietary models, tuning, MLOps, or inference architecture.",
            "AI evidence is generic or feature-level without stack depth.",
            context.evidences_for("technologies_used", "ai_signals"),
            unknown=not has_ai,
        ),
        _criterion(
            "proprietary_data_loop",
            has_proprietary_data,
            "Evidence indicates proprietary data or feedback loops.",
            "No evidence of proprietary data or feedback loops.",
            context.evidences_for("technologies_used", "ai_signals"),
            unknown=not has_ai,
        ),
        _criterion(
            "production_readiness",
            has_production,
            "Evidence indicates production inference, serving, MLOps, or latency concerns.",
            "No evidence of production inference infrastructure.",
            context.evidences_for("technologies_used", "product"),
            unknown=not has_ai,
        ),
        _criterion(
            "scale_governance_need",
            has_scale_need,
            "Evidence indicates scale, latency, cost, governance, or security pressure.",
            "No explicit scale, latency, cost, governance, or security pressure found.",
            context.evidences_for("technologies_used", "company_summary", "product"),
            unknown=not has_ai,
        ),
        CriterionResult(
            criterion="evidence_quality",
            status=AssessmentStatus.POSITIVE.value,
            confidence=0.8,
            rationale="Collection quality is ready for AI-native evaluation.",
            evidences=(),
        ),
    )


def _criterion(
    name: str,
    is_positive: bool,
    positive_rationale: str,
    negative_rationale: str,
    evidences: tuple[FieldEvidence, ...],
    *,
    unknown: bool = False,
) -> CriterionResult:
    if unknown:
        return CriterionResult(
            criterion=name,
            status=AssessmentStatus.UNKNOWN.value,
            confidence=0.0,
            rationale="Insufficient evidence for this criterion.",
            evidences=(),
        )
    return CriterionResult(
        criterion=name,
        status=AssessmentStatus.POSITIVE.value if is_positive else AssessmentStatus.NEGATIVE.value,
        confidence=0.8 if is_positive else 0.55,
        rationale=positive_rationale if is_positive else negative_rationale,
        evidences=evidences if is_positive else (),
    )


def _classification(criteria: tuple[CriterionResult, ...]) -> tuple[Classification, float]:
    statuses = {criterion.criterion: criterion.status for criterion in criteria}
    if statuses.get("ai_product_centrality") == AssessmentStatus.UNKNOWN.value:
        return Classification.NON_AI, 0.72

    positives = {
        criterion.criterion
        for criterion in criteria
        if criterion.status == AssessmentStatus.POSITIVE.value and criterion.criterion != "evidence_quality"
    }
    if "ai_product_centrality" not in positives:
        return Classification.AI_ENABLED, 0.58
    if len(positives & {"ai_architecture_depth", "proprietary_data_loop", "production_readiness"}) >= 2:
        confidence = round(0.72 + 0.04 * len(positives), 2)
        return Classification.AI_NATIVE, min(confidence, 0.92)
    return Classification.AI_ENABLED, 0.64


def _positive_signals(
    context: _AssessmentContext,
    criteria: tuple[CriterionResult, ...],
) -> tuple[PositiveSignal, ...]:
    signals: list[PositiveSignal] = []
    for criterion in criteria:
        if criterion.status != AssessmentStatus.POSITIVE.value or criterion.criterion == "evidence_quality":
            continue
        signals.append(
            PositiveSignal(
                signal_type=criterion.criterion,
                description=criterion.rationale,
                confidence=criterion.confidence,
                evidences=criterion.evidences or context.evidences_for("ai_signals"),
            )
        )
    return tuple(signals)


def _wrapper_risks(
    context: _AssessmentContext,
    classification: Classification,
) -> tuple[WrapperDependencyRisk, ...]:
    text = context.text
    if classification is Classification.NON_AI:
        return (_unknown_risk(),)

    external_api = _has_any(text, EXTERNAL_API_TERMS)
    deep_stack = _has_any(text, DEEP_STACK_TERMS)
    proprietary_data = _has_any(text, PROPRIETARY_DATA_TERMS)
    production = _has_any(text, PRODUCTION_TERMS)
    evidences = context.evidences_for("ai_signals", "technologies_used")

    risks = [
        WrapperDependencyRisk(
            risk_type="external_api_only",
            severity=Severity.HIGH.value if external_api and not deep_stack else Severity.LOW.value,
            confidence=0.82 if external_api else 0.62,
            rationale=(
                "Evidence points to external LLM/API dependency without deeper stack signals."
                if external_api and not deep_stack
                else "No evidence that external APIs are the only AI dependency."
            ),
            evidences=evidences if external_api else (),
            is_hypothesis=not external_api,
        ),
        WrapperDependencyRisk(
            risk_type="no_proprietary_data_evidence",
            severity=Severity.LOW.value if proprietary_data else Severity.MEDIUM.value,
            confidence=0.8 if proprietary_data else 0.55,
            rationale=(
                "Evidence indicates proprietary data or feedback loops."
                if proprietary_data
                else "No public evidence of proprietary data or feedback loops."
            ),
            evidences=evidences if proprietary_data else (),
            is_hypothesis=not proprietary_data,
        ),
        WrapperDependencyRisk(
            risk_type="no_production_inference_evidence",
            severity=Severity.LOW.value if production else Severity.MEDIUM.value,
            confidence=0.78 if production else 0.55,
            rationale=(
                "Evidence indicates inference or serving in production."
                if production
                else "No public evidence of production inference infrastructure."
            ),
            evidences=evidences if production else (),
            is_hypothesis=not production,
        ),
    ]
    return tuple(risks)


def _technical_gaps(
    context: _AssessmentContext,
    classification: Classification,
) -> tuple[TechnicalGap, ...]:
    if classification is Classification.NON_AI:
        return (_unknown_gap(),)

    text = context.text
    gaps: list[TechnicalGap] = []
    gap_specs = (
        (
            "model_serving",
            ("inferencia", "latencia", "model serving", "producao", "escala"),
            "Potential need around model serving, latency, cost, or production inference.",
            Severity.HIGH.value,
        ),
        (
            "llm_customization",
            ("llm", "gpt", "ia generativa", "nlp", "fine-tuning"),
            "Potential need around LLM customization, tuning, evaluation, or domain adaptation.",
            Severity.MEDIUM.value,
        ),
        (
            "data_acceleration",
            ("dados proprietarios", "grandes volumes de dados", "dataset", "feedback loop"),
            "Potential need around data processing, feedback loops, or acceleration.",
            Severity.MEDIUM.value,
        ),
        (
            "voice_ai",
            ("audio", "fala", "speech", "voz"),
            "Potential need around voice AI workloads.",
            Severity.MEDIUM.value,
        ),
        (
            "computer_vision",
            ("computer vision", "visao computacional"),
            "Potential need around computer vision training or inference.",
            Severity.HIGH.value,
        ),
        (
            "robotics_simulation",
            ("robotica", "robotics", "simulacao", "simulation"),
            "Potential need around robotics simulation or embodied AI.",
            Severity.HIGH.value,
        ),
        (
            "healthcare_ai",
            ("clinica", "clinico", "healthtech", "hospitais", "saude"),
            "Potential need around healthcare AI validation, privacy, or deployment.",
            Severity.MEDIUM.value,
        ),
        (
            "cybersecurity_ai",
            ("ciberseguranca", "cybersecurity", "seguranca"),
            "Potential need around cybersecurity AI detection or response.",
            Severity.MEDIUM.value,
        ),
    )
    for gap_type, terms, description, severity in gap_specs:
        if _has_any(text, terms):
            gaps.append(
                TechnicalGap(
                    gap_type=gap_type,
                    description=description,
                    severity=severity,
                    confidence=0.72,
                    evidences=context.evidences_for("product", "sector", "technologies_used", "ai_signals"),
                )
            )

    return tuple(gaps) if gaps else (_unknown_gap(),)


def _diagnostic_quality(
    classification: Classification,
    confidence: float,
    criteria: tuple[CriterionResult, ...],
    gaps: tuple[TechnicalGap, ...],
    risks: tuple[WrapperDependencyRisk, ...],
    conflicts: tuple[str, ...],
) -> DiagnosticQuality:
    reasons: list[str] = []
    if conflicts:
        reasons.extend(f"conflicting_{field}" for field in conflicts)
    if classification in {Classification.NON_AI, Classification.INSUFFICIENT_EVIDENCE}:
        reasons.append("not_a_recommendation_candidate")
    if confidence < 0.75:
        reasons.append("classification_confidence_below_threshold")
    if all(gap.gap_type == UNKNOWN for gap in gaps):
        reasons.append("no_specific_gap")
    if any(risk.severity == Severity.HIGH.value for risk in risks):
        reasons.append("high_wrapper_dependency_risk")
    unknown_criteria = [criterion.criterion for criterion in criteria if criterion.status == UNKNOWN]
    if unknown_criteria and classification is not Classification.NON_AI:
        reasons.append("unknown_assessment_criteria")

    ready = not reasons and classification is Classification.AI_NATIVE
    return DiagnosticQuality(
        ready_for_recommendation=ready,
        requires_human_review=bool(conflicts) or "unknown_assessment_criteria" in reasons,
        reasons=tuple(dict.fromkeys(reasons)) or ("ready_for_recommendation",),
    )


def _opportunity_urgency(
    classification: Classification,
    confidence: float,
    gaps: tuple[TechnicalGap, ...],
    quality: DiagnosticQuality,
) -> OpportunityUrgency:
    if quality.requires_human_review:
        return OpportunityUrgency.HUMAN_REVIEW
    if classification is Classification.NON_AI:
        return OpportunityUrgency.LOW
    if classification is Classification.AI_ENABLED:
        return OpportunityUrgency.MEDIUM
    if classification is Classification.AI_NATIVE and confidence >= 0.8:
        has_specific_gap = any(gap.gap_type != UNKNOWN and gap.severity in {Severity.HIGH.value, Severity.MEDIUM.value} for gap in gaps)
        if has_specific_gap:
            return OpportunityUrgency.URGENT
    return OpportunityUrgency.MEDIUM


def _critical_conflicts(evidence_groups: tuple[FieldEvidenceGroup, ...]) -> tuple[str, ...]:
    fields = []
    for group in evidence_groups:
        if group.has_conflict and group.field_name in {"ai_signals", "product", "technologies_used"}:
            fields.append(group.field_name)
    return tuple(fields)


def _insufficient_fields(profile: StartupProfile, conflicts: tuple[str, ...]) -> tuple[str, ...]:
    fields = [
        field_name
        for field_name, field_value in profile.__dict__.items()
        if isinstance(field_value, ProfileField) and field_value.value == UNKNOWN
    ]
    fields.extend(f"conflicting_{field}" for field in conflicts)
    return tuple(dict.fromkeys(fields))


def _unknown_quality_fields(collection_quality: CollectionQualitySummary) -> tuple[str, ...]:
    return tuple(field_name for field_name, _count in collection_quality.unknown_fields)


def _assessment_evidences(
    criteria: tuple[CriterionResult, ...],
    gaps: tuple[TechnicalGap, ...],
    risks: tuple[WrapperDependencyRisk, ...],
) -> tuple[FieldEvidence, ...]:
    evidences: list[FieldEvidence] = []
    for item in (*criteria, *gaps, *risks):
        evidences.extend(item.evidences)
    return _dedupe_evidences(tuple(evidences))


def _unknown_gap() -> TechnicalGap:
    return TechnicalGap(
        gap_type=UNKNOWN,
        description="No specific technical gap can be supported by current evidence.",
        severity=Severity.UNKNOWN.value,
        confidence=0.0,
        evidences=(),
        is_hypothesis=True,
    )


def _unknown_risk() -> WrapperDependencyRisk:
    return WrapperDependencyRisk(
        risk_type=UNKNOWN,
        severity=Severity.UNKNOWN.value,
        confidence=0.0,
        rationale="No AI dependency risk can be assessed from current evidence.",
        evidences=(),
        is_hypothesis=True,
    )


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _has_positive_ai_signal_field(value: str) -> bool:
    if value == UNKNOWN:
        return False
    normalized_value = normalize_text(value)
    return not _has_any(normalized_value, NEGATIVE_AI_SIGNAL_TERMS)


def _dedupe_evidences(evidences: tuple[FieldEvidence, ...]) -> tuple[FieldEvidence, ...]:
    unique: dict[tuple[str, str, str], FieldEvidence] = {}
    for evidence in evidences:
        unique[(evidence.url, evidence.snippet, evidence.source_type)] = evidence
    return tuple(unique.values())


def _enum_values(data: object) -> object:
    if isinstance(data, StrEnum):
        return data.value
    if isinstance(data, dict):
        return {key: _enum_values(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_enum_values(value) for value in data]
    if isinstance(data, tuple):
        return tuple(_enum_values(value) for value in data)
    return data
