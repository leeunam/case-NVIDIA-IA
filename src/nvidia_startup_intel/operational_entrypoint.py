"""Operational entrypoint for the complete local intelligence workflow."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields, is_dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
import os
import re

from nvidia_startup_intel.ai_native_assessment import TechnicalGap
from nvidia_startup_intel.llm_adapters import LiteLLMClient, llm_provider_config_from_env
from nvidia_startup_intel.nvidia_embeddings import embedding_client_from_config, embedding_provider_config_from_env
from nvidia_startup_intel.nvidia_knowledge import (
    NVIDIAKnowledgeQuery,
    NVIDIAKnowledgeRetrieval,
    RetrievedNVIDIAKnowledge,
    load_nvidia_knowledge_corpus,
)
from nvidia_startup_intel.nvidia_pgvector import PgvectorNVIDIAEmbeddingStore
from nvidia_startup_intel.nvidia_reranking import (
    NVIDIAReranker,
    SentenceTransformersCrossEncoderReranker,
    rerank_nvidia_retrieval,
)
from nvidia_startup_intel.nvidia_retrievers import (
    HybridNVIDIAPgvectorKnowledgeRetriever,
    NVIDIAKnowledgeRetriever,
)
from nvidia_startup_intel.page_collection import (
    Fetcher,
    PlaywrightPageRenderer,
    PlaywrightRenderer,
    StaticHTMLExtractionAdapter,
    fetch_url,
)
from nvidia_startup_intel.persistence import JsonIntelligenceArtifactStore
from nvidia_startup_intel.pipeline import assess_profiles_ai_native, run_controlled_startup_collection
from nvidia_startup_intel.robots import RobotsCache, RobotsFetcher
from nvidia_startup_intel.scraping_graph import ScrapingGraphRuntime
from nvidia_startup_intel.search_execution import SearchClient, search_client_from_env
from nvidia_startup_intel.search_params import UNKNOWN
from nvidia_startup_intel.sql_repository import SqlPipelineRepository, postgres_repository_from_env
from nvidia_startup_intel.workflow_graph import (
    DownstreamWorkflowError,
    DownstreamWorkflowRuntime,
    IntelligenceArtifactStore,
    IntelligenceWorkflowRuntime,
    build_intelligence_langgraph,
    build_local_intelligence_workflow,
)


SCHEMA_VERSION = "operational_entrypoint_result.v1"
DEFAULT_NVIDIA_CORPUS_PATH = "tests/fixtures/nvidia_knowledge_official_fixture.json"
Clock = Callable[[], datetime]
SqlRepositoryFactory = Callable[[], SqlPipelineRepository]


@dataclass(frozen=True)
class OperationalEntrypointOptions:
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


class DisabledSearchClient:
    provider_name = "disabled"

    def search(self, query: str, *, limit: int) -> tuple[object, ...]:
        raise RuntimeError("search_client_required_for_bounded_query")


class CompositeIntelligenceArtifactStore:
    """Fan out workflow persistence calls to multiple stores."""

    def __init__(self, stores: tuple[IntelligenceArtifactStore, ...]) -> None:
        self.stores = stores

    def create_run(self, *, run_id: str) -> str:
        for store in self.stores:
            store.create_run(run_id=run_id)
        return run_id

    def save_pipeline_result(self, run_id: str, result: object) -> None:
        for store in self.stores:
            store.save_pipeline_result(run_id, result)  # type: ignore[arg-type]

    def save_ai_native_assessments(self, run_id: str, assessments_by_profile: Mapping[str, object]) -> None:
        for store in self.stores:
            store.save_ai_native_assessments(run_id, assessments_by_profile)  # type: ignore[arg-type]

    def save_downstream_state(self, state: Mapping[str, object]) -> None:
        for store in self.stores:
            store.save_downstream_state(state)  # type: ignore[arg-type]


@dataclass(frozen=True)
class RerankingNVIDIAKnowledgeRetriever:
    base_retriever: NVIDIAKnowledgeRetriever
    reranker: NVIDIAReranker
    candidate_top_k: int = 30

    def retrieve_for_query(
        self,
        *,
        run_id: str,
        query: NVIDIAKnowledgeQuery,
        top_k: int,
    ) -> NVIDIAKnowledgeRetrieval:
        retrieval = self.base_retriever.retrieve_for_query(
            run_id=run_id,
            query=query,
            top_k=max(top_k, self.candidate_top_k),
        )
        return _reranked_retrieval(retrieval, self.reranker, candidate_top_k=self.candidate_top_k, top_k=top_k)

    def retrieve_for_gap(
        self,
        *,
        run_id: str,
        gap: TechnicalGap,
        startup_signals: tuple[str, ...],
        top_k: int,
    ) -> NVIDIAKnowledgeRetrieval:
        retrieval = self.base_retriever.retrieve_for_gap(
            run_id=run_id,
            gap=gap,
            startup_signals=startup_signals,
            top_k=max(top_k, self.candidate_top_k),
        )
        return _reranked_retrieval(retrieval, self.reranker, candidate_top_k=self.candidate_top_k, top_k=top_k)


def run_operational_intelligence(
    options: OperationalEntrypointOptions,
    *,
    fetcher: Fetcher | None = None,
    playwright_renderer: PlaywrightRenderer | None = None,
    robots_fetcher: RobotsFetcher | None = None,
    search_client: SearchClient | None = None,
    sql_repository_factory: SqlRepositoryFactory | None = None,
    clock: Clock | None = None,
) -> dict[str, object]:
    """Run the complete intelligence workflow and return a structured final payload."""

    created_at = (clock or _utc_now)()
    run_id = _run_id(created_at)
    json_store: JsonIntelligenceArtifactStore | None = None
    artifact_store = _artifact_store(
        options,
        created_at=created_at,
        sql_repository_factory=sql_repository_factory,
    )
    if isinstance(artifact_store, JsonIntelligenceArtifactStore):
        json_store = artifact_store
    elif isinstance(artifact_store, CompositeIntelligenceArtifactStore):
        json_store = next(
            (store for store in artifact_store.stores if isinstance(store, JsonIntelligenceArtifactStore)),
            None,
        )

    try:
        state = _run_workflow(
            options,
            run_id=run_id,
            fetcher=fetcher,
            playwright_renderer=playwright_renderer,
            robots_fetcher=robots_fetcher,
            search_client=search_client,
            artifact_store=artifact_store,
        )
    except Exception as exc:  # noqa: BLE001 - final payload is the operational error boundary.
        state = {
            "run_id": run_id,
            "workflow_outcome": "failed_with_auditable_error",
            "next_action": "review_workflow_errors",
            "startup_identifiers": (),
            "branch_decisions": (),
            "persistence_references": (),
            "errors": (
                DownstreamWorkflowError(
                    step="run_operational_intelligence",
                    error_type=type(exc).__name__,
                    message=str(exc),
                    audit_reason="operational_entrypoint_failed_structured_error",
                ),
            ),
        }

    return _final_payload(
        state,
        options=options,
        run_id=run_id,
        created_at=created_at,
        json_store=json_store,
    )


def _run_workflow(
    options: OperationalEntrypointOptions,
    *,
    run_id: str,
    fetcher: Fetcher | None,
    playwright_renderer: PlaywrightRenderer | None,
    robots_fetcher: RobotsFetcher | None,
    search_client: SearchClient | None,
    artifact_store: IntelligenceArtifactStore | None,
) -> Mapping[str, object]:
    _validate_options(options)
    active_fetcher = fetcher or (lambda url: fetch_url(url, timeout=options.timeout_seconds))
    active_renderer = _playwright_renderer(options, playwright_renderer)
    robots_cache = _robots_cache(options, robots_fetcher)
    corpus = load_nvidia_knowledge_corpus(options.nvidia_corpus_path)
    runtime = IntelligenceWorkflowRuntime(
        scraping=ScrapingGraphRuntime(
            search_client=_search_client(options, search_client),
            fetcher=active_fetcher,
            robots_cache=robots_cache,
            per_term_limit=options.limit,
            max_pages_per_candidate=options.max_pages,
            max_depth=options.max_depth,
        ),
        downstream=_downstream_runtime(options, corpus),
        artifact_store=artifact_store,
    )
    runtime.downstream.artifact_store = artifact_store

    initial_state = _initial_state(
        options,
        run_id=run_id,
        fetcher=active_fetcher,
        playwright_renderer=active_renderer,
        robots_cache=robots_cache,
    )
    if options.orchestration == "langgraph":
        return build_intelligence_langgraph(runtime).invoke(initial_state)
    return build_local_intelligence_workflow(runtime).invoke(initial_state)


def _initial_state(
    options: OperationalEntrypointOptions,
    *,
    run_id: str,
    fetcher: Fetcher,
    playwright_renderer: PlaywrightRenderer | None,
    robots_cache: RobotsCache | None,
) -> dict[str, object]:
    if options.startup_url:
        result = run_controlled_startup_collection(
            options.startup_url,
            startup_name=options.startup_name,
            fetcher=fetcher,
            playwright_renderer=playwright_renderer,
            html_extractor=StaticHTMLExtractionAdapter(),
            robots_cache=robots_cache,
            max_pages_per_candidate=options.max_pages,
            max_depth=options.max_depth,
        )
        assessments = assess_profiles_ai_native(
            result.profiles,
            result.evidence_groups_by_profile,
            result.quality_summary,
            run_id=run_id,
        )
        return {
            "run_id": run_id,
            "query": f"controlled startup intelligence for {options.startup_url}",
            "limit": 1,
            "search_params": result.search_params,
            "search_plan": result.search_plan,
            "raw_results": result.raw_results,
            "search_errors": result.search_errors,
            "candidates": result.candidates,
            "collected_pages_by_candidate": result.collected_pages_by_candidate,
            "profiles": result.profiles,
            "evidence_groups_by_profile": result.evidence_groups_by_profile,
            "quality_summary": result.quality_summary,
            "ai_native_assessments_by_profile": assessments,
        }

    return {
        "run_id": run_id,
        "query": str(options.query or ""),
        "limit": options.limit,
    }


def _downstream_runtime(options: OperationalEntrypointOptions, corpus: object) -> DownstreamWorkflowRuntime:
    runtime = DownstreamWorkflowRuntime(corpus=corpus)  # type: ignore[arg-type]
    if options.retrieval_mode == "pgvector":
        embedding_client = embedding_client_from_config(embedding_provider_config_from_env())
        vector_store = _pgvector_store_from_env()
        runtime.embedding_client = embedding_client
        runtime.vector_store = vector_store
        base_retriever = HybridNVIDIAPgvectorKnowledgeRetriever(
            corpus=corpus,  # type: ignore[arg-type]
            embedding_client=embedding_client,
            vector_store=vector_store,
        )
        runtime.knowledge_retriever = base_retriever
        if options.enable_reranking:
            runtime.knowledge_retriever = RerankingNVIDIAKnowledgeRetriever(
                base_retriever=base_retriever,
                reranker=_reranker_from_options(options),
            )
    elif options.enable_reranking:
        raise ValueError("reranking_requires_pgvector_hybrid_retrieval")
    if options.llm_narrative:
        runtime.llm_client = LiteLLMClient(llm_provider_config_from_env())
    return runtime


def _artifact_store(
    options: OperationalEntrypointOptions,
    *,
    created_at: datetime,
    sql_repository_factory: SqlRepositoryFactory | None,
) -> IntelligenceArtifactStore | None:
    stores: list[IntelligenceArtifactStore] = []
    if options.persistence_mode in {"json", "json-postgres"}:
        stores.append(JsonIntelligenceArtifactStore(options.output_dir, created_at=created_at))
    if options.persistence_mode in {"postgres", "json-postgres"}:
        stores.append((sql_repository_factory or postgres_repository_from_env)())
    if not stores:
        return None
    if len(stores) == 1:
        return stores[0]
    return CompositeIntelligenceArtifactStore(tuple(stores))


def _final_payload(
    state: Mapping[str, object],
    *,
    options: OperationalEntrypointOptions,
    run_id: str,
    created_at: datetime,
    json_store: JsonIntelligenceArtifactStore | None,
) -> dict[str, object]:
    startup_identifier = _startup_identifier(state)
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "created_at": _format_time(created_at),
        "input": {
            "startup_url": options.startup_url,
            "query": options.query,
            "startup_name": options.startup_name,
        },
        "startup_identifier": startup_identifier,
        "workflow_outcome": str(state.get("workflow_outcome", "unknown")),
        "next_action": str(state.get("next_action", "review_workflow_output")),
        "briefing_reference": _briefing_reference(state, startup_identifier=startup_identifier, json_store=json_store),
        "human_review_reasons": _human_review_reasons(state),
        "branch_decisions": _plain_data(state.get("branch_decisions", ())),
        "artifact_locations": _artifact_locations(json_store),
        "persistence_references": _plain_data(state.get("persistence_references", ())),
        "errors": _plain_data(state.get("errors", ())),
        "options": _options_payload(options),
    }


def _validate_options(options: OperationalEntrypointOptions) -> None:
    if bool(options.startup_url) == bool(options.query):
        raise ValueError("provide_exactly_one_of_startup_url_or_query")
    if options.limit < 1:
        raise ValueError("limit_must_be_greater_than_zero")
    if options.max_pages < 1:
        raise ValueError("max_pages_must_be_greater_than_zero")
    if options.max_depth < 0:
        raise ValueError("max_depth_must_be_zero_or_greater")


def _search_client(options: OperationalEntrypointOptions, search_client: SearchClient | None) -> SearchClient:
    if search_client is not None:
        return search_client
    if options.enable_search_provider:
        return search_client_from_env()
    return DisabledSearchClient()  # type: ignore[return-value]


def _playwright_renderer(
    options: OperationalEntrypointOptions,
    renderer: PlaywrightRenderer | None,
) -> PlaywrightRenderer | None:
    if not options.render_js:
        return None
    return renderer or PlaywrightPageRenderer(timeout_ms=options.timeout_seconds * 1000)


def _robots_cache(
    options: OperationalEntrypointOptions,
    robots_fetcher: RobotsFetcher | None,
) -> RobotsCache | None:
    if options.robots_policy == "off":
        return None
    return RobotsCache(
        conservative_on_error=options.robots_policy == "conservative",
        fetcher=robots_fetcher,
    )


def _pgvector_store_from_env() -> PgvectorNVIDIAEmbeddingStore:
    database_url = os.environ.get("NVIDIA_STARTUP_INTEL_PGVECTOR_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL or NVIDIA_STARTUP_INTEL_PGVECTOR_DATABASE_URL is required")
    try:
        import psycopg  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise RuntimeError("Install psycopg to use pgvector retrieval") from exc
    return PgvectorNVIDIAEmbeddingStore(psycopg.connect(database_url))


def _reranker_from_options(options: OperationalEntrypointOptions) -> NVIDIAReranker:
    model_name = options.reranker_model or os.environ.get("NVIDIA_STARTUP_INTEL_RERANKER_MODEL", "")
    if not model_name:
        raise ValueError("NVIDIA_STARTUP_INTEL_RERANKER_MODEL or --reranker-model is required")
    model_version = os.environ.get("NVIDIA_STARTUP_INTEL_RERANKER_MODEL_VERSION", "unknown")
    return SentenceTransformersCrossEncoderReranker(
        model_name=model_name,
        model_version=model_version,
    )


def _reranked_retrieval(
    retrieval: NVIDIAKnowledgeRetrieval,
    reranker: NVIDIAReranker,
    *,
    candidate_top_k: int,
    top_k: int,
) -> NVIDIAKnowledgeRetrieval:
    rerank_result = rerank_nvidia_retrieval(
        retrieval,
        reranker,
        candidate_top_k=candidate_top_k,
    )
    original_by_chunk_id = {result.chunk.chunk_id: result for result in retrieval.results}
    reranked_results: list[RetrievedNVIDIAKnowledge] = []
    for rank, item in enumerate(rerank_result.results[:top_k], start=1):
        original = original_by_chunk_id[item.chunk.chunk_id]
        reranked_results.append(
            replace(
                original,
                rank=rank,
                rationale=f"{original.rationale} Reranked by {rerank_result.ranking_strategy}.",
            )
        )
    return replace(retrieval, results=tuple(reranked_results))


def _startup_identifier(state: Mapping[str, object]) -> str:
    identifiers: tuple[object, ...] = tuple(state.get("startup_identifiers", ()))  # type: ignore[arg-type]
    if identifiers:
        return str(identifiers[0])
    downstream_states = state.get("downstream_states_by_startup", {})
    if isinstance(downstream_states, Mapping) and downstream_states:
        return str(next(iter(downstream_states)))
    return UNKNOWN


def _briefing_reference(
    state: Mapping[str, object],
    *,
    startup_identifier: str,
    json_store: JsonIntelligenceArtifactStore | None,
) -> dict[str, object] | None:
    downstream = _first_downstream_state(state)
    if downstream is None:
        return None
    if json_store is None or json_store.run is None:
        return {"storage": "workflow_state", "path": UNKNOWN, "briefing_type": _briefing_type(downstream)}
    briefing_type = _briefing_type(downstream)
    if briefing_type == UNKNOWN:
        return None
    return {
        "storage": "json",
        "path": str(
            json_store.run.processed_dir
            / "downstream"
            / _safe_path_segment(startup_identifier)
            / "briefing.json"
        ),
        "briefing_type": briefing_type,
    }


def _briefing_type(downstream: Mapping[str, object]) -> str:
    if "executive_briefing" in downstream:
        return "executive"
    if "human_review_briefing" in downstream:
        return "human_review"
    return UNKNOWN


def _first_downstream_state(state: Mapping[str, object]) -> Mapping[str, object] | None:
    downstream_states = state.get("downstream_states_by_startup", {})
    if isinstance(downstream_states, Mapping) and downstream_states:
        first = next(iter(downstream_states.values()))
        if isinstance(first, Mapping):
            return first
    return None


def _human_review_reasons(state: Mapping[str, object]) -> list[str]:
    reasons: list[str] = []
    for branch in state.get("branch_decisions", ()):
        branch_name = getattr(branch, "branch_name", "")
        if branch_name in {"human_review_requested", "needs_more_collection_or_human_review"}:
            reasons.append(str(getattr(branch, "audit_reason", "")))
    for error in state.get("errors", ()):
        reasons.append(str(getattr(error, "audit_reason", "")))
    return [reason for reason in dict.fromkeys(reasons) if reason]


def _artifact_locations(json_store: JsonIntelligenceArtifactStore | None) -> dict[str, object]:
    if json_store is None or json_store.run is None:
        return {}
    run = json_store.run
    return {
        "json_run_dir": str(run.root_dir),
        "manifest": str(run.root_dir / "manifest.json"),
        "raw_dir": str(run.raw_dir),
        "processed_dir": str(run.processed_dir),
    }


def _options_payload(options: OperationalEntrypointOptions) -> dict[str, object]:
    return {
        "limit": options.limit,
        "max_pages": options.max_pages,
        "max_depth": options.max_depth,
        "timeout_seconds": options.timeout_seconds,
        "persistence_mode": options.persistence_mode,
        "render_js": options.render_js,
        "robots_policy": options.robots_policy,
        "retrieval_mode": options.retrieval_mode,
        "orchestration": options.orchestration,
        "search_provider": options.enable_search_provider,
        "reranking": options.enable_reranking,
        "reranker_model": options.reranker_model,
        "llm_narrative": options.llm_narrative,
        "nvidia_corpus_path": str(options.nvidia_corpus_path),
    }


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


def _safe_path_segment(value: str) -> str:
    segment = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip(".-")
    return segment or "unknown"


def _run_id(value: datetime) -> str:
    return f"op-{_utc(value).strftime('%Y%m%dT%H%M%SZ')}"


def _format_time(value: datetime) -> str:
    return _utc(value).isoformat()


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _utc_now() -> datetime:
    return datetime.now(UTC)
