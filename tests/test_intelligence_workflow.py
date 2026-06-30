from pathlib import Path
import sys
from types import ModuleType
from unittest.mock import patch

from nvidia_startup_intel.nvidia_knowledge import load_nvidia_knowledge_corpus
from nvidia_startup_intel.page_collection import FetchResponse
from nvidia_startup_intel.pipeline import fixture_fetcher
from nvidia_startup_intel.robots import RobotsCache
from nvidia_startup_intel.scraping_graph import ScrapingGraphRuntime
from nvidia_startup_intel.search_execution import SearchProviderResult
from nvidia_startup_intel.sql_repository import sqlite_repository
from nvidia_startup_intel.workflow_graph import (
    DownstreamWorkflowRuntime,
    IntelligenceWorkflowRuntime,
    build_intelligence_langgraph,
    build_local_intelligence_workflow,
)


class FakeSearchClient:
    provider_name = "fake"

    def __init__(self, results: tuple[SearchProviderResult, ...]) -> None:
        self.results = results

    def search(self, query: str, *, limit: int) -> tuple[SearchProviderResult, ...]:
        return self.results[:limit]


class ExplodingSearchClient:
    provider_name = "exploding"

    def search(self, query: str, *, limit: int) -> tuple[SearchProviderResult, ...]:
        raise AssertionError("resume path must not repeat search or scraping")


class TimeoutSearchClient:
    provider_name = "timeout"

    def search(self, query: str, *, limit: int) -> tuple[SearchProviderResult, ...]:
        raise TimeoutError("search provider timeout")


def test_local_intelligence_workflow_generates_briefing_from_search_to_recommendation() -> None:
    runtime = IntelligenceWorkflowRuntime(
        scraping=ScrapingGraphRuntime(
            search_client=FakeSearchClient(
                (
                    SearchProviderResult(
                        title="NeuralMind",
                        url="https://neuralmind.ai/",
                        snippet="NeuralMind desenvolve IA para documentos.",
                        position=1,
                    ),
                )
            ),
            fetcher=fixture_fetcher(
                {
                    "https://neuralmind.ai": FetchResponse(
                        url="https://neuralmind.ai/",
                        status_code=200,
                        body=(
                            "<html><head><title>NeuralMind</title></head><body>"
                            "Resumo: Plataforma AI-native para documentos. Setor: dados. "
                            "Produto: Copiloto documental com IA generativa. "
                            "Sinais de IA: modelos proprietarios, fine-tuning, "
                            "inferencia em producao e latencia. "
                            "Tecnologias: MLOps, dados proprietarios, feedback loop, "
                            "model serving e inferencia em producao. "
                            "Clientes: bancos. Founders: Ana Silva. "
                            "Localizacao: Campinas, SP."
                            "</body></html>"
                        ),
                    )
                }
            ),
            robots_cache=RobotsCache(fetcher=lambda url: "User-agent: *\nAllow: /\n"),
            per_term_limit=1,
            max_pages_per_candidate=1,
        ),
        downstream=DownstreamWorkflowRuntime(corpus=load_nvidia_knowledge_corpus(_fixture_path())),
    )
    workflow = build_local_intelligence_workflow(runtime)

    state = workflow.invoke(
        {
            "run_id": "run-issue-82",
            "query": "startups AI-native do Brasil",
            "limit": 1,
        }
    )

    assert state["run_id"] == "run-issue-82"
    assert state["workflow_outcome"] == "briefing_generated"
    assert state["next_action"] == "prepare_technical_outreach"
    assert state["startup_identifiers"] == ("NeuralMind",)
    assert state["corpus_version"] == "official-nvidia-fixture.v1"
    assert state["errors"] == ()
    assert state["persistence_references"] == ()
    assert state["profiles"][0].schema_version == "startup_profile.v1"
    assert state["ai_native_assessments_by_profile"]["NeuralMind"].schema_version == "ai_native_assessment.v1"
    assert state["downstream_states_by_startup"]["NeuralMind"]["recommendation_set"].schema_version == (
        "nvidia_recommendation.v1"
    )
    assert state["downstream_states_by_startup"]["NeuralMind"]["executive_briefing"].schema_version == (
        "executive_briefing.v1"
    )
    assert tuple(branch.branch_name for branch in state["branch_decisions"]) == (
        "ready_for_recommendation",
        "ready_for_briefing",
        "briefing_generated",
    )
    assert all(branch.audit_reason for branch in state["branch_decisions"])


