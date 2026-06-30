"""Local downstream workflow orchestration.

The runner mirrors the future LangGraph downstream path while keeping the
default validation path independent from LangGraph and external services.
Business rules stay in Knowledge, Recommendation, and Briefing modules.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
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
from nvidia_startup_intel.discovery import CandidateStartup, RawDiscoveryResult
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
from nvidia_startup_intel.page_collection import PageCollectionResult
from nvidia_startup_intel.pipeline import ScrapingPipelineResult, profile_result_key
from nvidia_startup_intel.scraping_graph import (
    ScrapingGraphRuntime,
    build_local_scraping_graph,
)
from nvidia_startup_intel.search_execution import SearchExecutionError
from nvidia_startup_intel.search_params import UNKNOWN, SearchParams
from nvidia_startup_intel.search_plan import SearchPlan
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


@dataclass(frozen=True)
class WorkflowPersistenceReference:
    artifact_kind: str
    startup_identifier: str
    storage: str
    reference: str


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


class IntelligenceWorkflowState(TypedDict, total=False):
    run_id: str
    query: str
    limit: int
    search_params: SearchParams
    search_plan: SearchPlan
    raw_results: tuple[RawDiscoveryResult, ...]
    search_errors: tuple[SearchExecutionError, ...]
    candidates: tuple[CandidateStartup, ...]
    collected_pages_by_candidate: Mapping[str, PageCollectionResult]
    profiles: tuple[StartupProfile, ...]
    evidence_groups_by_profile: Mapping[str, tuple[FieldEvidenceGroup, ...]]
    ai_native_assessments_by_profile: Mapping[str, AINativeAssessment]
    quality_summary: CollectionQualitySummary
    next_action: str
    startup_identifiers: tuple[str, ...]
    corpus_version: str
    downstream_states_by_startup: Mapping[str, DownstreamWorkflowState]
    branch_decisions: tuple[DownstreamWorkflowBranch, ...]
    workflow_outcome: str
    persistence_references: tuple[WorkflowPersistenceReference, ...]
    errors: tuple[DownstreamWorkflowError, ...]


class DownstreamArtifactStore(Protocol):
    def save_downstream_state(self, state: DownstreamWorkflowState) -> None: ...


class IntelligenceArtifactStore(DownstreamArtifactStore, Protocol):
    def create_run(self, *, run_id: str) -> str: ...

    def save_pipeline_result(self, run_id: str, result: ScrapingPipelineResult) -> None: ...

    def save_ai_native_assessments(
        self,
        run_id: str,
        assessments_by_profile: Mapping[str, AINativeAssessment],
    ) -> None: ...


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


@dataclass
class IntelligenceWorkflowRuntime:
    scraping: ScrapingGraphRuntime
    downstream: DownstreamWorkflowRuntime
    artifact_store: IntelligenceArtifactStore | None = None
    checkpoints: list[IntelligenceWorkflowState] = field(default_factory=list)


class LocalIntelligenceWorkflow:
    """Invoke-compatible runner for the full local intelligence workflow."""

    def __init__(self, runtime: IntelligenceWorkflowRuntime) -> None:
        self.runtime = runtime

    def invoke(self, state: IntelligenceWorkflowState) -> IntelligenceWorkflowState:
        self.runtime.checkpoints.clear()
        current = initialize_intelligence_state_node(state, self.runtime)
        self.runtime.checkpoints.append(dict(current))

        current = run_upstream_scraping_node(current, self.runtime)
        self.runtime.checkpoints.append(dict(current))

        current = persist_upstream_artifacts_node(current, self.runtime)
        self.runtime.checkpoints.append(dict(current))

        current = run_downstream_for_profiles_node(current, self.runtime)
        self.runtime.checkpoints.append(dict(current))

        current = decide_intelligence_final_next_action_node(current, self.runtime)
        self.runtime.checkpoints.append(dict(current))
        return current


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


def build_local_intelligence_workflow(runtime: IntelligenceWorkflowRuntime) -> LocalIntelligenceWorkflow:
    return LocalIntelligenceWorkflow(runtime)


def build_intelligence_langgraph(
    runtime: IntelligenceWorkflowRuntime,
    *,
    checkpointer: Any = None,
) -> Any:
    """Compile the optional full LangGraph workflow when available."""

    try:
        from langgraph.graph import END, StateGraph  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise RuntimeError("Install langgraph to build the production intelligence graph") from exc

    graph = StateGraph(IntelligenceWorkflowState)
    graph.add_node(
        "initialize_intelligence_state",
        lambda state: initialize_intelligence_state_node(state, runtime),
    )
    graph.add_node(
        "run_upstream_scraping",
        lambda state: run_upstream_scraping_node(state, runtime),
    )
    graph.add_node(
        "persist_upstream_artifacts",
        lambda state: persist_upstream_artifacts_node(state, runtime),
    )
    graph.add_node(
        "run_downstream_for_profiles",
        lambda state: run_downstream_for_profiles_node(state, runtime),
    )
    graph.add_node(
        "decide_intelligence_final_next_action",
        lambda state: decide_intelligence_final_next_action_node(state, runtime),
    )

    graph.set_entry_point("initialize_intelligence_state")
    graph.add_edge("initialize_intelligence_state", "run_upstream_scraping")
    graph.add_edge("run_upstream_scraping", "persist_upstream_artifacts")
    graph.add_edge("persist_upstream_artifacts", "run_downstream_for_profiles")
    graph.add_edge("run_downstream_for_profiles", "decide_intelligence_final_next_action")
    graph.add_edge("decide_intelligence_final_next_action", END)

    compile_kwargs = {"checkpointer": checkpointer} if checkpointer is not None else {}
    return graph.compile(**compile_kwargs)


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


def initialize_intelligence_state_node(
    state: IntelligenceWorkflowState,
    runtime: IntelligenceWorkflowRuntime,
) -> IntelligenceWorkflowState:
    return _merge(
        state,
        run_id=state.get("run_id", "local-intelligence-run"),
        branch_decisions=state.get("branch_decisions", ()),
        errors=state.get("errors", ()),
        persistence_references=state.get("persistence_references", ()),
    )


def run_upstream_scraping_node(
    state: IntelligenceWorkflowState,
    runtime: IntelligenceWorkflowRuntime,
) -> IntelligenceWorkflowState:
    if _has_reusable_upstream_artifacts(state):
        return state

    scraping_state = build_local_scraping_graph(runtime.scraping).invoke(
        {
            "run_id": state["run_id"],
            "query": state["query"],
            "limit": state.get("limit", runtime.scraping.per_term_limit),
        }
    )
    return _append_upstream_search_errors(_merge(state, **scraping_state))


def persist_upstream_artifacts_node(
    state: IntelligenceWorkflowState,
    runtime: IntelligenceWorkflowRuntime,
) -> IntelligenceWorkflowState:
    if runtime.artifact_store is None:
        return state

    try:
        _ensure_persistence_run(runtime.artifact_store, state["run_id"])
        runtime.artifact_store.save_pipeline_result(state["run_id"], _scraping_result_from_state(state))
        runtime.artifact_store.save_ai_native_assessments(
            state["run_id"],
            state.get("ai_native_assessments_by_profile", {}),
        )
    except Exception as exc:
        return _append_error(
            state,
            step="persist_upstream_artifacts",
            error_type=type(exc).__name__,
            message=str(exc),
            audit_reason="upstream_storage_failed_structured_error",
        )

    return _append_persistence_reference(
        state,
        artifact_kind="upstream_run",
        startup_identifier="*",
        storage=type(runtime.artifact_store).__name__,
        reference=state["run_id"],
    )


def _ensure_persistence_run(store: IntelligenceArtifactStore, run_id: str) -> None:
    load_run = getattr(store, "load_run", None)
    if callable(load_run):
        try:
            load_run(run_id)
            return
        except KeyError:
            pass
    store.create_run(run_id=run_id)


def _scraping_result_from_state(state: IntelligenceWorkflowState) -> ScrapingPipelineResult:
    return ScrapingPipelineResult(
        search_params=state["search_params"],
        search_plan=state["search_plan"],
        raw_results=state.get("raw_results", ()),
        candidates=state.get("candidates", ()),
        collected_pages_by_candidate=state.get("collected_pages_by_candidate", {}),
        profiles=state.get("profiles", ()),
        evidence_groups_by_profile=state.get("evidence_groups_by_profile", {}),
        quality_summary=state["quality_summary"],
        search_errors=state.get("search_errors", ()),
    )


def _has_reusable_upstream_artifacts(state: IntelligenceWorkflowState) -> bool:
    return bool(
        state.get("profiles")
        and state.get("evidence_groups_by_profile") is not None
        and state.get("quality_summary") is not None
        and state.get("ai_native_assessments_by_profile") is not None
    )


def _append_upstream_search_errors(state: IntelligenceWorkflowState) -> IntelligenceWorkflowState:
    current: IntelligenceWorkflowState = state
    for search_error in state.get("search_errors", ()):
        current = _append_error(
            current,
            step="execute_search",
            error_type=search_error.error_type,
            message=search_error.message,
            audit_reason="search_adapter_failed_structured_error",
        )
    return current


def run_downstream_for_profiles_node(
    state: IntelligenceWorkflowState,
    runtime: IntelligenceWorkflowRuntime,
) -> IntelligenceWorkflowState:
    profiles = state.get("profiles", ())
    assessments = state.get("ai_native_assessments_by_profile", {})
    quality_summary = state.get("quality_summary")
    downstream_states: dict[str, DownstreamWorkflowState] = {}
    branches: list[DownstreamWorkflowBranch] = list(state.get("branch_decisions", ()))
    errors: list[DownstreamWorkflowError] = list(state.get("errors", ()))
    startup_identifiers: list[str] = []

    if quality_summary is None:
        return _append_error(
            state,
            step="run_downstream_for_profiles",
            error_type="missing_collection_quality",
            message="Collection quality summary is required before downstream orchestration.",
            audit_reason="downstream_skipped_missing_collection_quality",
        )

    for profile in profiles:
        startup_identifier = profile.company_name.value
        startup_identifiers.append(startup_identifier)
        assessment = assessments.get(startup_identifier)
        if assessment is None:
            continue

        downstream_workflow = build_local_downstream_workflow(runtime.downstream)
        downstream_state = downstream_workflow.invoke(
            {
                "run_id": state["run_id"],
                "user_query": state.get("query", ""),
                "profile": profile,
                "evidence_groups": state.get("evidence_groups_by_profile", {}).get(
                    profile_result_key(profile),
                    (),
                ),
                "collection_quality": quality_summary,
                "assessment": assessment,
            }
        )
        downstream_states[startup_identifier] = downstream_state
        branches.extend(downstream_state.get("branch_decisions", ()))
        errors.extend(downstream_state.get("errors", ()))

    corpus_version = _workflow_corpus_version(runtime.downstream, downstream_states)
    return _merge(
        state,
        startup_identifiers=tuple(startup_identifiers),
        corpus_version=corpus_version,
        downstream_states_by_startup=downstream_states,
        branch_decisions=tuple(branches),
        persistence_references=(
            *state.get("persistence_references", ()),
            *_downstream_persistence_references(runtime.downstream, downstream_states),
        ),
        errors=tuple(errors),
    )


def decide_intelligence_final_next_action_node(
    state: IntelligenceWorkflowState,
    runtime: IntelligenceWorkflowRuntime,
) -> IntelligenceWorkflowState:
    downstream_states = state.get("downstream_states_by_startup", {})
    if downstream_states:
        if any(item.get("workflow_outcome") == "briefing_generated" for item in downstream_states.values()):
            outcome = "briefing_generated"
        elif any(item.get("workflow_outcome") == "human_review_requested" for item in downstream_states.values()):
            outcome = "human_review_requested"
        else:
            outcome = "needs_more_collection_or_human_review"
        first_state = next(iter(downstream_states.values()))
        return _merge(
            state,
            workflow_outcome=outcome,
            next_action=first_state.get("next_action", "review_workflow_output"),
        )

    if state.get("errors"):
        return _merge(
            _append_branch(
                state,
                branch_name="failed_with_auditable_error",
                next_action="review_workflow_errors",
                audit_reason=";".join(dict.fromkeys(error.audit_reason for error in state.get("errors", ()))),
            ),
            workflow_outcome="failed_with_auditable_error",
            next_action="review_workflow_errors",
        )

    if state.get("next_action") == "needs_more_collection_or_human_review":
        return _merge(state, workflow_outcome="needs_more_collection_or_human_review")

    return _merge(state, workflow_outcome="needs_more_collection_or_human_review")


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


def _workflow_corpus_version(
    runtime: DownstreamWorkflowRuntime,
    downstream_states: Mapping[str, DownstreamWorkflowState],
) -> str:
    if runtime.corpus is not None:
        return runtime.corpus.corpus_version
    for downstream_state in downstream_states.values():
        for retrieval in downstream_state.get("retrievals", ()):
            return retrieval.corpus_version
    return UNKNOWN


def _downstream_persistence_references(
    runtime: DownstreamWorkflowRuntime,
    downstream_states: Mapping[str, DownstreamWorkflowState],
) -> tuple[WorkflowPersistenceReference, ...]:
    if runtime.artifact_store is None:
        return ()
    return tuple(
        WorkflowPersistenceReference(
            artifact_kind="downstream_artifacts",
            startup_identifier=startup_identifier,
            storage=type(runtime.artifact_store).__name__,
            reference=downstream_state.get("run_id", ""),
        )
        for startup_identifier, downstream_state in downstream_states.items()
    )


def _append_persistence_reference(
    state: IntelligenceWorkflowState,
    *,
    artifact_kind: str,
    startup_identifier: str,
    storage: str,
    reference: str,
) -> IntelligenceWorkflowState:
    persistence_reference = WorkflowPersistenceReference(
        artifact_kind=artifact_kind,
        startup_identifier=startup_identifier,
        storage=storage,
        reference=reference,
    )
    return _merge(
        state,
        persistence_references=(*state.get("persistence_references", ()), persistence_reference),
    )


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
