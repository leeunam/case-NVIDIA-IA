from nvidia_startup_intel.page_collection import FetchResponse
from nvidia_startup_intel.pipeline import fixture_fetcher
from nvidia_startup_intel.robots import RobotsCache
from nvidia_startup_intel.search_execution import SearchProviderResult
from nvidia_startup_intel.scraping_graph import ScrapingGraphRuntime, build_local_scraping_graph


class FakeSearchClient:
    provider_name = "fake"

    def __init__(self, results: tuple[SearchProviderResult, ...]) -> None:
        self.results = results

    def search(self, query: str, *, limit: int) -> tuple[SearchProviderResult, ...]:
        return self.results[:limit]


def allow_robots() -> RobotsCache:
    return RobotsCache(fetcher=lambda url: "User-agent: *\nAllow: /\n")


def test_scraping_graph_runs_happy_path_with_fixture_data() -> None:
    runtime = ScrapingGraphRuntime(
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
                        "Resumo: IA para documentos. Setor: dados. "
                        "Produto: Plataforma de IA documental. "
                        "Sinais de IA: modelos de IA proprietarios. "
                        "Clientes: bancos. Founders: Ana Silva. "
                        "Tecnologias: machine learning. Localizacao: Campinas, SP."
                        "</body></html>"
                    ),
                )
            }
        ),
        robots_cache=allow_robots(),
        per_term_limit=1,
        max_pages_per_candidate=1,
    )
    graph = build_local_scraping_graph(runtime)

    state = graph.invoke({"query": "startups AI-native do Brasil", "limit": 1})
    second_state = graph.invoke({"query": "startups AI-native do Brasil", "limit": 1})

    assert state["next_action"] == "proceed_to_ai_native_evaluation"
    assert second_state["next_action"] == "proceed_to_ai_native_evaluation"
    assert state["quality_summary"].ready_for_evaluation is True
    assert state["evidence_groups_by_profile"]
    assert len(runtime.checkpoints) == 8


def test_scraping_graph_flags_insufficient_quality_for_human_review() -> None:
    runtime = ScrapingGraphRuntime(
        search_client=FakeSearchClient(
            (
                SearchProviderResult(
                    title="Startup Sem Site",
                    url="https://distrito.me/startups/sem-site",
                    snippet="Citada em diretorio.",
                    position=1,
                ),
            )
        ),
        per_term_limit=1,
        max_pages_per_candidate=1,
    )
    graph = build_local_scraping_graph(runtime)

    state = graph.invoke({"query": "startups AI-native do Brasil", "limit": 1})

    assert state["next_action"] == "needs_more_collection_or_human_review"
    assert state["quality_summary"].ready_for_evaluation is False
    assert "minimum_profile_coverage_below_threshold" in state["quality_summary"].readiness_reasons
