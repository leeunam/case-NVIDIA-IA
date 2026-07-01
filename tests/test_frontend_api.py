from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

import pytest

from nvidia_startup_intel.frontend_api import (
    API_SCHEMA_VERSION,
    FrontendApiService,
    FrontendRunRequest,
    RUN_CREATE_SCHEMA_VERSION,
    SMOKE_MATRIX_SCHEMA_VERSION,
    build_run_record,
    create_app,
)
from nvidia_startup_intel.page_collection import FetchResponse
from nvidia_startup_intel.search_execution import SearchProviderResult


def test_frontend_api_starts_local_intelligence_run_from_startup_url(tmp_path: Path) -> None:
    output_dir = tmp_path / "runs"
    service = FrontendApiService(
        fetcher=_fetcher(
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
                        "Clientes: bancos. Founders: Ana Silva. Localizacao: Campinas, SP."
                        "</body></html>"
                    ),
                )
            }
        ),
        robots_fetcher=_allow_robots,
        clock=_fixed_clock,
    )

    record = service.start_run(
        {
            "schema_version": RUN_CREATE_SCHEMA_VERSION,
            "startup_url": "https://neuralmind.ai/",
            "startup_name": "NeuralMind",
            "max_pages": 1,
            "max_depth": 0,
            "output_dir": str(output_dir),
            "nvidia_corpus_path": "tests/fixtures/nvidia_knowledge_official_fixture.json",
        }
    )

    assert record["schema_version"] == API_SCHEMA_VERSION
    assert record["run_id"] == "op-20260626T093000Z"
    assert record["status"] == "completed"
    assert record["workflow_outcome"] == "briefing_generated"
    assert record["startup_identifier"] == "NeuralMind"
    assert record["next_action"] == "prepare_technical_outreach"
    assert record["briefing_reference"]["briefing_type"] == "executive"
    assert record["human_review_reasons"] == []
    assert record["errors"] == []
    assert record["artifact_references"]["artifact_locations"]["json_run_dir"] == str(
        output_dir / record["run_id"]
    )
    assert record["final_payload"]["schema_version"] == "operational_entrypoint_result.v1"
    json.dumps(record)

    loaded = service.get_run("op-20260626T093000Z")
    assert loaded == record


def test_frontend_api_accepts_bounded_query_with_injected_search_client(tmp_path: Path) -> None:
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
    service = FrontendApiService(
        fetcher=_fetcher(
            {
                "https://neuralmind.ai": FetchResponse(
                    url="https://neuralmind.ai/",
                    status_code=200,
                    body=(
                        "<html><head><title>NeuralMind</title></head><body>"
                        "Resumo: Plataforma AI-native para documentos. Setor: dados. "
                        "Produto: Copiloto documental com IA generativa. "
                        "Sinais de IA: modelos proprietarios, fine-tuning, inferencia em producao. "
                        "Tecnologias: MLOps, dados proprietarios e model serving. "
                        "Clientes: bancos. Founders: Ana Silva. Localizacao: Campinas, SP."
                        "</body></html>"
                    ),
                )
            }
        ),
        robots_fetcher=_allow_robots,
        search_client=search_client,
        clock=_query_clock,
    )

    record = service.start_run(
        {
            "query": "startups AI-native brasileiras em documentos",
            "limit": 1,
            "max_pages": 1,
            "output_dir": str(tmp_path / "query-runs"),
            "nvidia_corpus_path": "tests/fixtures/nvidia_knowledge_official_fixture.json",
        }
    )

    assert record["status"] == "completed"
    assert record["workflow_outcome"] == "briefing_generated"
    assert record["input"]["query"] == "startups AI-native brasileiras em documentos"
    assert record["options"]["search_provider"] is False
    assert search_client.requests
    assert json.loads(json.dumps(record))["run_id"] == "op-20260626T094500Z"


def test_frontend_api_projects_auditable_errors_as_failed_status() -> None:
    request = FrontendRunRequest.from_mapping({"startup_url": "https://startup.ai/"})
    record = build_run_record(
        {
            "schema_version": "operational_entrypoint_result.v1",
            "run_id": "op-error",
            "created_at": "2026-06-26T09:30:00+00:00",
            "input": {
                "startup_url": "https://startup.ai/",
                "query": None,
                "startup_name": "unknown",
            },
            "startup_identifier": "unknown",
            "workflow_outcome": "failed_with_auditable_error",
            "next_action": "review_workflow_errors",
            "briefing_reference": None,
            "human_review_reasons": ["search_adapter_failed_structured_error"],
            "artifact_locations": {},
            "persistence_references": [],
            "errors": [
                {
                    "step": "execute_search",
                    "error_type": "TimeoutError",
                    "message": "search provider timeout",
                    "audit_reason": "search_adapter_failed_structured_error",
                }
            ],
            "options": {"persistence_mode": "json"},
        },
        request=request,
    )

    assert record["schema_version"] == API_SCHEMA_VERSION
    assert record["status"] == "failed"
    assert record["next_action"] == "review_workflow_errors"
    assert record["human_review_reasons"] == ["search_adapter_failed_structured_error"]
    assert record["errors"][0]["error_type"] == "TimeoutError"
    assert record["artifact_references"] == {
        "artifact_locations": {},
        "persistence_references": [],
    }


def test_frontend_api_validates_run_request_input() -> None:
    with pytest.raises(ValueError, match="provide_exactly_one_of_startup_url_or_query"):
        FrontendRunRequest.from_mapping(
            {
                "startup_url": "https://startup.ai/",
                "query": "startups AI-native",
            }
        )

    with pytest.raises(ValueError, match="limit_must_be_integer"):
        FrontendRunRequest.from_mapping(
            {
                "query": "startups AI-native",
                "limit": "many",
            }
        )


def test_frontend_api_exposes_read_only_production_smoke_matrix() -> None:
    service = FrontendApiService()

    payload = service.production_smoke_matrix(
        env={},
        only=("postgres_persistence",),
    )

    assert payload["schema_version"] == SMOKE_MATRIX_SCHEMA_VERSION
    assert payload["read_only"] is True
    assert payload["matrix"]["schema_version"] == "production_smoke_matrix.v1"
    assert payload["matrix"]["overall_status"] == "skipped"
    assert [step["integration_id"] for step in payload["matrix"]["steps"]] == ["postgres_persistence"]
    assert payload["matrix"]["steps"][0]["status"] == "skipped"
    json.dumps(payload)


def test_frontend_api_allows_local_frontend_cors_preflight() -> None:
    try:
        from fastapi.testclient import TestClient
    except Exception as exc:  # noqa: BLE001 - optional API test dependency may be incomplete.
        pytest.skip(f"fastapi test client unavailable: {exc}")
    client = TestClient(create_app(FrontendApiService()))

    response = client.options(
        "/api/runs",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    assert "POST" in response.headers["access-control-allow-methods"]


def test_frontend_api_reports_missing_run() -> None:
    service = FrontendApiService()

    with pytest.raises(KeyError):
        service.get_run("missing-run")


def _fixed_clock() -> datetime:
    return datetime(2026, 6, 26, 9, 30, tzinfo=UTC)


def _query_clock() -> datetime:
    return datetime(2026, 6, 26, 9, 45, tzinfo=UTC)


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
