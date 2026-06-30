from pathlib import Path
import os

import pytest

from nvidia_startup_intel.nvidia_knowledge import load_nvidia_knowledge_corpus
from nvidia_startup_intel.page_collection import FetchResponse
from nvidia_startup_intel.pipeline import fixture_fetcher
from nvidia_startup_intel.robots import RobotsCache
from nvidia_startup_intel.scraping_graph import ScrapingGraphRuntime
from nvidia_startup_intel.search_execution import SearchProviderResult
from nvidia_startup_intel.workflow_graph import (
    DownstreamWorkflowRuntime,
    IntelligenceWorkflowRuntime,
    build_intelligence_langgraph,
    build_local_intelligence_workflow,
)


pytestmark = pytest.mark.langgraph_checkpoint_integration


class FakeSearchClient:
    provider_name = "fake"

    def __init__(self, results: tuple[SearchProviderResult, ...]) -> None:
        self.results = results

    def search(self, query: str, *, limit: int) -> tuple[SearchProviderResult, ...]:
        return self.results[:limit]


class ExplodingSearchClient:
    provider_name = "exploding"

    def search(self, query: str, *, limit: int) -> tuple[SearchProviderResult, ...]:
        raise AssertionError("checkpoint resume smoke must not repeat scraping")


@pytest.mark.skipif(
    os.environ.get("NVIDIA_STARTUP_INTEL_RUN_LANGGRAPH_CHECKPOINT_SMOKE") != "1",
    reason="optional real LangGraph/Postgres checkpoint smoke is disabled",
)
def test_real_langgraph_postgres_checkpoint_resumes_from_loaded_upstream_artifacts() -> None:
    database_url = os.environ.get("NVIDIA_STARTUP_INTEL_LANGGRAPH_CHECKPOINT_DATABASE_URL") or os.environ.get(
        "DATABASE_URL",
    )
    if not database_url:
        pytest.fail(
            "Set NVIDIA_STARTUP_INTEL_LANGGRAPH_CHECKPOINT_DATABASE_URL or DATABASE_URL "
            "to run the optional LangGraph checkpoint smoke.",
        )

    checkpointer = _postgres_checkpointer(database_url)
    seed_state = _seed_upstream_state()
    runtime = IntelligenceWorkflowRuntime(
        scraping=ScrapingGraphRuntime(search_client=ExplodingSearchClient()),
        downstream=DownstreamWorkflowRuntime(corpus=load_nvidia_knowledge_corpus(_fixture_path())),
    )
    graph = build_intelligence_langgraph(runtime, checkpointer=checkpointer)

    state = graph.invoke(
        {
            "run_id": "run-langgraph-checkpoint-smoke",
            "query": "startups AI-native do Brasil",
            "search_params": seed_state["search_params"],
            "search_plan": seed_state["search_plan"],
            "raw_results": seed_state["raw_results"],
            "candidates": seed_state["candidates"],
            "collected_pages_by_candidate": seed_state["collected_pages_by_candidate"],
            "profiles": seed_state["profiles"],
            "evidence_groups_by_profile": seed_state["evidence_groups_by_profile"],
            "quality_summary": seed_state["quality_summary"],
            "ai_native_assessments_by_profile": seed_state["ai_native_assessments_by_profile"],
        },
        config={"configurable": {"thread_id": "run-langgraph-checkpoint-smoke"}},
    )

    assert state["workflow_outcome"] == "briefing_generated"
    assert state["startup_identifiers"] == ("NeuralMind",)
    assert state["downstream_states_by_startup"]["NeuralMind"]["executive_briefing"].schema_version == (
        "executive_briefing.v1"
    )


def _postgres_checkpointer(database_url: str) -> object:
    try:
        from langgraph.checkpoint.postgres import PostgresSaver  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        pytest.fail(f"Install langgraph-checkpoint-postgres to run this smoke: {exc}")

    checkpointer = PostgresSaver.from_conn_string(database_url)
    setup = getattr(checkpointer, "setup", None)
    if callable(setup):
        setup()
    return checkpointer


def _seed_upstream_state() -> dict[str, object]:
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
    return build_local_intelligence_workflow(runtime).invoke(
        {
            "run_id": "run-langgraph-checkpoint-seed",
            "query": "startups AI-native do Brasil",
            "limit": 1,
        }
    )


def _fixture_path() -> Path:
    return Path(__file__).parents[1] / "fixtures" / "nvidia_knowledge_official_fixture.json"
