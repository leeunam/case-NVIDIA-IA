from __future__ import annotations

from datetime import UTC, datetime
from io import StringIO
import json

from nvidia_startup_intel.cli import main
from nvidia_startup_intel.page_collection import FetchResponse
from nvidia_startup_intel.search_execution import SearchProviderResult
from nvidia_startup_intel.sql_repository import sqlite_repository


FIXED_TIME = datetime(2026, 6, 26, 9, 30, tzinfo=UTC)


def fixed_clock() -> datetime:
    return FIXED_TIME


def test_collect_pages_cli_outputs_controlled_collection_json() -> None:
    stdout = StringIO()
    pages = {
        "https://startup.ai": FetchResponse(
            url="https://startup.ai/",
            status_code=200,
            body=(
                "<html><head><title>Startup AI</title></head>"
                "<body>Resumo: Plataforma AI-native brasileira.</body></html>"
            ),
        )
    }

    exit_code = main(
        [
            "collect-pages",
            "https://startup.ai/",
            "--max-pages",
            "1",
            "--max-depth",
            "0",
        ],
        stdout=stdout,
        fetcher=_fetcher(pages),
        playwright_renderer=_fetcher(pages),
        robots_fetcher=_allow_robots,
        clock=fixed_clock,
    )

    payload = json.loads(stdout.getvalue())

    assert exit_code == 0
    assert payload["schema_version"] == "collection_cli_result.v1"
    assert payload["run_id"] == "cli-20260626T093000Z"
    assert payload["input_url"] == "https://startup.ai/"
    assert payload["options"]["max_pages"] == 1
    assert payload["options"]["max_depth"] == 0
    assert payload["options"]["render_js"] is True
    assert payload["options"]["robots_policy"] == "conservative"
    assert payload["pages"][0]["url"] == "https://startup.ai"
    assert payload["pages"][0]["title"] == "Startup AI"
    assert "AI-native" in payload["pages"][0]["main_text"]
    assert payload["errors"] == []


def test_collect_pages_cli_can_render_javascript_with_injected_playwright_boundary() -> None:
    stdout = StringIO()

    exit_code = main(
        [
            "collect-pages",
            "https://startup.ai/",
            "--max-pages",
            "1",
        ],
        stdout=stdout,
        fetcher=_fetcher(
            {
                "https://startup.ai": FetchResponse(
                    url="https://startup.ai/",
                    status_code=200,
                    body="<html><body><div id='root'></div><script>render()</script></body></html>",
                )
            }
        ),
        playwright_renderer=_fetcher(
            {
                "https://startup.ai": FetchResponse(
                    url="https://startup.ai/",
                    status_code=200,
                    body=(
                        "<html><head><title>Startup AI Rendered</title></head>"
                        "<body>Conteudo renderizado com IA em producao.</body></html>"
                    ),
                )
            }
        ),
        robots_fetcher=_allow_robots,
        clock=fixed_clock,
    )

    payload = json.loads(stdout.getvalue())

    assert exit_code == 0
    assert payload["options"]["render_js"] is True
    assert payload["pages"][0]["title"] == "Startup AI Rendered"
    assert "renderizado" in payload["pages"][0]["main_text"]
    assert payload["pages"][0]["extraction_strategy"].endswith("+playwright")


def test_collect_pages_cli_can_disable_playwright_for_deterministic_debugging() -> None:
    stdout = StringIO()

    exit_code = main(
        [
            "collect-pages",
            "https://startup.ai/",
            "--max-pages",
            "1",
            "--no-render-js",
        ],
        stdout=stdout,
        fetcher=_fetcher(
            {
                "https://startup.ai": FetchResponse(
                    url="https://startup.ai/",
                    status_code=200,
                    body="<html><body><div id='root'></div><script>render()</script></body></html>",
                )
            }
        ),
        playwright_renderer=_fetcher(
            {
                "https://startup.ai": FetchResponse(
                    url="https://startup.ai/",
                    status_code=200,
                    body="<html><body>Conteudo renderizado.</body></html>",
                )
            }
        ),
        robots_fetcher=_allow_robots,
        clock=fixed_clock,
    )

    payload = json.loads(stdout.getvalue())

    assert exit_code == 0
    assert payload["options"]["render_js"] is False
    assert payload["pages"][0]["main_text"] == "unknown"
    assert payload["pages"][0]["needs_js_rendering"] is True


