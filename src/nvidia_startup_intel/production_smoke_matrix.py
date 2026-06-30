"""Opt-in production smoke matrix for real integration validation."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import sys
from typing import TextIO
from urllib.parse import urlsplit


SCHEMA_VERSION = "production_smoke_matrix.v1"
StepRunner = Callable[["ProductionSmokeMatrixContext"], object]


@dataclass(frozen=True)
class ProductionSmokeIntegration:
    integration_id: str
    title: str
    bottleneck: str
    env_flag: str
    command: str
    prerequisites: tuple[str, ...]
    required_env_vars: tuple[str, ...] = ()
    expected_artifacts: tuple[str, ...] = ()
    cleanup: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProductionSmokeMatrixContext:
    integration_id: str
    env: Mapping[str, str]
    definition: ProductionSmokeIntegration


@dataclass(frozen=True)
class ProductionSmokeStepResult:
    integration_id: str
    title: str
    status: str
    bottleneck: str
    message: str
    command: str
    prerequisites: tuple[str, ...]
    required_env_vars: tuple[str, ...]
    expected_artifacts: tuple[str, ...]
    cleanup: tuple[str, ...]
    payload: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ProductionSmokeMatrixResult:
    schema_version: str
    overall_status: str
    steps: tuple[ProductionSmokeStepResult, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "overall_status": self.overall_status,
            "steps": [step.to_dict() for step in self.steps],
        }


INTEGRATIONS: tuple[ProductionSmokeIntegration, ...] = (
    ProductionSmokeIntegration(
        integration_id="playwright_collection",
        title="Playwright real collection",
        bottleneck="collection",
        env_flag="NVIDIA_STARTUP_INTEL_RUN_PLAYWRIGHT_COLLECTION_SMOKE",
        command=(
            "NVIDIA_STARTUP_INTEL_RUN_PLAYWRIGHT_COLLECTION_SMOKE=1 "
            "python -m pytest -q tests/integration/test_playwright_collection_integration_smoke.py "
            "-m playwright_collection_integration"
        ),
        prerequisites=("python -m playwright install chromium",),
        expected_artifacts=("playwright_collection_smoke.v1 payload",),
    ),
    ProductionSmokeIntegration(
        integration_id="postgres_persistence",
        title="Postgres persistence",
        bottleneck="postgres",
        env_flag="NVIDIA_STARTUP_INTEL_RUN_POSTGRES_PERSISTENCE_SMOKE",
        command=(
            "NVIDIA_STARTUP_INTEL_RUN_POSTGRES_PERSISTENCE_SMOKE=1 "
            "PYTHONPATH=src python -m nvidia_startup_intel.postgres_persistence_smoke"
        ),
        prerequisites=("docker compose up -d postgres", "python -m pip install -e '.[postgres]'"),
        expected_artifacts=("postgres_persistence_smoke.v1 payload", "operational run rows"),
        cleanup=("docker compose down",),
    ),
    ProductionSmokeIntegration(
        integration_id="pgvector_retrieval",
        title="pgvector retrieval",
        bottleneck="pgvector",
        env_flag="NVIDIA_STARTUP_INTEL_RUN_PGVECTOR_SMOKE",
        command=(
            "NVIDIA_STARTUP_INTEL_RUN_PGVECTOR_SMOKE=1 "
            "python -m pytest -q tests/integration/test_pgvector_integration_smoke.py "
            "-m pgvector_integration"
        ),
        prerequisites=("docker compose up -d postgres", "python -m pip install -e '.[pgvector]'"),
        expected_artifacts=("persisted NVIDIA Knowledge chunks", "persisted chunk embeddings"),
        cleanup=("docker compose down",),
    ),
    ProductionSmokeIntegration(
        integration_id="real_embeddings",
        title="Real embedding model",
        bottleneck="embedding",
        env_flag="NVIDIA_STARTUP_INTEL_RUN_REAL_EMBEDDING_SMOKE",
        command=(
            "NVIDIA_STARTUP_INTEL_RUN_REAL_EMBEDDING_SMOKE=1 "
            "NVIDIA_STARTUP_INTEL_EMBEDDING_PROVIDER=sentence-transformers "
            "PYTHONPATH=src python -m nvidia_startup_intel.pgvector_smoke"
        ),
        prerequisites=("python -m pip install -e '.[embeddings,pgvector]'",),
        required_env_vars=(
            "NVIDIA_STARTUP_INTEL_EMBEDDING_PROVIDER",
            "NVIDIA_STARTUP_INTEL_EMBEDDING_MODEL",
            "NVIDIA_STARTUP_INTEL_EMBEDDING_MODEL_VERSION",
        ),
        expected_artifacts=("embedding metadata with provider/model/version",),
    ),
    ProductionSmokeIntegration(
        integration_id="hybrid_retrieval",
        title="Hybrid BM25 plus pgvector retrieval",
        bottleneck="retrieval",
        env_flag="NVIDIA_STARTUP_INTEL_RUN_HYBRID_RETRIEVAL_SMOKE",
        command=(
            "NVIDIA_STARTUP_INTEL_RUN_HYBRID_RETRIEVAL_SMOKE=1 "
            "PYTHONPATH=src python -m nvidia_startup_intel.production_smoke_matrix "
            "--only hybrid_retrieval"
        ),
        prerequisites=("pgvector corpus smoke has persisted the fixture corpus",),
        expected_artifacts=("nvidia_knowledge.v1 retrieval with hybrid ranking",),
    ),
    ProductionSmokeIntegration(
        integration_id="reranking",
        title="Real reranking",
        bottleneck="reranking",
        env_flag="NVIDIA_STARTUP_INTEL_RUN_REAL_RERANKING_SMOKE",
        command=(
            "NVIDIA_STARTUP_INTEL_RUN_REAL_RERANKING_SMOKE=1 "
            "NVIDIA_STARTUP_INTEL_RERANKER_MODEL=<model> "
            "PYTHONPATH=src python -m nvidia_startup_intel.production_smoke_matrix "
            "--only reranking"
        ),
        prerequisites=("python -m pip install -e '.[reranking]'",),
        required_env_vars=("NVIDIA_STARTUP_INTEL_RERANKER_MODEL",),
        expected_artifacts=("nvidia_rerank.v1 payload",),
    ),
    ProductionSmokeIntegration(
        integration_id="langgraph_checkpoint",
        title="LangGraph Postgres checkpointing",
        bottleneck="langgraph",
        env_flag="NVIDIA_STARTUP_INTEL_RUN_LANGGRAPH_CHECKPOINT_SMOKE",
        command=(
            "NVIDIA_STARTUP_INTEL_RUN_LANGGRAPH_CHECKPOINT_SMOKE=1 "
            "python -m pytest -q "
            "tests/integration/test_intelligence_workflow_langgraph_checkpoint_smoke.py "
            "-m langgraph_checkpoint_integration"
        ),
        prerequisites=("docker compose up -d postgres", "python -m pip install -e '.[workflow]'"),
        expected_artifacts=("LangGraph checkpoint rows", "resumed workflow state"),
        cleanup=("docker compose down",),
    ),
    ProductionSmokeIntegration(
        integration_id="groq_litellm_narrative",
        title="Groq/LiteLLM briefing narrative",
        bottleneck="llm",
        env_flag="NVIDIA_STARTUP_INTEL_RUN_LLM_ADAPTER_SMOKE",
        command=(
            "NVIDIA_STARTUP_INTEL_RUN_LLM_ADAPTER_SMOKE=1 "
            "NVIDIA_STARTUP_INTEL_LLM_PROVIDER=litellm "
            "python -m pytest -q tests/integration/test_llm_adapter_integration_smoke.py "
            "-m llm_adapter_integration"
        ),
        prerequisites=("python -m pip install -e '.[llm]'",),
        required_env_vars=(
            "NVIDIA_STARTUP_INTEL_LLM_PROVIDER",
            "NVIDIA_STARTUP_INTEL_LLM_MODEL",
            "NVIDIA_STARTUP_INTEL_LLM_API_KEY_ENV",
        ),
        expected_artifacts=("llm_generation_response.v1 payload", "briefing_narrative.v1 artifact"),
    ),
    ProductionSmokeIntegration(
        integration_id="full_operational_smoke",
        title="Full bounded operational smoke",
        bottleneck="briefing_quality",
        env_flag="NVIDIA_STARTUP_INTEL_RUN_FULL_PRODUCTION_SMOKE",
        command=(
            "NVIDIA_STARTUP_INTEL_RUN_FULL_PRODUCTION_SMOKE=1 "
            "PYTHONPATH=src python -m nvidia_startup_intel.production_smoke_matrix --only "
            "full_operational_smoke"
        ),
        prerequisites=(
            "All required optional services for selected modes are configured",
            "Use a public startup URL or bounded query only",
        ),
        expected_artifacts=("persisted run artifacts", "final briefing or Human Review Briefing"),
        cleanup=("rm -rf runs/production-smoke/<run_id>",),
    ),
)


def run_production_smoke_matrix(
    *,
    env: Mapping[str, str] | None = None,
    step_runners: Mapping[str, StepRunner] | None = None,
    only: tuple[str, ...] = (),
) -> ProductionSmokeMatrixResult:
    """Run enabled opt-in production smokes and report every integration status."""

    source = os.environ if env is None else env
    selected_ids = set(only)
    runners = step_runners or {}
    credential_values = _credential_values(source)
    steps: list[ProductionSmokeStepResult] = []
    for definition in INTEGRATIONS:
        if selected_ids and definition.integration_id not in selected_ids:
            continue
        if source.get(definition.env_flag) != "1":
            steps.append(_skipped_step(definition, f"set {definition.env_flag}=1 to enable"))
            continue

        missing_env = tuple(name for name in definition.required_env_vars if not source.get(name, "").strip())
        if missing_env:
            steps.append(_skipped_step(definition, "missing env vars: " + ", ".join(missing_env)))
            continue

        runner = runners.get(definition.integration_id, _default_runner(definition.integration_id))
        try:
            raw_payload = runner(
                ProductionSmokeMatrixContext(
                    integration_id=definition.integration_id,
                    env=source,
                    definition=definition,
                )
            )
        except Exception as exc:  # noqa: BLE001 - this is the smoke error boundary.
            steps.append(
                _step(
                    definition,
                    status="failed",
                    message=_sanitize_text(f"{type(exc).__name__}: {exc}", credential_values),
                    payload={},
                )
            )
            continue

        payload, leaked_credential = _sanitize_payload(_payload(raw_payload), credential_values)
        leaked_artifacts = _artifact_credential_leaks(payload, credential_values)
        if leaked_credential or leaked_artifacts:
            if leaked_artifacts:
                payload["credential_scan"] = {"leaked_artifacts": list(leaked_artifacts)}
            steps.append(
                _step(
                    definition,
                    status="failed",
                    bottleneck="credential_hygiene",
                    message="credential leak detected in smoke payload or generated artifact",
                    payload=payload,
                )
            )
            continue

        steps.append(
            _step(
                definition,
                status="passed",
                message="smoke passed",
                payload=payload,
            )
        )

    return ProductionSmokeMatrixResult(
        schema_version=SCHEMA_VERSION,
        overall_status=_overall_status(tuple(steps)),
        steps=tuple(steps),
    )


def main(argv: tuple[str, ...] | None = None, *, stdout: TextIO | None = None) -> int:
    """Run the opt-in production smoke matrix as a module."""

    parser = argparse.ArgumentParser(description="Run opt-in production smoke matrix.")
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="Integration id to include. Can be passed more than once or as comma-separated ids.",
    )
    parser.add_argument("--output", help="Write JSON payload to this path instead of stdout.")
    args = parser.parse_args(list(argv) if argv is not None else None)
    selected = _selected_integrations(tuple(args.only))
    result = run_production_smoke_matrix(only=selected)
    payload = result.to_dict()
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(f"{encoded}\n", encoding="utf-8")
    else:
        (stdout or sys.stdout).write(f"{encoded}\n")
    return 1 if result.overall_status == "failed" else 0


def _skipped_step(definition: ProductionSmokeIntegration, message: str) -> ProductionSmokeStepResult:
    return _step(definition, status="skipped", message=message, payload={})


def _step(
    definition: ProductionSmokeIntegration,
    *,
    status: str,
    message: str,
    payload: dict[str, object],
    bottleneck: str | None = None,
) -> ProductionSmokeStepResult:
    return ProductionSmokeStepResult(
        integration_id=definition.integration_id,
        title=definition.title,
        status=status,
        bottleneck=bottleneck or definition.bottleneck,
        message=message,
        command=definition.command,
        prerequisites=definition.prerequisites,
        required_env_vars=definition.required_env_vars,
        expected_artifacts=definition.expected_artifacts,
        cleanup=definition.cleanup,
        payload=payload,
    )


def _payload(value: object) -> dict[str, object]:
    if value is None:
        return {}
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        converted = to_dict()
        return converted if isinstance(converted, dict) else {"value": converted}
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items()}
    return {"value": value}


def _overall_status(steps: tuple[ProductionSmokeStepResult, ...]) -> str:
    if any(step.status == "failed" for step in steps):
        return "failed"
    if any(step.status == "passed" for step in steps):
        return "passed"
    return "skipped"


def _credential_values(env: Mapping[str, str]) -> tuple[str, ...]:
    sensitive_markers = ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "DATABASE_URL")
    values: list[str] = []
    for name, value in env.items():
        if any(marker in name.upper() for marker in sensitive_markers):
            _append_secret_values(values, value)

    api_key_env = env.get("NVIDIA_STARTUP_INTEL_LLM_API_KEY_ENV", "").strip()
    if api_key_env:
        _append_secret_values(values, env.get(api_key_env, ""))

    return tuple(dict.fromkeys(values))


def _append_secret_values(values: list[str], raw_value: str) -> None:
    value = raw_value.strip()
    if len(value) < 4:
        return
    values.append(value)
    password = _password_from_url(value)
    if password:
        values.append(password)


def _password_from_url(value: str) -> str:
    try:
        return urlsplit(value).password or ""
    except ValueError:
        return ""


def _sanitize_payload(value: object, secrets: tuple[str, ...]) -> tuple[dict[str, object], bool]:
    sanitized, changed = _sanitize_value(value, secrets)
    if isinstance(sanitized, dict):
        return sanitized, changed
    return {"value": sanitized}, changed


def _sanitize_value(value: object, secrets: tuple[str, ...]) -> tuple[object, bool]:
    if isinstance(value, str):
        sanitized = _sanitize_text(value, secrets)
        return sanitized, sanitized != value
    if isinstance(value, Mapping):
        changed = False
        sanitized_items: dict[str, object] = {}
        for key, item in value.items():
            sanitized_item, item_changed = _sanitize_value(item, secrets)
            sanitized_items[str(key)] = sanitized_item
            changed = changed or item_changed
        return sanitized_items, changed
    if isinstance(value, (list, tuple)):
        changed = False
        sanitized_items: list[object] = []
        for item in value:
            sanitized_item, item_changed = _sanitize_value(item, secrets)
            sanitized_items.append(sanitized_item)
            changed = changed or item_changed
        return sanitized_items, changed
    return value, False


def _sanitize_text(value: str, secrets: tuple[str, ...]) -> str:
    sanitized = value
    for secret in secrets:
        sanitized = sanitized.replace(secret, "[REDACTED]")
    return sanitized


def _artifact_credential_leaks(
    payload: Mapping[str, object],
    secrets: tuple[str, ...],
) -> tuple[str, ...]:
    if not secrets:
        return ()
    leaked_paths: list[str] = []
    for path in (*_artifact_paths(payload), Path("tests/fixtures")):
        if not path.exists():
            continue
        for file_path in _candidate_artifact_files(path):
            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            except OSError:
                continue
            if any(secret in content for secret in secrets):
                leaked_paths.append(str(file_path))
    return tuple(dict.fromkeys(leaked_paths))


def _artifact_paths(payload: Mapping[str, object]) -> tuple[Path, ...]:
    paths: list[Path] = []

    def visit(value: object, *, key: str = "") -> None:
        if isinstance(value, Mapping):
            for child_key, child_value in value.items():
                visit(child_value, key=str(child_key))
            return
        if isinstance(value, list):
            for item in value:
                visit(item, key=key)
            return
        if not isinstance(value, str) or value in {"", "unknown"}:
            return
        normalized_key = key.lower()
        if normalized_key.endswith("_dir") or normalized_key in {"manifest", "path"}:
            paths.append(Path(value))

    visit(payload)
    return tuple(dict.fromkeys(paths))


def _candidate_artifact_files(path: Path) -> tuple[Path, ...]:
    if path.is_file():
        return (path,)
    if not path.is_dir():
        return ()
    suffixes = {".json", ".jsonl", ".log", ".md", ".txt"}
    return tuple(file_path for file_path in path.rglob("*") if file_path.is_file() and file_path.suffix in suffixes)


def _selected_integrations(raw_values: tuple[str, ...]) -> tuple[str, ...]:
    selected: list[str] = []
    for raw_value in raw_values:
        selected.extend(item.strip() for item in raw_value.split(",") if item.strip())
    return tuple(dict.fromkeys(selected))


def _default_runner(integration_id: str) -> StepRunner:
    def missing_runner(_: ProductionSmokeMatrixContext) -> object:
        raise RuntimeError(f"no default runner registered for {integration_id}")

    return {
        "playwright_collection": _run_playwright_collection,
        "postgres_persistence": _run_postgres_persistence,
        "pgvector_retrieval": _run_pgvector,
        "real_embeddings": _run_pgvector,
        "hybrid_retrieval": _run_hybrid_retrieval,
        "reranking": _run_reranking,
        "langgraph_checkpoint": _run_langgraph_checkpoint,
        "groq_litellm_narrative": _run_litellm,
        "full_operational_smoke": _run_full_operational_smoke,
    }.get(integration_id, missing_runner)


def _run_playwright_collection(context: ProductionSmokeMatrixContext) -> object:
    del context
    from nvidia_startup_intel.playwright_collection_smoke import run_playwright_collection_smoke

    return run_playwright_collection_smoke()


def _run_postgres_persistence(context: ProductionSmokeMatrixContext) -> object:
    del context
    from nvidia_startup_intel.postgres_persistence_smoke import run_postgres_persistence_smoke

    return run_postgres_persistence_smoke()


def _run_pgvector(context: ProductionSmokeMatrixContext) -> object:
    from nvidia_startup_intel.pgvector_smoke import run_pgvector_smoke

    return run_pgvector_smoke(
        database_url=_database_url(context.env),
        embedding_env=context.env,
    )


def _run_litellm(context: ProductionSmokeMatrixContext) -> object:
    from nvidia_startup_intel.llm_adapter_smoke import run_litellm_adapter_smoke

    adapter_result = run_litellm_adapter_smoke(env=context.env)
    operational_payload = _run_llm_narrative_operational_fixture(context)
    return {
        "adapter": adapter_result.to_dict(),
        "operational": operational_payload,
    }


def _run_hybrid_retrieval(context: ProductionSmokeMatrixContext) -> object:
    from nvidia_startup_intel.ai_native_assessment import TechnicalGap
    from nvidia_startup_intel.nvidia_embeddings import (
        DeterministicFakeEmbeddingClient,
        embedding_client_from_config,
        embedding_provider_config_from_env,
    )
    from nvidia_startup_intel.nvidia_knowledge import load_nvidia_knowledge_corpus
    from nvidia_startup_intel.nvidia_knowledge import nvidia_knowledge_retrieval_to_dict
    from nvidia_startup_intel.nvidia_pgvector import PgvectorNVIDIAEmbeddingStore
    from nvidia_startup_intel.nvidia_retrievers import HybridNVIDIAPgvectorKnowledgeRetriever

    corpus = load_nvidia_knowledge_corpus(_corpus_path(context.env))
    embedding_client = (
        embedding_client_from_config(embedding_provider_config_from_env(context.env))
        if context.env.get("NVIDIA_STARTUP_INTEL_EMBEDDING_PROVIDER", "").strip()
        else DeterministicFakeEmbeddingClient(dimension=6)
    )
    store = PgvectorNVIDIAEmbeddingStore(_connect_postgres(_database_url(context.env)))
    retrieval = HybridNVIDIAPgvectorKnowledgeRetriever(
        corpus=corpus,
        embedding_client=embedding_client,
        vector_store=store,
        lexical_top_k=3,
        vector_top_k=3,
    ).retrieve_for_gap(
        run_id="run-hybrid-production-smoke",
        gap=TechnicalGap(
            gap_type="model_serving",
            description="Need lower latency production inference and model serving.",
            severity="high",
            confidence=0.9,
            evidences=(),
        ),
        startup_signals=("inferencia em producao", "latencia"),
        top_k=3,
    )
    if not retrieval.results:
        raise RuntimeError("hybrid retrieval returned no NVIDIA Knowledge chunks")
    return nvidia_knowledge_retrieval_to_dict(retrieval)


def _run_reranking(context: ProductionSmokeMatrixContext) -> object:
    from nvidia_startup_intel.nvidia_knowledge import load_nvidia_knowledge_corpus
    from nvidia_startup_intel.nvidia_knowledge import retrieve_nvidia_knowledge_by_gap
    from nvidia_startup_intel.nvidia_reranking import (
        SentenceTransformersCrossEncoderReranker,
        nvidia_rerank_result_to_dict,
        rerank_nvidia_retrieval,
    )

    corpus = load_nvidia_knowledge_corpus(_corpus_path(context.env))
    retrieval = retrieve_nvidia_knowledge_by_gap(
        corpus,
        run_id="run-reranking-production-smoke",
        gap_type="model_serving",
        description="Need lower latency production inference and model serving.",
        startup_signals=("inferencia em producao", "latencia"),
        top_k=5,
    )
    if not retrieval.results:
        raise RuntimeError("reranking smoke could not build candidate retrieval")
    reranker = SentenceTransformersCrossEncoderReranker(
        model_name=context.env["NVIDIA_STARTUP_INTEL_RERANKER_MODEL"],
        model_version=context.env.get("NVIDIA_STARTUP_INTEL_RERANKER_MODEL_VERSION", "unknown"),
    )
    result = rerank_nvidia_retrieval(
        retrieval,
        reranker,
        candidate_top_k=min(5, len(retrieval.results)),
    )
    return nvidia_rerank_result_to_dict(result)


def _run_langgraph_checkpoint(context: ProductionSmokeMatrixContext) -> object:
    from nvidia_startup_intel.nvidia_knowledge import load_nvidia_knowledge_corpus
    from nvidia_startup_intel.workflow_graph import (
        DownstreamWorkflowRuntime,
        IntelligenceWorkflowRuntime,
        build_intelligence_langgraph,
    )

    database_url = _database_url(context.env, langgraph=True)
    checkpointer = _postgres_checkpointer(database_url)
    seed_state = _seed_upstream_state(context.env)
    runtime = IntelligenceWorkflowRuntime(
        scraping=_exploding_scraping_runtime(),
        downstream=DownstreamWorkflowRuntime(corpus=load_nvidia_knowledge_corpus(_corpus_path(context.env))),
    )
    graph = build_intelligence_langgraph(runtime, checkpointer=checkpointer)
    state = graph.invoke(
        {
            **seed_state,
            "run_id": "run-langgraph-production-smoke",
            "query": "startups AI-native do Brasil",
        },
        config={"configurable": {"thread_id": "run-langgraph-production-smoke"}},
    )
    if state.get("workflow_outcome") not in {"briefing_generated", "human_review_requested"}:
        raise RuntimeError(f"unexpected LangGraph workflow outcome: {state.get('workflow_outcome')}")
    return {
        "workflow_outcome": state.get("workflow_outcome"),
        "startup_identifiers": list(state.get("startup_identifiers", ())),
        "branch_decisions": [getattr(branch, "branch_name", "") for branch in state.get("branch_decisions", ())],
    }


def _run_full_operational_smoke(context: ProductionSmokeMatrixContext) -> object:
    from nvidia_startup_intel.operational_entrypoint import (
        OperationalEntrypointOptions,
        run_operational_intelligence,
    )

    startup_url = context.env.get("NVIDIA_STARTUP_INTEL_PRODUCTION_SMOKE_STARTUP_URL", "").strip()
    query = context.env.get("NVIDIA_STARTUP_INTEL_PRODUCTION_SMOKE_QUERY", "").strip()
    if bool(startup_url) == bool(query):
        raise RuntimeError(
            "set exactly one of NVIDIA_STARTUP_INTEL_PRODUCTION_SMOKE_STARTUP_URL "
            "or NVIDIA_STARTUP_INTEL_PRODUCTION_SMOKE_QUERY"
        )
    payload = run_operational_intelligence(
        OperationalEntrypointOptions(
            startup_url=startup_url or None,
            query=query or None,
            startup_name=context.env.get("NVIDIA_STARTUP_INTEL_PRODUCTION_SMOKE_STARTUP_NAME", "unknown"),
            limit=_int_env(context.env, "NVIDIA_STARTUP_INTEL_PRODUCTION_SMOKE_LIMIT", 1),
            max_pages=_int_env(context.env, "NVIDIA_STARTUP_INTEL_PRODUCTION_SMOKE_MAX_PAGES", 1),
            max_depth=_int_env(context.env, "NVIDIA_STARTUP_INTEL_PRODUCTION_SMOKE_MAX_DEPTH", 0),
            timeout_seconds=_int_env(context.env, "NVIDIA_STARTUP_INTEL_PRODUCTION_SMOKE_TIMEOUT_SECONDS", 15),
            output_dir=context.env.get(
                "NVIDIA_STARTUP_INTEL_PRODUCTION_SMOKE_OUTPUT_DIR",
                "runs/production-smoke",
            ),
            persistence_mode=context.env.get(
                "NVIDIA_STARTUP_INTEL_PRODUCTION_SMOKE_PERSISTENCE_MODE",
                "json-postgres",
            ),
            nvidia_corpus_path=_corpus_path(context.env),
            render_js=True,
            retrieval_mode="pgvector",
            orchestration="langgraph",
            enable_search_provider=bool(query),
            enable_reranking=True,
            reranker_model=context.env.get("NVIDIA_STARTUP_INTEL_RERANKER_MODEL", ""),
            llm_narrative=True,
        )
    )
    _assert_final_briefing_payload(payload)
    return payload


def _run_llm_narrative_operational_fixture(context: ProductionSmokeMatrixContext) -> dict[str, object]:
    from nvidia_startup_intel.operational_entrypoint import (
        OperationalEntrypointOptions,
        run_operational_intelligence,
    )

    payload = run_operational_intelligence(
        OperationalEntrypointOptions(
            startup_url="https://vetai.example/",
            startup_name="VetAI",
            max_pages=1,
            max_depth=0,
            output_dir=context.env.get(
                "NVIDIA_STARTUP_INTEL_PRODUCTION_SMOKE_OUTPUT_DIR",
                "runs/production-smoke",
            ),
            persistence_mode="json",
            nvidia_corpus_path=_corpus_path(context.env),
            llm_narrative=True,
        ),
        fetcher=_fixture_fetcher,
        robots_fetcher=lambda _url: "User-agent: *\nAllow: /\n",
    )
    _assert_final_briefing_payload(payload)
    return payload


def _assert_final_briefing_payload(payload: Mapping[str, object]) -> None:
    if payload.get("workflow_outcome") == "failed_with_auditable_error":
        raise RuntimeError(f"full smoke failed with errors: {payload.get('errors')}")
    briefing_reference = payload.get("briefing_reference")
    if not isinstance(briefing_reference, Mapping):
        raise RuntimeError("full smoke did not produce a briefing reference")
    if briefing_reference.get("briefing_type") not in {"executive", "human_review"}:
        raise RuntimeError(f"unexpected briefing type: {briefing_reference.get('briefing_type')}")


def _seed_upstream_state(env: Mapping[str, str]) -> dict[str, object]:
    from nvidia_startup_intel.nvidia_knowledge import load_nvidia_knowledge_corpus
    from nvidia_startup_intel.robots import RobotsCache
    from nvidia_startup_intel.scraping_graph import ScrapingGraphRuntime
    from nvidia_startup_intel.search_execution import SearchProviderResult
    from nvidia_startup_intel.workflow_graph import (
        DownstreamWorkflowRuntime,
        IntelligenceWorkflowRuntime,
        build_local_intelligence_workflow,
    )

    runtime = IntelligenceWorkflowRuntime(
        scraping=ScrapingGraphRuntime(
            search_client=_FakeSearchClient(
                (
                    SearchProviderResult(
                        title="NeuralMind",
                        url="https://neuralmind.ai/",
                        snippet="NeuralMind desenvolve IA para documentos.",
                        position=1,
                    ),
                )
            ),
            fetcher=_fixture_fetcher,
            robots_cache=RobotsCache(fetcher=lambda _url: "User-agent: *\nAllow: /\n"),
            per_term_limit=1,
            max_pages_per_candidate=1,
        ),
        downstream=DownstreamWorkflowRuntime(corpus=load_nvidia_knowledge_corpus(_corpus_path(env))),
    )
    return build_local_intelligence_workflow(runtime).invoke(
        {
            "run_id": "run-langgraph-production-smoke-seed",
            "query": "startups AI-native do Brasil",
            "limit": 1,
        }
    )


def _exploding_scraping_runtime() -> object:
    from nvidia_startup_intel.scraping_graph import ScrapingGraphRuntime

    return ScrapingGraphRuntime(search_client=_ExplodingSearchClient())


def _postgres_checkpointer(database_url: str) -> object:
    try:
        from langgraph.checkpoint.postgres import PostgresSaver  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise RuntimeError(f"install langgraph-checkpoint-postgres to run this smoke: {exc}") from exc
    checkpointer = PostgresSaver.from_conn_string(database_url)
    setup = getattr(checkpointer, "setup", None)
    if callable(setup):
        setup()
    return checkpointer


def _connect_postgres(database_url: str) -> object:
    try:
        import psycopg  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise RuntimeError(f"install psycopg to run this smoke: {exc}") from exc
    return psycopg.connect(database_url)


def _database_url(env: Mapping[str, str], *, langgraph: bool = False) -> str:
    if langgraph:
        value = env.get("NVIDIA_STARTUP_INTEL_LANGGRAPH_CHECKPOINT_DATABASE_URL", "").strip()
        if value:
            return value
    value = (
        env.get("NVIDIA_STARTUP_INTEL_PGVECTOR_DATABASE_URL", "").strip()
        or env.get("DATABASE_URL", "").strip()
    )
    if not value:
        raise RuntimeError("set DATABASE_URL or NVIDIA_STARTUP_INTEL_PGVECTOR_DATABASE_URL")
    return value


def _corpus_path(env: Mapping[str, str]) -> Path:
    return Path(
        env.get(
            "NVIDIA_STARTUP_INTEL_PRODUCTION_SMOKE_CORPUS_PATH",
            "tests/fixtures/nvidia_knowledge_official_fixture.json",
        )
    )


def _int_env(env: Mapping[str, str], name: str, default: int) -> int:
    raw_value = env.get(name, "").strip()
    return int(raw_value) if raw_value else default


def _fixture_fetcher(url: str) -> object:
    from nvidia_startup_intel.page_collection import FetchResponse

    normalized = url.rstrip("/")
    if normalized not in {"https://vetai.example", "https://neuralmind.ai"}:
        raise TimeoutError(f"unexpected fixture URL: {url}")
    if normalized == "https://vetai.example":
        title = "VetAI"
        body = (
            "Resumo: Plataforma AI-native para triagem veterinaria. Setor: healthtech. "
            "Produto: Copiloto de triagem com IA para clinicas veterinarias. "
            "Sinais de IA: modelos proprietarios, fine-tuning, inferencia em producao e latencia. "
            "Tecnologias: MLOps, dados proprietarios, feedback loop e inferencia em producao. "
            "Clientes: clinicas veterinarias. Founders: unknown. Localizacao: Sao Paulo, SP."
        )
    else:
        title = "NeuralMind"
        body = (
            "Resumo: Plataforma AI-native para documentos. Setor: dados. "
            "Produto: Copiloto documental com IA generativa. Sinais de IA: modelos proprietarios, "
            "fine-tuning, inferencia em producao e latencia. Tecnologias: MLOps, dados proprietarios, "
            "feedback loop, model serving e inferencia em producao. Clientes: bancos. "
            "Founders: Ana Silva. Localizacao: Campinas, SP."
        )
    return FetchResponse(
        url=f"{normalized}/",
        status_code=200,
        body=f"<html><head><title>{title}</title></head><body>{body}</body></html>",
    )


class _FakeSearchClient:
    provider_name = "fake"

    def __init__(self, results: tuple[object, ...]) -> None:
        self.results = results

    def search(self, query: str, *, limit: int) -> tuple[object, ...]:
        del query
        return self.results[:limit]


class _ExplodingSearchClient:
    provider_name = "exploding"

    def search(self, query: str, *, limit: int) -> tuple[object, ...]:
        del query, limit
        raise AssertionError("checkpoint smoke must not repeat scraping")


if __name__ == "__main__":
    raise SystemExit(main())
