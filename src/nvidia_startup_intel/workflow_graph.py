"""Local downstream workflow orchestration.

The runner mirrors the future LangGraph downstream path while keeping the
default validation path independent from LangGraph and external services.
Business rules stay in Knowledge, Recommendation, and Briefing modules.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass, field
from typing import Any, Protocol, TypedDict

from nvidia_startup_intel.ai_native_assessment import AINativeAssessment
from nvidia_startup_intel.briefing import (
    ExecutiveBriefing,
    HumanReviewBriefing,
    generate_executive_briefing,
    generate_human_review_briefing,
)
from nvidia_startup_intel.collection_quality import CollectionQualitySummary
from nvidia_startup_intel.evidence import FieldEvidenceGroup
from nvidia_startup_intel.nvidia_knowledge import (
    NVIDIAKnowledgeCorpus,
    NVIDIAKnowledgeRetrieval,
    retrieve_nvidia_knowledge_by_gap,
)
from nvidia_startup_intel.nvidia_recommendation import (
    NVIDIARecommendationSet,
    build_nvidia_recommendations,
)
from nvidia_startup_intel.search_params import UNKNOWN
from nvidia_startup_intel.startup_profile import ProfileField, StartupProfile


@dataclass(frozen=True)
class DownstreamWorkflowBranch:
    branch_name: str
    next_action: str
    audit_reason: str


@dataclass(frozen=True)
class DownstreamWorkflowError:
    step: str
    error_type: str
    message: str
    audit_reason: str


class DownstreamWorkflowState(TypedDict, total=False):
    run_id: str
    profile: StartupProfile
    evidence_groups: tuple[FieldEvidenceGroup, ...]
    collection_quality: CollectionQualitySummary
    assessment: AINativeAssessment
    corpus: NVIDIAKnowledgeCorpus
    retrievals: tuple[NVIDIAKnowledgeRetrieval, ...]
    recommendation_set: NVIDIARecommendationSet
    executive_briefing: ExecutiveBriefing
    human_review_briefing: HumanReviewBriefing
    branch_decisions: tuple[DownstreamWorkflowBranch, ...]
    workflow_outcome: str
    next_action: str
    errors: tuple[DownstreamWorkflowError, ...]


class DownstreamArtifactStore(Protocol):
    def save_downstream_state(self, state: DownstreamWorkflowState) -> None: ...


@dataclass
class DownstreamWorkflowRuntime:
    corpus: NVIDIAKnowledgeCorpus | None = None
    retrievals: tuple[NVIDIAKnowledgeRetrieval, ...] = ()
    artifact_store: DownstreamArtifactStore | None = None
    checkpoints: list[DownstreamWorkflowState] = field(default_factory=list)


class LocalDownstreamWorkflow:
    """Small invoke-compatible runner for deterministic downstream validation."""

    def __init__(self, runtime: DownstreamWorkflowRuntime) -> None:
        self.runtime = runtime

    def invoke(self, state: DownstreamWorkflowState) -> DownstreamWorkflowState:
        self.runtime.checkpoints.clear()
        current = _merge(
            state,
            branch_decisions=state.get("branch_decisions", ()),
            errors=state.get("errors", ()),
        )
        for node in (
            decide_recommendation_readiness_node,
            retrieve_nvidia_knowledge_node,
            build_recommendations_node,
            decide_briefing_readiness_node,
            generate_downstream_briefing_node,
            persist_downstream_artifacts_node,
            decide_final_next_action_node,
        ):
            current = node(current, self.runtime)
            self.runtime.checkpoints.append(dict(current))
        return current


def build_local_downstream_workflow(runtime: DownstreamWorkflowRuntime) -> LocalDownstreamWorkflow:
    return LocalDownstreamWorkflow(runtime)


def decide_recommendation_readiness_node(
    state: DownstreamWorkflowState,
    runtime: DownstreamWorkflowRuntime,
) -> DownstreamWorkflowState:
    collection_quality = state["collection_quality"]
    assessment = state["assessment"]
    if collection_quality.ready_for_evaluation and assessment.ready_for_recommendation:
        return _append_branch(
            state,
            branch_name="ready_for_recommendation",
            next_action="retrieve_nvidia_knowledge",
            audit_reason="collection_and_assessment_ready_for_recommendation",
        )

    reasons = (*collection_quality.readiness_reasons, *assessment.diagnostic_quality.reasons)
    return _append_branch(
        state,
        branch_name="needs_more_collection_or_human_review",
        next_action="generate_human_review_briefing",
        audit_reason=";".join(reasons) or "upstream_not_ready_for_recommendation",
    )


def retrieve_nvidia_knowledge_node(
    state: DownstreamWorkflowState,
    runtime: DownstreamWorkflowRuntime,
) -> DownstreamWorkflowState:
    if _has_branch(state, "needs_more_collection_or_human_review"):
        return _merge(state, retrievals=())
    if state.get("retrievals"):
        return state
    if runtime.retrievals:
        return _merge(state, retrievals=runtime.retrievals)

    corpus = state.get("corpus") or runtime.corpus
    if corpus is None:
        return _merge(
            _append_error(
                state,
                step="retrieve_nvidia_knowledge",
                error_type="missing_nvidia_knowledge_input",
                message="A local NVIDIA corpus or retrieval fixture is required for downstream retrieval.",
                audit_reason="retrieval_skipped_missing_corpus_or_fixture",
            ),
            retrievals=(),
        )

    assessment = state["assessment"]
    profile = state["profile"]
    retrievals: list[NVIDIAKnowledgeRetrieval] = []
    try:
        for gap in assessment.technical_gaps:
            if gap.gap_type == UNKNOWN:
                continue
            retrievals.append(
                retrieve_nvidia_knowledge_by_gap(
                    corpus,
                    run_id=state.get("run_id", assessment.run_id),
                    gap_type=gap.gap_type,
                    description=gap.description,
                    startup_signals=_startup_signals(profile),
                    top_k=1,
                )
            )
    except Exception as exc:
        return _merge(
            _append_error(
                state,
                step="retrieve_nvidia_knowledge",
                error_type=type(exc).__name__,
                message=str(exc),
                audit_reason="retrieval_failed_structured_error",
            ),
            retrievals=tuple(retrievals),
        )
    return _merge(state, retrievals=tuple(retrievals))


def build_recommendations_node(
    state: DownstreamWorkflowState,
    runtime: DownstreamWorkflowRuntime,
) -> DownstreamWorkflowState:
    recommendation_set = build_nvidia_recommendations(
        profile=state["profile"],
        evidence_groups=state.get("evidence_groups", ()),
        collection_quality=state["collection_quality"],
        assessment=state["assessment"],
        retrievals=state.get("retrievals", ()),
    )
    return _merge(state, recommendation_set=recommendation_set)


def decide_briefing_readiness_node(
    state: DownstreamWorkflowState,
    runtime: DownstreamWorkflowRuntime,
) -> DownstreamWorkflowState:
    recommendation_set = state["recommendation_set"]
    if recommendation_set.quality.ready_for_briefing:
        return _append_branch(
            state,
            branch_name="ready_for_briefing",
            next_action="generate_executive_briefing",
            audit_reason=";".join(recommendation_set.quality.reasons),
        )

    return _append_branch(
        state,
        branch_name="human_review_requested",
        next_action="generate_human_review_briefing",
        audit_reason=";".join(recommendation_set.quality.reasons),
    )


def generate_downstream_briefing_node(
    state: DownstreamWorkflowState,
    runtime: DownstreamWorkflowRuntime,
) -> DownstreamWorkflowState:
    recommendation_set = state["recommendation_set"]
    briefing_args = {
        "profile": state["profile"],
        "evidence_groups": state.get("evidence_groups", ()),
        "collection_quality": state["collection_quality"],
        "assessment": state["assessment"],
        "recommendation_set": recommendation_set,
    }
    if recommendation_set.quality.ready_for_briefing:
        briefing = generate_executive_briefing(**briefing_args)
        return _append_branch(
            _merge(state, executive_briefing=briefing),
            branch_name="briefing_generated",
            next_action="prepare_technical_outreach",
            audit_reason="executive_briefing_ready_for_use",
        )

    return _merge(state, human_review_briefing=generate_human_review_briefing(**briefing_args))


def persist_downstream_artifacts_node(
    state: DownstreamWorkflowState,
    runtime: DownstreamWorkflowRuntime,
) -> DownstreamWorkflowState:
    if runtime.artifact_store is None:
        return state

    try:
        runtime.artifact_store.save_downstream_state(state)
    except Exception as exc:
        return _append_error(
            state,
            step="persist_downstream_artifacts",
            error_type=type(exc).__name__,
            message=str(exc),
            audit_reason="storage_failed_structured_error",
        )
    return state


def decide_final_next_action_node(
    state: DownstreamWorkflowState,
    runtime: DownstreamWorkflowRuntime,
) -> DownstreamWorkflowState:
    if "executive_briefing" in state:
        return _merge(
            state,
            workflow_outcome="briefing_generated",
            next_action=state["executive_briefing"].next_action,
        )

    if "human_review_briefing" in state:
        workflow_outcome = (
            "needs_more_collection_or_human_review"
            if _has_branch(state, "needs_more_collection_or_human_review")
            else "human_review_requested"
        )
        return _merge(
            state,
            workflow_outcome=workflow_outcome,
            next_action=state["human_review_briefing"].next_action,
        )

    return _merge(state, workflow_outcome="human_review_requested", next_action="review_workflow_errors")


def _startup_signals(profile: StartupProfile) -> tuple[str, ...]:
    signals: list[str] = []
    for field_name in ("ai_signals", "technologies_used", "company_summary"):
        field_value = getattr(profile, field_name)
        if isinstance(field_value, ProfileField) and field_value.value != UNKNOWN:
            signals.append(field_value.value)
    return tuple(signals)


def _append_branch(
    state: DownstreamWorkflowState,
    *,
    branch_name: str,
    next_action: str,
    audit_reason: str,
) -> DownstreamWorkflowState:
    branch = DownstreamWorkflowBranch(
        branch_name=branch_name,
        next_action=next_action,
        audit_reason=audit_reason,
    )
    return _merge(state, branch_decisions=(*state.get("branch_decisions", ()), branch))


def _has_branch(state: DownstreamWorkflowState, branch_name: str) -> bool:
    return any(branch.branch_name == branch_name for branch in state.get("branch_decisions", ()))


def _append_error(
    state: DownstreamWorkflowState,
    *,
    step: str,
    error_type: str,
    message: str,
    audit_reason: str,
) -> DownstreamWorkflowState:
    error = DownstreamWorkflowError(
        step=step,
        error_type=error_type,
        message=message,
        audit_reason=audit_reason,
    )
    return _merge(state, errors=(*state.get("errors", ()), error))


def _merge(state: DownstreamWorkflowState, **updates: Any) -> DownstreamWorkflowState:
    current: MutableMapping[str, Any] = dict(state)
    current.update(updates)
    return dict(current)  # type: ignore[return-value]
