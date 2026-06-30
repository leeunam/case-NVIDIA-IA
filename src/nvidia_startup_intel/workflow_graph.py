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
    BriefingNarrative,
    ExecutiveBriefing,
    HumanReviewBriefing,
    generate_briefing_narrative,
    generate_executive_briefing,
    generate_human_review_briefing,
)
from nvidia_startup_intel.collection_quality import CollectionQualitySummary
from nvidia_startup_intel.evidence import FieldEvidenceGroup
from nvidia_startup_intel.llm_adapters import LLMClient
from nvidia_startup_intel.nvidia_retrievers import (
    HybridNVIDIAPgvectorKnowledgeRetriever,
    LocalBM25NVIDIAKnowledgeRetriever,
    NVIDIAKnowledgeRetriever,
    NVIDIAVectorKnowledgeStore,
)
from nvidia_startup_intel.gap_space_assessment import GapSpaceAssessment, assess_gap_space
from nvidia_startup_intel.nvidia_embeddings import EmbeddingClient
from nvidia_startup_intel.nvidia_knowledge import (
    NVIDIAKnowledgeCorpus,
    NVIDIAKnowledgeRetrieval,
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
    user_query: str
    profile: StartupProfile
    evidence_groups: tuple[FieldEvidenceGroup, ...]
    collection_quality: CollectionQualitySummary
    assessment: AINativeAssessment
    gap_space_assessment: GapSpaceAssessment
    corpus: NVIDIAKnowledgeCorpus
    retrievals: tuple[NVIDIAKnowledgeRetrieval, ...]
    recommendation_set: NVIDIARecommendationSet
    executive_briefing: ExecutiveBriefing
    human_review_briefing: HumanReviewBriefing
    briefing_narrative: BriefingNarrative
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
    knowledge_retriever: NVIDIAKnowledgeRetriever | None = None
    embedding_client: EmbeddingClient | None = None
    vector_store: NVIDIAVectorKnowledgeStore | None = None
    retrieval_top_k: int = 1
    lexical_top_k: int = 3
    vector_top_k: int = 3
    lexical_weight: float = 1.0
    vector_weight: float = 1.0
    rrf_k: int = 60
    min_vector_score: float = 0.0
    llm_client: LLMClient | None = None
    artifact_store: DownstreamArtifactStore | None = None
    checkpoints: list[DownstreamWorkflowState] = field(default_factory=list)


class LocalDownstreamWorkflow:
    """Small invoke-compatible runner for deterministic downstream validation."""

    def __init__(self, runtime: DownstreamWorkflowRuntime) -> None:
        self.runtime = runtime

    def invoke(self, state: DownstreamWorkflowState) -> DownstreamWorkflowState:
        self.runtime.checkpoints.clear()
        current = initialize_downstream_state_node(state, self.runtime)
        for node in (
            decide_recommendation_readiness_node,
            assess_gap_space_node,
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


def build_downstream_langgraph(runtime: DownstreamWorkflowRuntime) -> Any:
    """Compile the optional LangGraph downstream workflow when available."""

    try:
        from langgraph.graph import END, StateGraph  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise RuntimeError("Install langgraph to build the production downstream graph") from exc

    graph = StateGraph(DownstreamWorkflowState)
    graph.add_node(
        "initialize_state",
        lambda state: initialize_downstream_state_node(state, runtime),
    )
    graph.add_node(
        "decide_recommendation_readiness",
        lambda state: decide_recommendation_readiness_node(state, runtime),
    )
    graph.add_node(
        "retrieve_nvidia_knowledge",
        lambda state: retrieve_nvidia_knowledge_node(state, runtime),
    )
    graph.add_node(
        "assess_gap_space",
        lambda state: assess_gap_space_node(state, runtime),
    )
    graph.add_node(
        "build_recommendations",
        lambda state: build_recommendations_node(state, runtime),
    )
    graph.add_node(
        "decide_briefing_readiness",
        lambda state: decide_briefing_readiness_node(state, runtime),
    )
    graph.add_node(
        "generate_downstream_briefing",
        lambda state: generate_downstream_briefing_node(state, runtime),
    )
    graph.add_node(
        "persist_downstream_artifacts",
        lambda state: persist_downstream_artifacts_node(state, runtime),
    )
    graph.add_node(
        "decide_final_next_action",
        lambda state: decide_final_next_action_node(state, runtime),
    )

    graph.set_entry_point("initialize_state")
    graph.add_edge("initialize_state", "decide_recommendation_readiness")
    graph.add_conditional_edges(
        "decide_recommendation_readiness",
        _route_after_recommendation_readiness,
        {
            "ready_for_recommendation": "assess_gap_space",
            "needs_more_collection_or_human_review": "assess_gap_space",
        },
    )
    graph.add_edge("assess_gap_space", "retrieve_nvidia_knowledge")
    graph.add_edge("retrieve_nvidia_knowledge", "build_recommendations")
    graph.add_edge("build_recommendations", "decide_briefing_readiness")
    graph.add_conditional_edges(
        "decide_briefing_readiness",
        _route_after_briefing_readiness,
        {
            "ready_for_briefing": "generate_downstream_briefing",
            "human_review_requested": "generate_downstream_briefing",
        },
    )
    graph.add_conditional_edges(
        "generate_downstream_briefing",
        _route_after_briefing_generation,
        {
            "briefing_generated": "persist_downstream_artifacts",
            "human_review_requested": "persist_downstream_artifacts",
            "needs_more_collection_or_human_review": "persist_downstream_artifacts",
        },
    )
    graph.add_edge("persist_downstream_artifacts", "decide_final_next_action")
    graph.add_edge("decide_final_next_action", END)
    return graph.compile()


build_langgraph = build_downstream_langgraph


def initialize_downstream_state_node(
    state: DownstreamWorkflowState,
    runtime: DownstreamWorkflowRuntime,
) -> DownstreamWorkflowState:
    return _merge(
        state,
        branch_decisions=state.get("branch_decisions", ()),
        errors=state.get("errors", ()),
    )


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
    retriever = runtime.knowledge_retriever
    if (
        retriever is None
        and corpus is not None
        and runtime.embedding_client is not None
        and runtime.vector_store is not None
    ):
        retriever = HybridNVIDIAPgvectorKnowledgeRetriever(
            corpus=corpus,
            embedding_client=runtime.embedding_client,
            vector_store=runtime.vector_store,
            lexical_top_k=runtime.lexical_top_k,
            vector_top_k=runtime.vector_top_k,
            lexical_weight=runtime.lexical_weight,
            vector_weight=runtime.vector_weight,
            rrf_k=runtime.rrf_k,
            min_vector_score=runtime.min_vector_score,
        )
    if retriever is None and corpus is not None:
        retriever = LocalBM25NVIDIAKnowledgeRetriever(corpus)
    if retriever is None:
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
    gap_space_assessment = state.get("gap_space_assessment")
    retrievals: list[NVIDIAKnowledgeRetrieval] = []
    try:
        retrieve_for_query = getattr(retriever, "retrieve_for_query", None)
        if gap_space_assessment is not None and callable(retrieve_for_query):
            for query_request in gap_space_assessment.retrieval_requests:
                retrievals.append(
                    retrieve_for_query(
                        run_id=state.get("run_id", assessment.run_id),
                        query=query_request,
                        top_k=runtime.retrieval_top_k,
                    )
                )
            return _merge(state, retrievals=tuple(retrievals))

        for gap in assessment.technical_gaps:
            if gap.gap_type == UNKNOWN:
                continue
            retrievals.append(
                retriever.retrieve_for_gap(
                    run_id=state.get("run_id", assessment.run_id),
                    gap=gap,
                    startup_signals=_startup_signals(profile),
                    top_k=runtime.retrieval_top_k,
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


def assess_gap_space_node(
    state: DownstreamWorkflowState,
    runtime: DownstreamWorkflowRuntime,
) -> DownstreamWorkflowState:
    if _has_branch(state, "needs_more_collection_or_human_review"):
        return state
    if state.get("gap_space_assessment") is not None:
        return state

    corpus = state.get("corpus") or runtime.corpus
    if corpus is None:
        return state

    assessment = state["assessment"]
    return _merge(
        state,
        gap_space_assessment=assess_gap_space(
            profile=state["profile"],
            collection_quality=state["collection_quality"],
            assessment=assessment,
            evidence_groups=state.get("evidence_groups", ()),
            corpus=corpus,
            run_id=state.get("run_id", assessment.run_id),
        ),
    )


def build_recommendations_node(
    state: DownstreamWorkflowState,
    runtime: DownstreamWorkflowRuntime,
) -> DownstreamWorkflowState:
    gap_space_assessment = state.get("gap_space_assessment")
    recommendation_set = build_nvidia_recommendations(
        profile=state["profile"],
        evidence_groups=state.get("evidence_groups", ()),
        collection_quality=state["collection_quality"],
        assessment=state["assessment"],
        retrievals=state.get("retrievals", ()),
        commercial_opportunities=gap_space_assessment.commercial_opportunities
        if gap_space_assessment is not None
        else (),
        gap_space_assessment=gap_space_assessment,
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
        updates: dict[str, object] = {"executive_briefing": briefing}
        if runtime.llm_client is not None:
            updates["briefing_narrative"] = generate_briefing_narrative(
                briefing=briefing,
                llm_client=runtime.llm_client,
                user_query=str(state.get("user_query", "")),
                profile=state["profile"],
                assessment=state["assessment"],
                recommendation_set=recommendation_set,
                retrievals=state.get("retrievals", ()),
            )
        return _append_branch(
            _merge(state, **updates),
            branch_name="briefing_generated",
            next_action="prepare_technical_outreach",
            audit_reason="executive_briefing_ready_for_use",
        )

    briefing = generate_human_review_briefing(**briefing_args)
    updates = {"human_review_briefing": briefing}
    if runtime.llm_client is not None:
        updates["briefing_narrative"] = generate_briefing_narrative(
            briefing=briefing,
            llm_client=runtime.llm_client,
            user_query=str(state.get("user_query", "")),
            profile=state["profile"],
            assessment=state["assessment"],
            recommendation_set=recommendation_set,
            retrievals=state.get("retrievals", ()),
        )
    return _merge(state, **updates)


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


def _route_after_recommendation_readiness(state: DownstreamWorkflowState) -> str:
    if _has_branch(state, "needs_more_collection_or_human_review"):
        return "needs_more_collection_or_human_review"
    return "ready_for_recommendation"


def _route_after_briefing_readiness(state: DownstreamWorkflowState) -> str:
    if _has_branch(state, "ready_for_briefing"):
        return "ready_for_briefing"
    return "human_review_requested"


def _route_after_briefing_generation(state: DownstreamWorkflowState) -> str:
    if _has_branch(state, "briefing_generated"):
        return "briefing_generated"
    if _has_branch(state, "human_review_requested"):
        return "human_review_requested"
    return "needs_more_collection_or_human_review"


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