def test_local_intelligence_workflow_resumes_downstream_from_loaded_upstream_artifacts() -> None:
    initial_state = _successful_state()
    runtime = IntelligenceWorkflowRuntime(
        scraping=ScrapingGraphRuntime(search_client=ExplodingSearchClient()),
        downstream=DownstreamWorkflowRuntime(corpus=load_nvidia_knowledge_corpus(_fixture_path())),
    )
    workflow = build_local_intelligence_workflow(runtime)

    state = workflow.invoke(
        {
            "run_id": "run-issue-82-resume",
            "query": "startups AI-native do Brasil",
            "search_params": initial_state["search_params"],
            "search_plan": initial_state["search_plan"],
            "raw_results": initial_state["raw_results"],
            "candidates": initial_state["candidates"],
            "collected_pages_by_candidate": initial_state["collected_pages_by_candidate"],
            "profiles": initial_state["profiles"],
            "evidence_groups_by_profile": initial_state["evidence_groups_by_profile"],
            "quality_summary": initial_state["quality_summary"],
            "ai_native_assessments_by_profile": initial_state["ai_native_assessments_by_profile"],
        }
    )

    assert state["workflow_outcome"] == "briefing_generated"
    assert state["startup_identifiers"] == ("NeuralMind",)
    assert state["profiles"] == initial_state["profiles"]
    assert state["raw_results"] == initial_state["raw_results"]
    assert runtime.scraping.checkpoints == []
    assert state["downstream_states_by_startup"]["NeuralMind"]["executive_briefing"].schema_version == (
        "executive_briefing.v1"
    )


def test_local_intelligence_workflow_persists_upstream_and_downstream_artifacts() -> None:
    repository = sqlite_repository()
    runtime = _successful_runtime()
    runtime.artifact_store = repository
    runtime.downstream.artifact_store = repository
    workflow = build_local_intelligence_workflow(runtime)

    state = workflow.invoke(
        {
            "run_id": "run-issue-82-persisted",
            "query": "startups AI-native do Brasil",
            "limit": 1,
        }
    )
    stored = repository.load_operational_run("run-issue-82-persisted", startup_identifier="NeuralMind")

    assert state["errors"] == ()
    assert stored.upstream.startup_profiles[0]["schema_version"] == "startup_profile.v1"
    assert stored.upstream.ai_native_assessments[0]["schema_version"] == "ai_native_assessment.v1"
    assert stored.downstream.retrievals[0]["schema_version"] == "nvidia_knowledge.v1"
    assert stored.downstream.recommendation_sets[0]["schema_version"] == "nvidia_recommendation.v1"
    assert stored.downstream.briefings[0]["schema_version"] == "executive_briefing.v1"
    assert tuple(ref.artifact_kind for ref in state["persistence_references"]) == (
        "upstream_run",
        "downstream_artifacts",
    )
    assert state["persistence_references"][0].reference == "run-issue-82-persisted"
    assert state["persistence_references"][1].startup_identifier == "NeuralMind"


def test_local_intelligence_workflow_surfaces_blocking_adapter_failure_as_auditable_error() -> None:
    runtime = IntelligenceWorkflowRuntime(
        scraping=ScrapingGraphRuntime(
            search_client=TimeoutSearchClient(),
            per_term_limit=1,
            max_pages_per_candidate=1,
        ),
        downstream=DownstreamWorkflowRuntime(corpus=load_nvidia_knowledge_corpus(_fixture_path())),
    )
    workflow = build_local_intelligence_workflow(runtime)

    state = workflow.invoke(
        {
            "run_id": "run-issue-82-failed",
            "query": "startups AI-native do Brasil",
            "limit": 1,
        }
    )

    assert state["workflow_outcome"] == "failed_with_auditable_error"
    assert state["raw_results"] == ()
    assert state["profiles"] == ()
    assert state["search_errors"][0].error_type == "TimeoutError"
    assert state["errors"][0].step == "execute_search"
    assert state["errors"][0].audit_reason == "search_adapter_failed_structured_error"
    assert state["branch_decisions"][-1].branch_name == "failed_with_auditable_error"
    assert state["branch_decisions"][-1].audit_reason == "search_adapter_failed_structured_error"


