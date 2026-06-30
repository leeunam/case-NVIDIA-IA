"""Optional Postgres persistence smoke for complete startup runs.

The default test suite injects SQLite through the same repository contract.
Running this module directly uses the configured Postgres repository and writes
one deterministic smoke run to the operational store.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
import sys
from typing import Any

from nvidia_startup_intel.downstream_metrics import (
    RetrievalMetricExpectation,
    build_downstream_quality_report,
)
from nvidia_startup_intel.nvidia_knowledge import load_nvidia_knowledge_corpus
from nvidia_startup_intel.page_collection import FetchResponse
from nvidia_startup_intel.pipeline import (
    assess_profiles_ai_native,
    profile_result_key,
    run_controlled_startup_collection,
)
from nvidia_startup_intel.robots import RobotsCache
from nvidia_startup_intel.sql_repository import SqlPipelineRepository, postgres_repository_from_env
from nvidia_startup_intel.workflow_graph import DownstreamWorkflowRuntime, build_local_downstream_workflow


SCHEMA_VERSION = "postgres_persistence_smoke.v1"
DEFAULT_RUN_ID = "run-postgres-persistence-smoke"
DEFAULT_CORPUS_PATH = Path("tests/fixtures/nvidia_knowledge_official_fixture.json")


class PostgresPersistenceSmokeError(RuntimeError):
    """Actionable failure for the optional Postgres persistence smoke."""


@dataclass(frozen=True)
class PostgresPersistenceSmokeResult:
    schema_version: str
    run_id: str
    startup_identifier: str
    corpus_version: str
    persisted_collected_pages: int
    persisted_collection_errors: int
    persisted_startup_profiles: int
    persisted_field_evidences: int
    persisted_collection_quality_summaries: int
    persisted_ai_native_assessments: int
    persisted_retrievals: int
    persisted_recommendation_sets: int
    persisted_briefings: int
    persisted_metrics: int
    ready_for_reprocessing: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def run_postgres_persistence_smoke(
    *,
    repository_factory: Callable[[], SqlPipelineRepository] | None = None,
    run_id: str = DEFAULT_RUN_ID,
    corpus_path: Path = DEFAULT_CORPUS_PATH,
    clock: Callable[[], datetime] | None = None,
) -> PostgresPersistenceSmokeResult:
    """Validate the complete operational persistence path with local fixtures."""

    repository = (repository_factory or postgres_repository_from_env)()
    should_close_repository = repository_factory is None
    created_at = (clock or _utc_now)()
    try:
        repository.create_run(run_id=run_id, created_at=created_at)
        collection_result = run_controlled_startup_collection(
            "https://vetai.example/",
            startup_name="VetAI",
            fetcher=_fixture_fetcher,
            robots_cache=RobotsCache(fetcher=_allow_robots),
            max_pages_per_candidate=1,
            max_depth=0,
        )
        repository.save_pipeline_result(run_id, collection_result)

        assessments = assess_profiles_ai_native(
            collection_result.profiles,
            collection_result.evidence_groups_by_profile,
            collection_result.quality_summary,
            run_id=run_id,
        )
        repository.save_ai_native_assessments(run_id, assessments)

        profile = _single(collection_result.profiles, "startup profile")
        assessment = assessments.get(profile.company_name.value)
        if assessment is None:
            raise PostgresPersistenceSmokeError("AI-native assessment was not persisted for VetAI.")

        corpus = load_nvidia_knowledge_corpus(corpus_path)
        workflow = build_local_downstream_workflow(
            DownstreamWorkflowRuntime(corpus=corpus, artifact_store=repository)
        )
        state = workflow.invoke(
            {
                "run_id": run_id,
                "profile": profile,
                "evidence_groups": collection_result.evidence_groups_by_profile.get(
                    profile_result_key(profile),
                    (),
                ),
                "collection_quality": collection_result.quality_summary,
                "assessment": assessment,
            }
        )
        if state.get("errors"):
            raise PostgresPersistenceSmokeError(f"Downstream workflow errors: {state['errors']}")

        startup_identifier = state["recommendation_set"].startup_identifier
        metrics = build_downstream_quality_report(
            run_id=run_id,
            startup_identifier=startup_identifier,
            retrievals=state.get("retrievals", ()),
            retrieval_expectations=(
                RetrievalMetricExpectation(
                    expectation_id="model-serving-nim",
                    target_type="technical_gap",
                    target="model_serving",
                    expected_chunk_ids=("nvidia-nim-developers:0",),
                ),
            ),
            recommendation_set=state["recommendation_set"],
        )
        repository.save_downstream_state({**state, "downstream_quality_report": metrics})

        stored = repository.load_operational_run(run_id, startup_identifier=startup_identifier)
        reprocessing_artifacts = repository.load_downstream_artifacts_for_reprocessing(
            run_id,
            startup_identifier=startup_identifier,
            corpus_version=corpus.corpus_version,
        )
        result = PostgresPersistenceSmokeResult(
            schema_version=SCHEMA_VERSION,
            run_id=run_id,
            startup_identifier=startup_identifier,
            corpus_version=corpus.corpus_version,
            persisted_collected_pages=_count_page_rows(stored.upstream.collected_pages, is_error=False),
            persisted_collection_errors=_count_page_rows(stored.upstream.collected_pages, is_error=True),
            persisted_startup_profiles=len(stored.upstream.startup_profiles),
            persisted_field_evidences=len(stored.upstream.field_evidences),
            persisted_collection_quality_summaries=len(stored.upstream.collection_quality_summaries),
            persisted_ai_native_assessments=len(stored.upstream.ai_native_assessments),
            persisted_retrievals=len(stored.downstream.retrievals),
            persisted_recommendation_sets=len(stored.downstream.recommendation_sets),
            persisted_briefings=len(stored.downstream.briefings),
            persisted_metrics=len(stored.downstream.metrics),
            ready_for_reprocessing=bool(
                reprocessing_artifacts.retrievals and reprocessing_artifacts.recommendation_sets
            ),
        )
        _validate_result(result)
        return result
    finally:
        close = getattr(getattr(repository, "connection", None), "close", None)
        if should_close_repository and callable(close):
            close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run optional real Postgres persistence smoke.")
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    args = parser.parse_args(argv)

    try:
        result = run_postgres_persistence_smoke(run_id=args.run_id, corpus_path=args.corpus)
    except PostgresPersistenceSmokeError as exc:
        print(f"OPTIONAL POSTGRES PERSISTENCE SMOKE FAILED: {exc}", file=sys.stderr)
        return 2

    print("OPTIONAL POSTGRES PERSISTENCE SMOKE PASSED")
    for key, value in result.to_dict().items():
        print(f"{key}: {value}")
    return 0


def _fixture_fetcher(url: str) -> FetchResponse:
    if url.rstrip("/") != "https://vetai.example":
        raise TimeoutError(f"unexpected fixture URL: {url}")
    return FetchResponse(
        url="https://vetai.example/",
        status_code=200,
        body=(
            "<html><head><title>VetAI</title></head><body>"
            "Resumo: Plataforma AI-native para triagem veterinaria. Setor: healthtech. "
            "Produto: Copiloto de triagem com IA para clinicas veterinarias. "
            "Sinais de IA: modelos proprietarios, fine-tuning, inferencia em producao e latencia. "
            "Tecnologias: MLOps, dados proprietarios, feedback loop e inferencia em producao. "
            "Clientes: clinicas veterinarias. Founders: unknown. Localizacao: Sao Paulo, SP."
            "</body></html>"
        ),
    )


def _allow_robots(url: str) -> str:
    del url
    return "User-agent: *\nAllow: /\n"


def _single(items: tuple[Any, ...], label: str) -> Any:
    if len(items) != 1:
        raise PostgresPersistenceSmokeError(f"Expected one {label}, got {len(items)}.")
    return items[0]


def _count_page_rows(rows: tuple[dict[str, Any], ...], *, is_error: bool) -> int:
    return sum(1 for row in rows if bool(row.get("is_error")) is is_error)


def _validate_result(result: PostgresPersistenceSmokeResult) -> None:
    missing: list[str] = []
    if result.persisted_collected_pages < 1:
        missing.append("collected_pages")
    if result.persisted_startup_profiles < 1:
        missing.append("startup_profiles")
    if result.persisted_field_evidences < 1:
        missing.append("field_evidences")
    if result.persisted_collection_quality_summaries < 1:
        missing.append("collection_quality")
    if result.persisted_ai_native_assessments < 1:
        missing.append("ai_native_assessments")
    if result.persisted_retrievals < 1:
        missing.append("retrievals")
    if result.persisted_recommendation_sets < 1:
        missing.append("recommendation_sets")
    if result.persisted_briefings < 1:
        missing.append("briefings")
    if result.persisted_metrics < 1:
        missing.append("metrics")
    if not result.ready_for_reprocessing:
        missing.append("reprocessing_artifacts")
    if missing:
        raise PostgresPersistenceSmokeError("Missing persisted artifacts: " + ", ".join(missing))


def _utc_now() -> datetime:
    return datetime.now(UTC)


if __name__ == "__main__":
    raise SystemExit(main())
