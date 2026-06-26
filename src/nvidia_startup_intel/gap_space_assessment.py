"""Audit assessed startup gaps against the NVIDIA Knowledge taxonomy.

This module prepares Recommendation inputs. It does not retrieve NVIDIA
Knowledge, call LLMs, scrape, or touch the network.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from nvidia_startup_intel.ai_native_assessment import AINativeAssessment, TechnicalGap
from nvidia_startup_intel.collection_quality import CollectionQualitySummary
from nvidia_startup_intel.evidence import FieldEvidenceGroup
from nvidia_startup_intel.nvidia_knowledge import (
    NVIDIAKnowledgeCorpus,
    NVIDIAStackProfile,
    build_nvidia_knowledge_query,
    nvidia_stack_profiles_from_corpus,
)
from nvidia_startup_intel.search_params import UNKNOWN
from nvidia_startup_intel.startup_profile import FieldEvidence, ProfileField, StartupProfile


SCHEMA_VERSION = "gap_space_assessment.v1"
MIN_SUPPORTED_GAP_CONFIDENCE = 0.60
STACK_RELEVANT_UNKNOWN_FIELDS = frozenset({"ai_signals", "company_summary", "product", "technologies_used"})


@dataclass(frozen=True)
class NVIDIATaxonomyTarget:
    stack_id: str
    stack_name: str
    document_id: str
    topic: str
    supported_gap_types: tuple[str, ...]
    source_url: str
    citation_chunk_ids: tuple[str, ...]


@dataclass(frozen=True)
class GapSpaceMapping:
    gap_type: str
    gap_description: str
    support_status: str
    confidence: float
    observed_evidences: tuple[FieldEvidence, ...]
    inference_rationale: str
    is_hypothesis: bool
    requires_human_review: bool
    review_reasons: tuple[str, ...]
    taxonomy_targets: tuple[NVIDIATaxonomyTarget, ...]
    retrieval_gap_type: str
    retrieval_description: str
    retrieval_startup_signals: tuple[str, ...]
    retrieval_query: str


@dataclass(frozen=True)
class GapSpaceQuality:
    ready_for_recommendation: bool
    requires_human_review: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class GapSpaceAssessment:
    schema_version: str
    run_id: str
    startup_identifier: str
    corpus_version: str
    mappings: tuple[GapSpaceMapping, ...]
    retrieval_queries: tuple[str, ...]
    quality: GapSpaceQuality


def assess_gap_space(
    *,
    profile: StartupProfile,
    collection_quality: CollectionQualitySummary,
    assessment: AINativeAssessment,
    evidence_groups: tuple[FieldEvidenceGroup, ...],
    corpus: NVIDIAKnowledgeCorpus,
    run_id: str,
) -> GapSpaceAssessment:
    """Map technical gaps to the versioned NVIDIA taxonomy before retrieval."""

    stack_profiles = nvidia_stack_profiles_from_corpus(corpus)
    startup_signals = _startup_signals(profile)
    context_review_reasons = (
        *_assessment_review_reasons(assessment),
        *_collection_review_reasons(collection_quality),
        *_evidence_group_review_reasons(evidence_groups),
    )
    mappings = tuple(
        _mapping_for_gap(
            gap=gap,
            stack_profiles=stack_profiles,
            startup_signals=startup_signals,
            context_review_reasons=context_review_reasons,
        )
        for gap in assessment.technical_gaps
        if gap.gap_type != UNKNOWN
    )
    quality = _quality(
        mappings=mappings,
        collection_quality=collection_quality,
        assessment=assessment,
        evidence_groups=evidence_groups,
    )
    return GapSpaceAssessment(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        startup_identifier=_startup_identifier(profile, assessment),
        corpus_version=corpus.corpus_version,
        mappings=mappings,
        retrieval_queries=tuple(mapping.retrieval_query for mapping in mappings),
        quality=quality,
    )


def gap_space_assessment_to_dict(assessment: GapSpaceAssessment) -> dict[str, object]:
    """Convert a gap-space assessment to a JSON-serializable dictionary."""

    return asdict(assessment)


def _mapping_for_gap(
    *,
    gap: TechnicalGap,
    stack_profiles: tuple[NVIDIAStackProfile, ...],
    startup_signals: tuple[str, ...],
    context_review_reasons: tuple[str, ...],
) -> GapSpaceMapping:
    targets = tuple(
        _taxonomy_target(profile)
        for profile in stack_profiles
        if gap.gap_type in profile.supported_gap_types or gap.gap_type == profile.topic
    )
    review_reasons = tuple(
        dict.fromkeys((*_review_reasons(gap=gap, taxonomy_targets=targets), *context_review_reasons))
    )
    support_status = _support_status(review_reasons)
    query = build_nvidia_knowledge_query(
        gap_type=gap.gap_type,
        description=gap.description,
        startup_signals=startup_signals,
    )
    return GapSpaceMapping(
        gap_type=gap.gap_type,
        gap_description=gap.description,
        support_status=support_status,
        confidence=gap.confidence,
        observed_evidences=tuple(gap.evidences),
        inference_rationale=_inference_rationale(gap=gap, targets=targets, review_reasons=review_reasons),
        is_hypothesis=bool(review_reasons) or gap.is_hypothesis,
        requires_human_review=bool(review_reasons),
        review_reasons=review_reasons,
        taxonomy_targets=targets,
        retrieval_gap_type=gap.gap_type,
        retrieval_description=gap.description,
        retrieval_startup_signals=startup_signals,
        retrieval_query=query,
    )


def _review_reasons(
    *,
    gap: TechnicalGap,
    taxonomy_targets: tuple[NVIDIATaxonomyTarget, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not taxonomy_targets:
        reasons.append("unsupported_gap_type")
    if not gap.evidences:
        reasons.append("missing_observed_gap_evidence")
    if gap.confidence < MIN_SUPPORTED_GAP_CONFIDENCE:
        reasons.append("low_gap_confidence")
    if gap.is_hypothesis:
        reasons.append("upstream_gap_is_hypothesis")
    return tuple(dict.fromkeys(reasons))


def _support_status(review_reasons: tuple[str, ...]) -> str:
    if "unsupported_gap_type" in review_reasons:
        return "unsupported"
    if review_reasons:
        return "hypothesis"
    return "supported"


def _assessment_review_reasons(assessment: AINativeAssessment) -> tuple[str, ...]:
    reasons: list[str] = []
    if any(risk.severity == "high" for risk in assessment.wrapper_dependency_risks):
        reasons.append("high_wrapper_risk")
    return tuple(reasons)


def _collection_review_reasons(collection_quality: CollectionQualitySummary) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name, count in _unknown_field_entries(collection_quality):
        if count > 0 and field_name in STACK_RELEVANT_UNKNOWN_FIELDS:
            reasons.append(f"unknown_field:{field_name}")
    return tuple(dict.fromkeys(reasons))


def _evidence_group_review_reasons(evidence_groups: tuple[FieldEvidenceGroup, ...]) -> tuple[str, ...]:
    if any(group.has_conflict for group in evidence_groups):
        return ("conflicting_startup_evidence",)
    return ()


def _unknown_field_entries(collection_quality: CollectionQualitySummary) -> tuple[tuple[str, int], ...]:
    entries: list[tuple[str, int]] = []
    for item in collection_quality.unknown_fields:
        if isinstance(item, tuple) and len(item) == 2:
            field_name, count = item
            entries.append((str(field_name), int(count)))
            continue
        entries.append((str(item), 1))
    return tuple(entries)


def _inference_rationale(
    *,
    gap: TechnicalGap,
    targets: tuple[NVIDIATaxonomyTarget, ...],
    review_reasons: tuple[str, ...],
) -> str:
    if targets and not review_reasons:
        stack_names = ", ".join(target.stack_name for target in targets)
        return f"Observed startup evidence and official NVIDIA taxonomy supports {gap.gap_type}: {stack_names}."
    if targets:
        return (
            f"The gap maps to official NVIDIA taxonomy for {gap.gap_type}, "
            f"but human review is required: {', '.join(review_reasons)}."
        )
    return f"No official NVIDIA taxonomy target supports {gap.gap_type}; human review is required."


def _taxonomy_target(profile: NVIDIAStackProfile) -> NVIDIATaxonomyTarget:
    return NVIDIATaxonomyTarget(
        stack_id=profile.stack_id,
        stack_name=profile.stack_name,
        document_id=profile.document_id,
        topic=profile.topic,
        supported_gap_types=profile.supported_gap_types,
        source_url=profile.source_url,
        citation_chunk_ids=profile.citation_chunk_ids,
    )


def _quality(
    *,
    mappings: tuple[GapSpaceMapping, ...],
    collection_quality: CollectionQualitySummary,
    assessment: AINativeAssessment,
    evidence_groups: tuple[FieldEvidenceGroup, ...],
) -> GapSpaceQuality:
    reasons: list[str] = []
    if not collection_quality.ready_for_evaluation:
        reasons.append("collection_quality_not_ready")
    if not assessment.ready_for_recommendation:
        reasons.append("assessment_not_ready_for_recommendation")
    if any(group.has_conflict for group in evidence_groups):
        reasons.append("conflicting_startup_evidence")
    for mapping in mappings:
        reasons.extend(mapping.review_reasons)
    if not mappings:
        reasons.append("no_gap_space_mapping")

    reason_tuple = tuple(dict.fromkeys(reasons))
    return GapSpaceQuality(
        ready_for_recommendation=not reason_tuple,
        requires_human_review=bool(reason_tuple),
        reasons=reason_tuple or ("gap_space_ready_for_recommendation",),
    )


def _startup_identifier(profile: StartupProfile, assessment: AINativeAssessment) -> str:
    if profile.company_name.value != UNKNOWN:
        return profile.company_name.value
    if assessment.company_name:
        return assessment.company_name
    return UNKNOWN


def _startup_signals(profile: StartupProfile) -> tuple[str, ...]:
    signals: list[str] = []
    for field_name in ("ai_signals", "technologies_used", "company_summary"):
        field_value = getattr(profile, field_name)
        if isinstance(field_value, ProfileField) and field_value.value != UNKNOWN:
            signals.append(field_value.value)
    return tuple(signals)