def test_collect_pages_cli_can_write_json_output_file(tmp_path) -> None:
    output_path = tmp_path / "collection.json"
    pages = {
        "https://startup.ai": FetchResponse(
            url="https://startup.ai/",
            status_code=200,
            body="<html><body>Coleta controlada.</body></html>",
        )
    }

    exit_code = main(
        [
            "collect-pages",
            "https://startup.ai/",
            "--max-pages",
            "1",
            "--output",
            str(output_path),
        ],
        fetcher=_fetcher(pages),
        playwright_renderer=_fetcher(pages),
        robots_fetcher=_allow_robots,
        clock=fixed_clock,
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["pages"][0]["main_text"] == "Coleta controlada."


def test_collect_startup_cli_saves_full_collection_run_to_sql_and_json(tmp_path) -> None:
    stdout = StringIO()
    repository = sqlite_repository()
    output_dir = tmp_path / "runs"
    pages = {
        "https://startup.ai": FetchResponse(
            url="https://startup.ai/",
            status_code=200,
            body=(
                "<html><head><title>Startup AI</title></head><body>"
                "Resumo: Plataforma AI-native brasileira. Setor: dados. "
                "Produto: Copiloto para operacoes financeiras. "
                "Sinais de IA: modelos proprietarios e fine-tuning. "
                "Tecnologias: inferencia em producao, MLOps e dados proprietarios. "
                "Clientes: bancos. Founders: Ana Silva. Localizacao: Sao Paulo, SP."
                "</body></html>"
            ),
        )
    }

    exit_code = main(
        [
            "collect-startup",
            "https://startup.ai/",
            "--startup-name",
            "Startup AI",
            "--max-pages",
            "1",
            "--max-depth",
            "0",
            "--output-dir",
            str(output_dir),
        ],
        stdout=stdout,
        fetcher=_fetcher(pages),
        playwright_renderer=_fetcher(pages),
        robots_fetcher=_allow_robots,
        clock=fixed_clock,
        sql_repository_factory=lambda: repository,
    )

    payload = json.loads(stdout.getvalue())
    loaded = repository.load_run(payload["run_id"])
    json_run_dir = output_dir / payload["run_id"]

    assert exit_code == 0
    assert payload["schema_version"] == "startup_collection_cli_result.v1"
    assert payload["run_id"] == "cli-20260626T093000Z"
    assert payload["created_at"] == "2026-06-26T09:30:00+00:00"
    assert payload["input_url"] == "https://startup.ai/"
    assert payload["candidate_identifier"] == "url:https://startup.ai"
    assert payload["startup_identifier"] == "url:https://startup.ai"
    assert payload["source_urls"] == ["https://startup.ai"]
    assert payload["postgres"]["persisted"] is True
    assert payload["json_run_dir"] == str(json_run_dir)

    assert loaded.created_at == "2026-06-26T09:30:00+00:00"
    assert loaded.candidate_startups[0]["candidate_key"] == "url:https://startup.ai"
    assert loaded.candidate_startups[0]["name"] == "Startup AI"
    assert loaded.collected_pages[0]["url"] == "https://startup.ai"
    assert loaded.collected_pages[0]["is_error"] is False
    assert loaded.startup_profiles[0]["schema_version"] == "startup_profile.v1"
    assert loaded.startup_profiles[0]["company_name"] == "Startup AI"
    assert loaded.field_evidences
    assert loaded.collection_quality_summaries[0]["ready_for_evaluation"] is True

    assert (json_run_dir / "manifest.json").exists()
    assert (json_run_dir / "raw" / "collected_pages.json").exists()
    assert (json_run_dir / "processed" / "startup_profiles.json").exists()
    assert (json_run_dir / "processed" / "field_evidences.json").exists()
    assert (json_run_dir / "processed" / "collection_quality.json").exists()


def test_collect_startup_cli_persists_collection_errors_for_auditing(tmp_path) -> None:
    stdout = StringIO()
    repository = sqlite_repository()

    def fetch(url: str) -> FetchResponse:
        if url == "https://startup.ai":
            return FetchResponse(
                url="https://startup.ai/",
                status_code=200,
                body=(
                    "<html><head><title>Startup AI</title></head><body>"
                    "<a href='/sobre'>Sobre</a>"
                    "Resumo: Plataforma AI-native brasileira. "
                    "Sinais de IA: modelos proprietarios."
                    "</body></html>"
                ),
            )
        raise TimeoutError("timeout collecting linked page")

    exit_code = main(
        [
            "collect-startup",
            "https://startup.ai/",
            "--startup-name",
            "Startup AI",
            "--max-pages",
            "2",
            "--max-depth",
            "1",
            "--no-render-js",
            "--output-dir",
            str(tmp_path / "runs"),
        ],
        stdout=stdout,
        fetcher=fetch,
        robots_fetcher=_allow_robots,
        clock=fixed_clock,
        sql_repository_factory=lambda: repository,
    )

    payload = json.loads(stdout.getvalue())
    loaded = repository.load_run(payload["run_id"])
    error_rows = [row for row in loaded.collected_pages if row["is_error"]]

    assert exit_code == 0
    assert payload["summary"]["collection_errors"] == 1
    assert payload["source_urls"] == ["https://startup.ai", "https://startup.ai/sobre"]
    assert error_rows[0]["url"] == "https://startup.ai/sobre"
    assert error_rows[0]["error_type"] == "TimeoutError"
    assert error_rows[0]["message"] == "timeout collecting linked page"


def test_run_intelligence_cli_writes_operational_payload_for_startup_url(tmp_path) -> None:
    stdout = StringIO()
    output_dir = tmp_path / "runs"
    pages = {
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
                "Clientes: bancos. Founders: Ana Silva. Localizacao: Campinas, SP."
                "</body></html>"
            ),
        )
    }

    exit_code = main(
        [
            "run-intelligence",
            "--startup-url",
            "https://neuralmind.ai/",
            "--startup-name",
            "NeuralMind",
            "--max-pages",
            "1",
            "--max-depth",
            "0",
            "--output-dir",
            str(output_dir),
            "--nvidia-corpus-path",
            "tests/fixtures/nvidia_knowledge_official_fixture.json",
        ],
        stdout=stdout,
        fetcher=_fetcher(pages),
        robots_fetcher=_allow_robots,
        clock=fixed_clock,
    )

    payload = json.loads(stdout.getvalue())
    briefing_path = output_dir / payload["run_id"] / "processed" / "downstream" / "NeuralMind" / "briefing.json"

    assert exit_code == 0
    assert payload["schema_version"] == "operational_entrypoint_result.v1"
    assert payload["run_id"] == "op-20260626T093000Z"
    assert payload["startup_identifier"] == "NeuralMind"
    assert payload["workflow_outcome"] == "briefing_generated"
    assert payload["next_action"] == "prepare_technical_outreach"
    assert payload["briefing_reference"] == {
        "storage": "json",
        "path": str(briefing_path),
        "briefing_type": "executive",
    }
    assert payload["human_review_reasons"] == []
    assert payload["errors"] == []
    assert payload["options"]["persistence_mode"] == "json"
    assert payload["options"]["render_js"] is False
    assert payload["options"]["llm_narrative"] is False
    assert payload["options"]["retrieval_mode"] == "bm25"
    assert payload["artifact_locations"]["json_run_dir"] == str(output_dir / payload["run_id"])
    assert briefing_path.exists()


