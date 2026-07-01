"""Optional backend-for-frontend API for operational intelligence runs."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
import sys
from typing import Any

from nvidia_startup_intel.operational_entrypoint import (
    DEFAULT_NVIDIA_CORPUS_PATH,
    OperationalEntrypointOptions,
    run_operational_intelligence,
)
from nvidia_startup_intel.page_collection import Fetcher, PlaywrightRenderer
from nvidia_startup_intel.production_smoke_matrix import run_production_smoke_matrix
from nvidia_startup_intel.robots import RobotsFetcher
from nvidia_startup_intel.search_execution import SearchClient
from nvidia_startup_intel.search_params import UNKNOWN
from nvidia_startup_intel.sql_repository import SqlPipelineRepository


API_SCHEMA_VERSION = "frontend_api_run.v1"
RUN_CREATE_SCHEMA_VERSION = "frontend_api_run_create.v1"
SMOKE_MATRIX_SCHEMA_VERSION = "frontend_api_production_smoke_matrix.v1"
Clock = Callable[[], datetime]
OperationalRunner = Callable[..., dict[str, object]]
SqlRepositoryFactory = Callable[[], SqlPipelineRepository]


@dataclass(frozen=True)
class FrontendRunRequest:
    """Transport-owned request for starting one operational intelligence run."""

    startup_url: str | None = None
    query: str | None = None
    startup_name: str = UNKNOWN
    limit: int = 1
    max_pages: int = 1
    max_depth: int = 0
    timeout_seconds: int = 15
    output_dir: str | Path = "runs"
    persistence_mode: str = "json"
    nvidia_corpus_path: str | Path = DEFAULT_NVIDIA_CORPUS_PATH
    render_js: bool = False
    robots_policy: str = "conservative"
    retrieval_mode: str = "bm25"
    orchestration: str = "local"
    enable_search_provider: bool = False
    enable_reranking: bool = False
    reranker_model: str = ""
    llm_narrative: bool = False

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "FrontendRunRequest":
        request = cls(
            startup_url=_optional_text(payload, "startup_url"),
            query=_optional_text(payload, "query"),
            startup_name=_text(payload, "startup_name", UNKNOWN),
            limit=_integer(payload, "limit", 1),
            max_pages=_integer(payload, "max_pages", 1),
            max_depth=_integer(payload, "max_depth", 0),
            timeout_seconds=_integer(payload, "timeout_seconds", 15),
            output_dir=_text(payload, "output_dir", "runs"),
            persistence_mode=_choice(
                payload,
                "persistence_mode",
                "json",
                ("json", "postgres", "json-postgres", "none"),
            ),
            nvidia_corpus_path=_text(payload, "nvidia_corpus_path", DEFAULT_NVIDIA_CORPUS_PATH),
            render_js=_boolean(payload, "render_js", False),
            robots_policy=_choice(
                payload,
                "robots_policy",
                "conservative",
                ("conservative", "permissive-on-error", "off"),
            ),
            retrieval_mode=_choice(payload, "retrieval_mode", "bm25", ("bm25", "pgvector")),
            orchestration=_choice(payload, "orchestration", "local", ("local", "langgraph")),
            enable_search_provider=_boolean(payload, "enable_search_provider", False),
            enable_reranking=_boolean(payload, "enable_reranking", False),
            reranker_model=_text(payload, "reranker_model", ""),
            llm_narrative=_boolean(payload, "llm_narrative", False),
        )
        if bool(request.startup_url) == bool(request.query):
            raise ValueError("provide_exactly_one_of_startup_url_or_query")
        return request

    def to_operational_options(self) -> OperationalEntrypointOptions:
        return OperationalEntrypointOptions(
            startup_url=self.startup_url,
            query=self.query,
            startup_name=self.startup_name,
            limit=self.limit,
            max_pages=self.max_pages,
            max_depth=self.max_depth,
            timeout_seconds=self.timeout_seconds,
            output_dir=self.output_dir,
            persistence_mode=self.persistence_mode,
            nvidia_corpus_path=self.nvidia_corpus_path,
            render_js=self.render_js,
            robots_policy=self.robots_policy,
            retrieval_mode=self.retrieval_mode,
            orchestration=self.orchestration,
            enable_search_provider=self.enable_search_provider,
            enable_reranking=self.enable_reranking,
            reranker_model=self.reranker_model,
            llm_narrative=self.llm_narrative,
        )


class InMemoryFrontendRunStore:
    """Small in-process run index for the optional API process."""

    def __init__(self) -> None:
        self._records: dict[str, dict[str, object]] = {}

    def save(self, record: Mapping[str, object]) -> dict[str, object]:
        run_id = str(record.get("run_id", ""))
        if not run_id:
            raise ValueError("run_id is required")
        stored = _plain_data(record)
        assert isinstance(stored, dict)
        self._records[run_id] = stored
        return stored

    def get(self, run_id: str) -> dict[str, object] | None:
        record = self._records.get(run_id)
        if record is None:
            return None
        return dict(record)


class FrontendApiService:
    """Framework-neutral API behavior used by tests and the optional web adapter."""

    def __init__(
        self,
        *,
        store: InMemoryFrontendRunStore | None = None,
        operational_runner: OperationalRunner = run_operational_intelligence,
        fetcher: Fetcher | None = None,
        playwright_renderer: PlaywrightRenderer | None = None,
        robots_fetcher: RobotsFetcher | None = None,
        search_client: SearchClient | None = None,
        sql_repository_factory: SqlRepositoryFactory | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.store = store or InMemoryFrontendRunStore()
        self.operational_runner = operational_runner
        self.fetcher = fetcher
        self.playwright_renderer = playwright_renderer
        self.robots_fetcher = robots_fetcher
        self.search_client = search_client
        self.sql_repository_factory = sql_repository_factory
        self.clock = clock

    def start_run(self, payload: Mapping[str, object]) -> dict[str, object]:
        request = FrontendRunRequest.from_mapping(payload)
        final_payload = self.operational_runner(
            request.to_operational_options(),
            fetcher=self.fetcher,
            playwright_renderer=self.playwright_renderer,
            robots_fetcher=self.robots_fetcher,
            search_client=self.search_client,
            sql_repository_factory=self.sql_repository_factory,
            clock=self.clock,
        )
        record = build_run_record(final_payload, request=request)
        return self.store.save(record)

    def get_run(self, run_id: str) -> dict[str, object]:
        record = self.store.get(run_id)
        if record is None:
            raise KeyError(run_id)
        return record

    def production_smoke_matrix(
        self,
        *,
        env: Mapping[str, str] | None = None,
        only: tuple[str, ...] = (),
    ) -> dict[str, object]:
        matrix = run_production_smoke_matrix(env=env, only=only)
        return {
            "schema_version": SMOKE_MATRIX_SCHEMA_VERSION,
            "read_only": True,
            "matrix": matrix.to_dict(),
        }


def build_run_record(
    final_payload: Mapping[str, object],
    *,
    request: FrontendRunRequest,
) -> dict[str, object]:
    """Project the operational payload into a stable frontend API run record."""

    payload = _plain_data(final_payload)
    assert isinstance(payload, dict)
    outcome = str(payload.get("workflow_outcome", "unknown"))
    status = "failed" if outcome == "failed_with_auditable_error" else "completed"
    return {
        "schema_version": API_SCHEMA_VERSION,
        "run_id": str(payload.get("run_id", UNKNOWN)),
        "status": status,
        "workflow_outcome": outcome,
        "created_at": str(payload.get("created_at", "")),
        "input": payload.get("input", _request_input(request)),
        "startup_identifier": str(payload.get("startup_identifier", UNKNOWN)),
        "next_action": str(payload.get("next_action", "review_workflow_output")),
        "briefing_reference": payload.get("briefing_reference"),
        "human_review_reasons": payload.get("human_review_reasons", []),
        "artifact_references": {
            "artifact_locations": payload.get("artifact_locations", {}),
            "persistence_references": payload.get("persistence_references", []),
        },
        "errors": payload.get("errors", []),
        "options": payload.get("options", _plain_data(request)),
        "final_payload": payload,
    }


def create_app(service: FrontendApiService | None = None) -> Any:
    """Create the optional FastAPI app, importing framework dependencies lazily."""

    try:
        from fastapi import FastAPI, HTTPException, Query, status
    except ModuleNotFoundError as exc:
        raise RuntimeError('Install the optional API extra with: python -m pip install -e ".[api]"') from exc

    active_service = service or FrontendApiService()
    app = FastAPI(
        title="NVIDIA Startup Intel Frontend API",
        version="0.1.0",
        description="Optional transport layer over project-owned operational intelligence contracts.",
    )

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"schema_version": "frontend_api_health.v1", "status": "ok"}

    @app.post("/api/runs", status_code=status.HTTP_201_CREATED)
    def start_run(payload: dict[str, object]) -> dict[str, object]:
        try:
            return active_service.start_run(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, object]:
        try:
            return active_service.get_run(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="run_not_found") from exc

    @app.get("/api/production-smoke-matrix")
    def production_smoke_matrix(only: str | None = Query(default=None)) -> dict[str, object]:
        return active_service.production_smoke_matrix(only=_selected_integrations(only))

    return app


def main(argv: tuple[str, ...] | None = None) -> int:
    """Run the optional API server with uvicorn."""

    parser = argparse.ArgumentParser(description="Run the optional frontend API server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        import uvicorn
    except ModuleNotFoundError as exc:
        raise RuntimeError('Install the optional API extra with: python -m pip install -e ".[api]"') from exc

    uvicorn.run(
        "nvidia_startup_intel.frontend_api:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


def _request_input(request: FrontendRunRequest) -> dict[str, object]:
    return {
        "startup_url": request.startup_url,
        "query": request.query,
        "startup_name": request.startup_name,
    }


def _optional_text(payload: Mapping[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _text(payload: Mapping[str, object], key: str, default: str | Path) -> str:
    value = payload.get(key, default)
    if value is None:
        return str(default)
    return str(value).strip() or str(default)


def _integer(payload: Mapping[str, object], key: str, default: int) -> int:
    value = payload.get(key, default)
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key}_must_be_integer") from exc


def _boolean(payload: Mapping[str, object], key: str, default: bool) -> bool:
    value = payload.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    raise ValueError(f"{key}_must_be_boolean")


def _choice(
    payload: Mapping[str, object],
    key: str,
    default: str,
    allowed: tuple[str, ...],
) -> str:
    value = _text(payload, key, default)
    if value not in allowed:
        raise ValueError(f"{key}_must_be_one_of:{','.join(allowed)}")
    return value


def _selected_integrations(raw_value: str | None) -> tuple[str, ...]:
    if raw_value is None:
        return ()
    return tuple(dict.fromkeys(item.strip() for item in raw_value.split(",") if item.strip()))


def _plain_data(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _plain_data(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_data(item) for item in value]
    return value


def _utc_now() -> datetime:
    return datetime.now(UTC)


if __name__ == "__main__":
    raise SystemExit(main(tuple(sys.argv[1:])))