def test_optional_intelligence_langgraph_builder_uses_injected_checkpointer() -> None:
    runtime = _successful_runtime()
    checkpointer = object()

    with fake_langgraph_modules():
        graph = build_intelligence_langgraph(runtime, checkpointer=checkpointer)

    state = graph.invoke(
        {
            "run_id": "run-issue-82-langgraph",
            "query": "startups AI-native do Brasil",
            "limit": 1,
        }
    )

    assert graph.graph.compile_kwargs == {"checkpointer": checkpointer}
    assert state["workflow_outcome"] == "briefing_generated"
    assert state["startup_identifiers"] == ("NeuralMind",)
    assert state["corpus_version"] == "official-nvidia-fixture.v1"


def _successful_state() -> dict[str, object]:
    return build_local_intelligence_workflow(_successful_runtime()).invoke(
        {
            "run_id": "run-issue-82-seed",
            "query": "startups AI-native do Brasil",
            "limit": 1,
        }
    )


def _successful_runtime() -> IntelligenceWorkflowRuntime:
    return IntelligenceWorkflowRuntime(
        scraping=ScrapingGraphRuntime(
            search_client=FakeSearchClient(
                (
                    SearchProviderResult(
                        title="NeuralMind",
                        url="https://neuralmind.ai/",
                        snippet="NeuralMind desenvolve IA para documentos.",
                        position=1,
                    ),
                )
            ),
            fetcher=fixture_fetcher(
                {
                    "https://neuralmind.ai": FetchResponse(
                        url="https://neuralmind.ai/",
                        status_code=200,
                        body=(
                            "<html><head><title>NeuralMind</title></head><body>"
                            "Resumo: Plataforma AI-native para documentos. Setor: dados. "
                            "Produto: Copiloto documental com IA generativa. "
                            "Sinais de IA: modelos proprietarios, fine-tuning, "
                            "inferencia em producao e latencia. "
                            "Tecnologias: MLOps, dados proprietarios, feedback loop, "
                            "model serving e inferencia em producao. "
                            "Clientes: bancos. Founders: Ana Silva. "
                            "Localizacao: Campinas, SP."
                            "</body></html>"
                        ),
                    )
                }
            ),
            robots_cache=RobotsCache(fetcher=lambda url: "User-agent: *\nAllow: /\n"),
            per_term_limit=1,
            max_pages_per_candidate=1,
        ),
        downstream=DownstreamWorkflowRuntime(corpus=load_nvidia_knowledge_corpus(_fixture_path())),
    )


def _fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "nvidia_knowledge_official_fixture.json"


class FakeCompiledStateGraph:
    def __init__(self, graph: "FakeStateGraph", *, compile_kwargs: dict[str, object]) -> None:
        self.graph = graph
        self.graph.compile_kwargs = compile_kwargs

    def invoke(self, state: dict[str, object]) -> dict[str, object]:
        current = dict(state)
        node_name = self.graph.entry_point
        while node_name != self.graph.end_marker:
            current = self.graph.nodes[node_name](current)
            node_name = self.graph.edges[node_name]
        return current


class FakeStateGraph:
    def __init__(self, state_type: object) -> None:
        self.state_type = state_type
        self.end_marker = "__end__"
        self.nodes: dict[str, object] = {}
        self.edges: dict[str, str] = {}
        self.entry_point = ""
        self.compile_kwargs: dict[str, object] = {}

    def add_node(self, name: str, node: object) -> None:
        self.nodes[name] = node

    def set_entry_point(self, name: str) -> None:
        self.entry_point = name

    def add_edge(self, source: str, target: str) -> None:
        self.edges[source] = target

    def compile(self, **kwargs: object) -> FakeCompiledStateGraph:
        return FakeCompiledStateGraph(self, compile_kwargs=kwargs)


def fake_langgraph_modules() -> object:
    langgraph_module = ModuleType("langgraph")
    graph_module = ModuleType("langgraph.graph")
    graph_module.END = "__end__"
    graph_module.StateGraph = FakeStateGraph
    langgraph_module.graph = graph_module
    return patch.dict(sys.modules, {"langgraph": langgraph_module, "langgraph.graph": graph_module})