def test_run_intelligence_cli_accepts_bounded_query_with_injected_search_client(tmp_path) -> None:
    stdout = StringIO()
    output_dir = tmp_path / "runs"
    pages = {
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
                "Clientes: bancos. Founders: Ana Silva. Localizacao: Campinas, SP."
                "</body></html>"
            ),
        )
    }
    search_client = _SearchClient(
        (
            SearchProviderResult(
                title="NeuralMind",
                url="https://neuralmind.ai/",
                snippet="NeuralMind desenvolve IA para documentos.",
                position=1,
            ),
        )
    )

    exit_code = main(
        [
            "run-intelligence",
            "--query",
            "startups AI-native brasileiras em documentos",
            "--limit",
            "1",
            "--max-pages",
            "1",
            "--output-dir",
            str(output_dir),
            "--nvidia-corpus-path",
            "tests/fixtures/nvidia_knowledge_official_fixture.json",
        ],
        stdout=stdout,
        fetcher=_fetcher(pages),
        robots_fetcher=_allow_robots,
        search_client=search_client,
        clock=fixed_clock,
    )

    payload = json.loads(stdout.getvalue())

    assert exit_code == 0
    assert payload["input"]["query"] == "startups AI-native brasileiras em documentos"
    assert payload["startup_identifier"] == "NeuralMind"
    assert payload["workflow_outcome"] == "briefing_generated"
    assert payload["next_action"] == "prepare_technical_outreach"
    assert payload["options"]["limit"] == 1
    assert payload["options"]["search_provider"] is False
    assert search_client.requests
    assert payload["errors"] == []


