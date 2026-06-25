"""LangGraph-compatible orchestration for the scraping pipeline.

The graph nodes delegate to deterministic pipeline functions. A small local
runner keeps tests independent from the optional LangGraph dependency, while
``build_langgraph`` uses LangGraph when it is installed.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass, field
from typing import Any, TypedDict

from nvidia_startup_intel.ai_native_assessment import AINativeAssessment
from nvidia_startup_intel.collection_quality import summarize_collection_quality
from nvidia_startup_intel.discovery import CandidateStartup, RawDiscoveryResult
from nvidia_startup_intel.evidence import FieldEvidenceGroup
from nvidia_startup_intel.page_collection import Fetcher, PageCollectionResult
from nvidia_startup_intel.pipeline import (
    build_candidates,
    collect_pages_for_candidates,
    assess_profiles_ai_native,
    extract_profiles_for_candidates,
    plan_startup_search,
    structure_profile_evidence,
)
from nvidia_startup_intel.robots import RobotsCache
from nvidia_startup_intel.scraping_policy import ScrapingPolicy
from nvidia_startup_intel.search_execution import SearchClient, SearchExecutionError, execute_search_plan
from nvidia_startup_intel.search_params import SearchParams
from nvidia_startup_intel.search_plan import SearchPlan
from nvidia_startup_intel.startup_profile import StartupProfile


class ScrapingGraphState(TypedDict, total=False):
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
    quality_summary: Any
    next_action: str
    errors: tuple[str, ...]


@dataclass
class ScrapingGraphRuntime:
    search_client: SearchClient
    fetcher: Fetcher | None = None
    scraping_policy: ScrapingPolicy | None = None
    robots_cache: RobotsCache | None = None
    per_term_limit: int = 5
    max_pages_per_candidate: int = 5
    max_depth: int = 1
    checkpoints: list[ScrapingGraphState] = field(default_factory=list)


class LocalScrapingGraph:
    """Small invoke-compatible runner mirroring the LangGraph node flow."""

    def __init__(self, runtime: ScrapingGraphRuntime) -> None:
        self.runtime = runtime

    def invoke(self, state: ScrapingGraphState) -> ScrapingGraphState:
        self.runtime.checkpoints.clear()
        current: ScrapingGraphState = dict(state)
        for node in (
            plan_search_node,
            execute_search_node,
            discover_candidates_node,
            collect_pages_node,
            extract_profiles_node,
            structure_evidence_node,
            measure_quality_node,
            assess_ai_native_node,
            decide_next_action_node,
        ):
            current = node(current, self.runtime)
            self.runtime.checkpoints.append(dict(current))
        return current


def build_local_scraping_graph(runtime: ScrapingGraphRuntime) -> LocalScrapingGraph:
    return LocalScrapingGraph(runtime)


def build_langgraph(runtime: ScrapingGraphRuntime) -> Any:
    """Compile a LangGraph graph when the optional dependency is installed."""

    try:
        from langgraph.graph import END, StateGraph  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise RuntimeError("Install langgraph to build the production scraping graph") from exc

    graph = StateGraph(ScrapingGraphState)
    graph.add_node("plan_search", lambda state: plan_search_node(state, runtime))
    graph.add_node("execute_search", lambda state: execute_search_node(state, runtime))
    graph.add_node("discover_candidates", lambda state: discover_candidates_node(state, runtime))
    graph.add_node("collect_pages", lambda state: collect_pages_node(state, runtime))
    graph.add_node("extract_profiles", lambda state: extract_profiles_node(state, runtime))
    graph.add_node("structure_evidence", lambda state: structure_evidence_node(state, runtime))
    graph.add_node("measure_quality", lambda state: measure_quality_node(state, runtime))
    graph.add_node("assess_ai_native", lambda state: assess_ai_native_node(state, runtime))
    graph.add_node("decide_next_action", lambda state: decide_next_action_node(state, runtime))
    graph.set_entry_point("plan_search")
    graph.add_edge("plan_search", "execute_search")
    graph.add_edge("execute_search", "discover_candidates")
    graph.add_edge("discover_candidates", "collect_pages")
    graph.add_edge("collect_pages", "extract_profiles")
    graph.add_edge("extract_profiles", "structure_evidence")
    graph.add_edge("structure_evidence", "measure_quality")
    graph.add_edge("measure_quality", "assess_ai_native")
    graph.add_edge("assess_ai_native", "decide_next_action")
    graph.add_edge("decide_next_action", END)
    return graph.compile()


def plan_search_node(state: ScrapingGraphState, runtime: ScrapingGraphRuntime) -> ScrapingGraphState:
    params, plan = plan_startup_search(state["query"], limit=state.get("limit"))
    return _merge(state, search_params=params, search_plan=plan)


def execute_search_node(state: ScrapingGraphState, runtime: ScrapingGraphRuntime) -> ScrapingGraphState:
    params = state["search_params"]
    execution = execute_search_plan(
        state["search_plan"],
        runtime.search_client,
        per_term_limit=runtime.per_term_limit,
        total_limit=params.limit,
    )
    return _merge(state, raw_results=execution.raw_results, search_errors=execution.errors)


def discover_candidates_node(state: ScrapingGraphState, runtime: ScrapingGraphRuntime) -> ScrapingGraphState:
    params = state["search_params"]
    candidates = build_candidates(state.get("raw_results", ()), limit=params.limit)
    return _merge(state, candidates=candidates)


def collect_pages_node(state: ScrapingGraphState, runtime: ScrapingGraphRuntime) -> ScrapingGraphState:
    collected = collect_pages_for_candidates(
        state.get("candidates", ()),
        fetcher=runtime.fetcher,
        scraping_policy=runtime.scraping_policy,
        robots_cache=runtime.robots_cache,
        max_pages_per_candidate=runtime.max_pages_per_candidate,
        max_depth=runtime.max_depth,
    )
    return _merge(state, collected_pages_by_candidate=collected)


def extract_profiles_node(state: ScrapingGraphState, runtime: ScrapingGraphRuntime) -> ScrapingGraphState:
    profiles = extract_profiles_for_candidates(
        state.get("candidates", ()),
        state.get("collected_pages_by_candidate", {}),
    )
    return _merge(state, profiles=profiles)


def structure_evidence_node(state: ScrapingGraphState, runtime: ScrapingGraphRuntime) -> ScrapingGraphState:
    groups = structure_profile_evidence(state.get("profiles", ()))
    return _merge(state, evidence_groups_by_profile=groups)


def measure_quality_node(state: ScrapingGraphState, runtime: ScrapingGraphRuntime) -> ScrapingGraphState:
    summary = summarize_collection_quality(
        state.get("candidates", ()),
        state.get("profiles", ()),
        collection_results_by_source=state.get("collected_pages_by_candidate", {}),
    )
    return _merge(state, quality_summary=summary)


def assess_ai_native_node(state: ScrapingGraphState, runtime: ScrapingGraphRuntime) -> ScrapingGraphState:
    assessments = assess_profiles_ai_native(
        state.get("profiles", ()),
        state.get("evidence_groups_by_profile", {}),
        state["quality_summary"],
        run_id=state.get("run_id", "local-graph-run"),
    )
    return _merge(state, ai_native_assessments_by_profile=assessments)


def decide_next_action_node(state: ScrapingGraphState, runtime: ScrapingGraphRuntime) -> ScrapingGraphState:
    summary = state["quality_summary"]
    if not summary.ready_for_evaluation:
        next_action = "needs_more_collection_or_human_review"
    else:
        next_action = "proceed_to_ai_native_evaluation"
    return _merge(state, next_action=next_action)


def _merge(state: ScrapingGraphState, **updates: Any) -> ScrapingGraphState:
    current: MutableMapping[str, Any] = dict(state)
    current.update(updates)
    return dict(current)  # type: ignore[return-value]