def test_run_intelligence_cli_represents_errors_and_preserves_partial_artifacts(tmp_path) -> None:
    stdout = StringIO()
    output_dir = tmp_path / "runs"

    exit_code = main(
        [
            "run-intelligence",
            "--query",
            "startups AI-native brasileiras",
            "--limit",
            "1",
            "--output-dir",
            str(output_dir),
            "--nvidia-corpus-path",
            "tests/fixtures/nvidia_knowledge_official_fixture.json",
        ],
        stdout=stdout,
        search_client=_TimeoutSearchClient(),
        clock=fixed_clock,
    )

    payload = json.loads(stdout.getvalue())
    run_dir = output_dir / payload["run_id"]

    assert exit_code == 1
    assert payload["workflow_outcome"] == "failed_with_auditable_error"
    assert payload["next_action"] == "review_workflow_errors"
    assert payload["startup_identifier"] == "unknown"
    assert payload["human_review_reasons"] == ["search_adapter_failed_structured_error"]
    assert payload["errors"][0]["step"] == "execute_search"
    assert payload["errors"][0]["error_type"] == "TimeoutError"
    assert payload["artifact_locations"]["json_run_dir"] == str(run_dir)
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "raw" / "discovery_results.json").exists()
    assert (run_dir / "processed" / "collection_quality.json").exists()


def test_run_intelligence_cli_validates_run_limits_before_collection(tmp_path) -> None:
    stdout = StringIO()

    exit_code = main(
        [
            "run-intelligence",
            "--startup-url",
            "https://neuralmind.ai/",
            "--max-pages",
            "0",
            "--output-dir",
            str(tmp_path / "runs"),
            "--nvidia-corpus-path",
            "tests/fixtures/nvidia_knowledge_official_fixture.json",
        ],
        stdout=stdout,
        fetcher=_ExplodingFetcher(),
        clock=fixed_clock,
    )

    payload = json.loads(stdout.getvalue())

    assert exit_code == 1
    assert payload["workflow_outcome"] == "failed_with_auditable_error"
    assert payload["errors"][0]["error_type"] == "ValueError"
    assert payload["errors"][0]["message"] == "max_pages_must_be_greater_than_zero"
    assert payload["artifact_locations"] == {}


def _fetcher(pages: dict[str, FetchResponse]):
    def fetch(url: str) -> FetchResponse:
        return pages[url]

    return fetch


def _allow_robots(url: str) -> str:
    return "User-agent: *\nAllow: /\n"


class _SearchClient:
    provider_name = "fake"

    def __init__(self, results: tuple[SearchProviderResult, ...]) -> None:
        self.results = results
        self.requests: tuple[tuple[str, int], ...] = ()

    def search(self, query: str, *, limit: int) -> tuple[SearchProviderResult, ...]:
        self.requests = (*self.requests, (query, limit))
        return self.results[:limit]


class _TimeoutSearchClient:
    provider_name = "timeout"

    def search(self, query: str, *, limit: int) -> tuple[SearchProviderResult, ...]:
        raise TimeoutError("search provider timeout")


class _ExplodingFetcher:
    def __call__(self, url: str) -> FetchResponse:
        raise AssertionError("validation should fail before collection")
