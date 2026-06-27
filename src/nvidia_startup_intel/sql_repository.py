"""Relational persistence for scraping pipeline runs.

The repository stores auditable pipeline artifacts in normalized run tables,
while keeping each payload as JSON to avoid premature schema churn during the
walking skeleton phase. It accepts a DB-API connection, so tests run on SQLite
and development can use Postgres through the Docker Compose service.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from enum import Enum
import json
import os
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from nvidia_startup_intel.ai_native_assessment import AINativeAssessment
from nvidia_startup_intel.collection_quality import CollectionQualitySummary
from nvidia_startup_intel.discovery import CandidateStartup, RawDiscoveryResult
from nvidia_startup_intel.downstream_artifacts import (
    build_downstream_artifact_snapshot,
    build_downstream_briefing_artifact,
    build_downstream_recommendation_artifact,
    build_downstream_retrieval_artifact,
    downstream_briefing_payload,
    downstream_briefing_status,
    downstream_briefing_type,
    downstream_retrieval_strategy,
    downstream_startup_identifier,
)
from nvidia_startup_intel.evidence import FieldEvidenceGroup
from nvidia_startup_intel.nvidia_knowledge import (
    NVIDIAKnowledgeChunk,
    NVIDIAKnowledgeCorpus,
    NVIDIAKnowledgeDocument,
    validate_nvidia_knowledge_corpus,
)
from nvidia_startup_intel.page_collection import PageCollectionResult
from nvidia_startup_intel.pipeline import ScrapingPipelineResult, candidate_result_key, profile_result_key
from nvidia_startup_intel.search_params import SearchParams
from nvidia_startup_intel.search_plan import SearchPlan
from nvidia_startup_intel.startup_profile import StartupProfile


@dataclass(frozen=True)
class StoredPipelineRun:
    run_id: str
    created_at: str
    search_params: dict[str, Any] | None
    search_plan_items: tuple[dict[str, Any], ...]
    raw_discovery_results: tuple[dict[str, Any], ...]
    candidate_startups: tuple[dict[str, Any], ...]
    collected_pages: tuple[dict[str, Any], ...]
    startup_profiles: tuple[dict[str, Any], ...]
    field_evidences: tuple[dict[str, Any], ...]
    collection_quality_summaries: tuple[dict[str, Any], ...]
    ai_native_assessments: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class StoredDownstreamArtifacts:
    run_id: str
    startup_identifier: str
    retrievals: tuple[dict[str, Any], ...]
    recommendation_sets: tuple[dict[str, Any], ...]
    briefings: tuple[dict[str, Any], ...]


class SqlPipelineRepository:
    """Persist and load scraping pipeline runs using a DB-API connection."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection
        self._postgres = "psycopg" in type(connection).__module__
        self._transaction_depth = 0

    def initialize_schema(self) -> None:
        statements = POSTGRES_SCHEMA_STATEMENTS if self._postgres else SQLITE_SCHEMA_STATEMENTS
        if not self._postgres:
            self.connection.execute("PRAGMA foreign_keys = ON")
        for statement in statements:
            self.connection.execute(statement)
        self.connection.commit()

    def create_run(
        self,
        *,
        run_id: str | None = None,
        created_at: datetime | None = None,
        search_params: SearchParams | None = None,
    ) -> str:
        resolved_run_id = run_id or _new_run_id()
        created = _format_time(created_at or datetime.now(UTC))
        self._execute(
            "INSERT INTO pipeline_runs (run_id, created_at, search_params_json) VALUES (?, ?, ?)",
            (resolved_run_id, created, _dumps(search_params) if search_params is not None else None),
        )
        self._commit()
        return resolved_run_id

    def save_search_plan(self, run_id: str, plan: SearchPlan) -> None:
        self._execute("DELETE FROM search_plan_items WHERE run_id = ?", (run_id,))
        for item in plan.items:
            self._execute(
                """
                INSERT INTO search_plan_items
                (run_id, priority, term, target_source, scope, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, item.priority, item.term, item.target_source, item.scope.value, _dumps(item)),
            )
        self._commit()

    def save_raw_discovery_results(self, run_id: str, results: Sequence[RawDiscoveryResult]) -> None:
        self._execute("DELETE FROM raw_discovery_results WHERE run_id = ?", (run_id,))
        for position, result in enumerate(results, start=1):
            self._execute(
                """
                INSERT INTO raw_discovery_results
                (run_id, position, title, url, source_name, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, position, result.title, result.url, result.source_name, _dumps(result)),
            )
        self._commit()

    def save_candidate_startups(self, run_id: str, candidates: Sequence[CandidateStartup]) -> None:
        self._execute("DELETE FROM candidate_startups WHERE run_id = ?", (run_id,))
        for candidate in candidates:
            candidate_key = candidate_result_key(candidate)
            self._execute(
                """
                INSERT INTO candidate_startups
                (run_id, candidate_key, name, normalized_name, primary_url, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    candidate_key,
                    candidate.name,
                    candidate.normalized_name,
                    candidate.primary_url,
                    _dumps(candidate),
                ),
            )
        self._commit()

    def save_collected_pages(
        self,
        run_id: str,
        results_by_candidate: Mapping[str, PageCollectionResult],
        *,
        candidate_keys: Mapping[str, str] | None = None,
        candidate_names: Mapping[str, str] | None = None,
    ) -> None:
        self._execute("DELETE FROM collected_pages WHERE run_id = ?", (run_id,))
        for candidate_ref, result in results_by_candidate.items():
            candidate_key = _lookup_key(candidate_keys, candidate_ref)
            candidate_name = _lookup_key(candidate_names, candidate_key)
            for page in result.pages:
                self._execute(
                    """
                    INSERT INTO collected_pages
                    (run_id, candidate_key, candidate_name, url, status_code, payload_json, is_error)
                    VALUES (?, ?, ?, ?, ?, ?, 0)
                    """,
                    (run_id, candidate_key, candidate_name, page.url, page.status_code, _dumps(page)),
                )
            for error in result.errors:
                self._execute(
                    """
                    INSERT INTO collected_pages
                    (run_id, candidate_key, candidate_name, url, status_code, payload_json, is_error)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                    """,
                    (run_id, candidate_key, candidate_name, error.url, error.status_code, _dumps(error)),
                )
        self._commit()

    def save_startup_profiles(self, run_id: str, profiles: Sequence[StartupProfile]) -> None:
        self._execute("DELETE FROM startup_profiles WHERE run_id = ?", (run_id,))
        for profile in profiles:
            profile_key = profile_result_key(profile)
            self._execute(
                """
                INSERT INTO startup_profiles
                (run_id, profile_key, company_name, schema_version, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, profile_key, profile.company_name.value, profile.schema_version, _dumps(profile)),
            )
        self._commit()

    def save_field_evidences(
        self,
        run_id: str,
        evidences_by_profile: Mapping[str, Sequence[FieldEvidenceGroup]],
        *,
        profile_keys: Mapping[str, str] | None = None,
        profile_names: Mapping[str, str] | None = None,
    ) -> None:
        self._execute("DELETE FROM field_evidences WHERE run_id = ?", (run_id,))
        for profile_ref, groups in evidences_by_profile.items():
            profile_key = _lookup_key(profile_keys, profile_ref)
            company_name = _lookup_key(profile_names, profile_key)
            for group in groups:
                for evidence in group.evidences:
                    self._execute(
                        """
                        INSERT INTO field_evidences
                        (run_id, profile_key, company_name, field_name, evidence_url, payload_json)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            profile_key,
                            company_name,
                            group.field_name,
                            evidence.url,
                            _dumps({"group": group, "evidence": evidence}),
                        ),
                    )
        self._commit()

    def save_collection_quality(self, run_id: str, summary: CollectionQualitySummary) -> None:
        self._execute("DELETE FROM collection_quality_summaries WHERE run_id = ?", (run_id,))
        self._execute(
            """
            INSERT INTO collection_quality_summaries
            (run_id, ready_for_evaluation, payload_json)
            VALUES (?, ?, ?)
            """,
            (run_id, int(summary.ready_for_evaluation), _dumps(summary)),
        )
        self._commit()

    def save_ai_native_assessments(
        self,
        run_id: str,
        assessments_by_profile: Mapping[str, AINativeAssessment],
    ) -> None:
        self._execute("DELETE FROM ai_native_assessments WHERE run_id = ?", (run_id,))
        for company_name, assessment in assessments_by_profile.items():
            self._execute(
                """
                INSERT INTO ai_native_assessments
                (run_id, company_name, classification, ready_for_recommendation, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    company_name,
                    assessment.classification,
                    int(assessment.ready_for_recommendation),
                    _dumps(assessment),
                ),
        )
        self._commit()

    def save_downstream_state(self, state: Mapping[str, Any]) -> None:
        """Persist downstream workflow artifacts from the local runner state."""

        snapshot = build_downstream_artifact_snapshot(state)
        run_id = snapshot.run_id

        with self._transaction():
            if snapshot.retrievals:
                self.save_downstream_retrievals(
                    run_id,
                    startup_identifier=snapshot.startup_identifier,
                    retrievals=tuple(item.retrieval for item in snapshot.retrievals),
                )
            if snapshot.recommendation is not None:
                self.save_downstream_recommendation_set(run_id, snapshot.recommendation.recommendation_set)
            for briefing in snapshot.briefings:
                self.save_downstream_briefing(run_id, briefing.briefing)

    def save_downstream_retrievals(
        self,
        run_id: str,
        *,
        startup_identifier: str,
        retrievals: Sequence[Any],
    ) -> None:
        retrieval_artifacts = tuple(build_downstream_retrieval_artifact(retrieval) for retrieval in retrievals)
        self._execute(
            "DELETE FROM downstream_retrievals WHERE run_id = ? AND startup_identifier = ?",
            (run_id, startup_identifier),
        )
        for position, retrieval in enumerate(retrieval_artifacts, start=1):
            self._execute(
                """
                INSERT INTO downstream_retrievals
                (run_id, startup_identifier, corpus_version, retrieval_strategy, position, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    startup_identifier,
                    retrieval.corpus_version,
                    retrieval.retrieval_strategy,
                    position,
                    _dumps(retrieval.payload),
                ),
            )
        self._commit()

    def save_downstream_recommendation_set(self, run_id: str, recommendation_set: Any) -> None:
        recommendation = build_downstream_recommendation_artifact(recommendation_set)
        self._execute(
            "DELETE FROM downstream_recommendations WHERE run_id = ? AND startup_identifier = ?",
            (run_id, recommendation.startup_identifier),
        )
        self._execute(
            """
            INSERT INTO downstream_recommendations
            (
                run_id,
                startup_identifier,
                corpus_version,
                final_nvidia_opportunity_priority,
                ready_for_briefing,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                recommendation.startup_identifier,
                recommendation.corpus_version,
                recommendation.final_nvidia_opportunity_priority,
                int(recommendation.ready_for_briefing),
                _dumps(recommendation.payload),
            ),
        )
        self._commit()

    def save_downstream_briefing(self, run_id: str, briefing: Any) -> None:
        artifact = build_downstream_briefing_artifact(briefing)
        self._execute(
            """
            DELETE FROM downstream_briefings
            WHERE run_id = ? AND startup_identifier = ? AND briefing_type = ?
            """,
            (run_id, artifact.startup_identifier, artifact.briefing_type),
        )
        self._execute(
            """
            INSERT INTO downstream_briefings
            (run_id, startup_identifier, briefing_type, status, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                artifact.startup_identifier,
                artifact.briefing_type,
                artifact.status,
                _dumps(artifact.payload),
            ),
        )
        self._commit()

    def save_nvidia_knowledge_corpus(self, corpus: NVIDIAKnowledgeCorpus) -> None:
        """Persist a validated NVIDIA Knowledge corpus with idempotent upserts."""

        validation = validate_nvidia_knowledge_corpus(corpus)
        if not validation.is_valid:
            raise ValueError(_nvidia_knowledge_validation_error(validation.issues))

        with self._transaction():
            for document in corpus.documents:
                self._execute(
                    """
                    INSERT INTO nvidia_knowledge_documents
                    (
                        schema_version,
                        corpus_version,
                        document_id,
                        title,
                        source_url,
                        source_type,
                        ingested_at,
                        metadata_json,
                        payload_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (corpus_version, document_id)
                    DO UPDATE SET
                        schema_version = excluded.schema_version,
                        title = excluded.title,
                        source_url = excluded.source_url,
                        source_type = excluded.source_type,
                        ingested_at = excluded.ingested_at,
                        metadata_json = excluded.metadata_json,
                        payload_json = excluded.payload_json
                    """,
                    (
                        document.schema_version,
                        document.corpus_version,
                        document.document_id,
                        document.title,
                        document.source_url,
                        document.source_type,
                        document.ingested_at,
                        _dumps(document.metadata),
                        _dumps(document),
                    ),
                )

            for chunk in corpus.chunks:
                self._execute(
                    """
                    INSERT INTO nvidia_knowledge_chunks
                    (
                        schema_version,
                        corpus_version,
                        chunk_id,
                        document_id,
                        chunk_index,
                        topic,
                        text,
                        metadata_json,
                        payload_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (corpus_version, chunk_id)
                    DO UPDATE SET
                        schema_version = excluded.schema_version,
                        document_id = excluded.document_id,
                        chunk_index = excluded.chunk_index,
                        topic = excluded.topic,
                        text = excluded.text,
                        metadata_json = excluded.metadata_json,
                        payload_json = excluded.payload_json
                    """,
                    (
                        chunk.schema_version,
                        chunk.corpus_version,
                        chunk.chunk_id,
                        chunk.document_id,
                        chunk.chunk_index,
                        chunk.topic,
                        chunk.text,
                        _dumps(chunk.metadata),
                        _dumps(chunk),
                    ),
                )

    def load_nvidia_knowledge_corpus(self, corpus_version: str) -> NVIDIAKnowledgeCorpus:
        document_rows = self._execute(
            """
            SELECT payload_json FROM nvidia_knowledge_documents
            WHERE corpus_version = ?
            ORDER BY document_id
            """,
            (corpus_version,),
        ).fetchall()
        if not document_rows:
            raise KeyError(f"NVIDIA Knowledge corpus not found: {corpus_version}")

        chunk_rows = self._execute(
            """
            SELECT payload_json FROM nvidia_knowledge_chunks
            WHERE corpus_version = ?
            ORDER BY document_id, chunk_index, chunk_id
            """,
            (corpus_version,),
        ).fetchall()
        documents = tuple(_nvidia_document_from_payload(row[0]) for row in document_rows)
        chunks = tuple(_nvidia_chunk_from_payload(row[0]) for row in chunk_rows)
        return NVIDIAKnowledgeCorpus(
            schema_version=documents[0].schema_version,
            corpus_version=corpus_version,
            documents=documents,
            chunks=chunks,
        )

    def save_pipeline_result(
        self,
        run_id: str,
        result: ScrapingPipelineResult,
        *,
        raw_discovery_results: Sequence[RawDiscoveryResult] = (),
    ) -> None:
        raw_results_to_save = tuple(raw_discovery_results) if raw_discovery_results else result.raw_results
        candidate_names = {candidate_result_key(candidate): candidate.name for candidate in result.candidates}
        profile_names = {profile_result_key(profile): profile.company_name.value for profile in result.profiles}
        with self._transaction():
            self._execute(
                "UPDATE pipeline_runs SET search_params_json = ? WHERE run_id = ?",
                (_dumps(result.search_params), run_id),
            )
            self.save_search_plan(run_id, result.search_plan)
            self.save_raw_discovery_results(run_id, raw_results_to_save)
            self.save_candidate_startups(run_id, result.candidates)
            self.save_collected_pages(
                run_id,
                result.collected_pages_by_candidate,
                candidate_names=candidate_names,
            )
            self.save_startup_profiles(run_id, result.profiles)
            self.save_field_evidences(
                run_id,
                result.evidence_groups_by_profile,
                profile_names=profile_names,
            )
            self.save_collection_quality(run_id, result.quality_summary)

    def load_run(self, run_id: str) -> StoredPipelineRun:
        run_row = self._execute(
            "SELECT created_at, search_params_json FROM pipeline_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if run_row is None:
            raise KeyError(f"Pipeline run not found: {run_id}")

        return StoredPipelineRun(
            run_id=run_id,
            created_at=run_row[0],
            search_params=_loads_optional(run_row[1]),
            search_plan_items=self._payloads(
                "search_plan_items",
                run_id,
                columns=("priority", "term", "target_source", "scope"),
                order_by="priority",
            ),
            raw_discovery_results=self._payloads(
                "raw_discovery_results",
                run_id,
                columns=("position", "title", "url", "source_name"),
                order_by="position",
            ),
            candidate_startups=self._payloads(
                "candidate_startups",
                run_id,
                columns=("candidate_key", "name", "normalized_name", "primary_url"),
                order_by="name",
            ),
            collected_pages=self._payloads(
                "collected_pages",
                run_id,
                columns=("candidate_key", "candidate_name", "url", "status_code", "is_error"),
                order_by="id",
            ),
            startup_profiles=self._payloads(
                "startup_profiles",
                run_id,
                columns=("profile_key", "company_name", "schema_version"),
                order_by="company_name",
            ),
            field_evidences=self._payloads(
                "field_evidences",
                run_id,
                columns=("profile_key", "company_name", "field_name", "evidence_url"),
                order_by="id",
            ),
            collection_quality_summaries=self._payloads(
                "collection_quality_summaries",
                run_id,
                columns=("ready_for_evaluation",),
                order_by="id",
            ),
            ai_native_assessments=self._payloads(
                "ai_native_assessments",
                run_id,
                columns=("company_name", "classification", "ready_for_recommendation"),
                order_by="company_name",
            ),
        )

    def load_downstream_artifacts(
        self,
        run_id: str,
        *,
        startup_identifier: str,
    ) -> StoredDownstreamArtifacts:
        return StoredDownstreamArtifacts(
            run_id=run_id,
            startup_identifier=startup_identifier,
            retrievals=self._downstream_payloads(
                "downstream_retrievals",
                run_id,
                startup_identifier=startup_identifier,
                order_by="position",
            ),
            recommendation_sets=self._downstream_payloads(
                "downstream_recommendations",
                run_id,
                startup_identifier=startup_identifier,
                order_by="id",
            ),
            briefings=self._downstream_payloads(
                "downstream_briefings",
                run_id,
                startup_identifier=startup_identifier,
                order_by="id",
            ),
        )

    def _payloads(
        self,
        table: str,
        run_id: str,
        *,
        columns: tuple[str, ...],
        order_by: str,
    ) -> tuple[dict[str, Any], ...]:
        selected_columns = ", ".join((*columns, "payload_json"))
        rows = self._execute(
            f"SELECT {selected_columns} FROM {table} WHERE run_id = ? ORDER BY {order_by}",
            (run_id,),
        ).fetchall()
        payload_index = len(columns)
        loaded_payloads: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row[payload_index])
            for index, column in enumerate(columns):
                payload[column] = _column_value(column, row[index])
            loaded_payloads.append(payload)
        return tuple(loaded_payloads)

    def _downstream_payloads(
        self,
        table: str,
        run_id: str,
        *,
        startup_identifier: str,
        order_by: str,
    ) -> tuple[dict[str, Any], ...]:
        rows = self._execute(
            f"""
            SELECT payload_json FROM {table}
            WHERE run_id = ? AND startup_identifier = ?
            ORDER BY {order_by}
            """,
            (run_id, startup_identifier),
        ).fetchall()
        return tuple(json.loads(row[0]) for row in rows)

    def _execute(self, sql: str, params: tuple[Any, ...]) -> Any:
        if self._postgres:
            sql = sql.replace("?", "%s")
        return self.connection.execute(sql, params)

    def _commit(self) -> None:
        if self._transaction_depth == 0:
            self.connection.commit()

    @contextmanager
    def _transaction(self) -> Any:
        nested = self._transaction_depth > 0
        self._transaction_depth += 1
        try:
            yield
        except Exception:
            if not nested:
                self.connection.rollback()
            raise
        else:
            if not nested:
                self.connection.commit()
        finally:
            self._transaction_depth -= 1


def sqlite_repository(path: str | Path = ":memory:") -> SqlPipelineRepository:
    connection = sqlite3.connect(path)
    repository = SqlPipelineRepository(connection)
    repository.initialize_schema()
    return repository


def postgres_repository_from_env() -> SqlPipelineRepository:
    """Create a Postgres repository from ``DATABASE_URL`` using optional psycopg."""

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is required for Postgres persistence")
    try:
        import psycopg  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise RuntimeError("Install psycopg to use Postgres persistence") from exc

    repository = SqlPipelineRepository(psycopg.connect(database_url))
    repository.initialize_schema()
    return repository


def _schema_statements(id_column_type: str) -> tuple[str, ...]:
    run_fk = "REFERENCES pipeline_runs(run_id) ON DELETE CASCADE"
    return (
        """
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            run_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            search_params_json TEXT
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS search_plan_items (
            id {id_column_type},
            run_id TEXT NOT NULL {run_fk},
            priority INTEGER NOT NULL,
            term TEXT NOT NULL,
            target_source TEXT NOT NULL,
            scope TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS raw_discovery_results (
            id {id_column_type},
            run_id TEXT NOT NULL {run_fk},
            position INTEGER NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            source_name TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS candidate_startups (
            id {id_column_type},
            run_id TEXT NOT NULL {run_fk},
            candidate_key TEXT NOT NULL,
            name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            primary_url TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS collected_pages (
            id {id_column_type},
            run_id TEXT NOT NULL {run_fk},
            candidate_key TEXT NOT NULL,
            candidate_name TEXT NOT NULL,
            url TEXT NOT NULL,
            status_code INTEGER,
            is_error INTEGER NOT NULL,
            payload_json TEXT NOT NULL
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS startup_profiles (
            id {id_column_type},
            run_id TEXT NOT NULL {run_fk},
            profile_key TEXT NOT NULL,
            company_name TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS field_evidences (
            id {id_column_type},
            run_id TEXT NOT NULL {run_fk},
            profile_key TEXT NOT NULL,
            company_name TEXT NOT NULL,
            field_name TEXT NOT NULL,
            evidence_url TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS collection_quality_summaries (
            id {id_column_type},
            run_id TEXT NOT NULL {run_fk},
            ready_for_evaluation INTEGER NOT NULL,
            payload_json TEXT NOT NULL
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS ai_native_assessments (
            id {id_column_type},
            run_id TEXT NOT NULL {run_fk},
            company_name TEXT NOT NULL,
            classification TEXT NOT NULL,
            ready_for_recommendation INTEGER NOT NULL,
            payload_json TEXT NOT NULL
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS downstream_retrievals (
            id {id_column_type},
            run_id TEXT NOT NULL {run_fk},
            startup_identifier TEXT NOT NULL,
            corpus_version TEXT NOT NULL,
            retrieval_strategy TEXT NOT NULL,
            position INTEGER NOT NULL,
            payload_json TEXT NOT NULL
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS downstream_recommendations (
            id {id_column_type},
            run_id TEXT NOT NULL {run_fk},
            startup_identifier TEXT NOT NULL,
            corpus_version TEXT NOT NULL,
            final_nvidia_opportunity_priority TEXT NOT NULL,
            ready_for_briefing INTEGER NOT NULL,
            payload_json TEXT NOT NULL
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS downstream_briefings (
            id {id_column_type},
            run_id TEXT NOT NULL {run_fk},
            startup_identifier TEXT NOT NULL,
            briefing_type TEXT NOT NULL,
            status TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_search_plan_items_run_id ON search_plan_items(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_raw_discovery_results_run_id ON raw_discovery_results(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_candidate_startups_run_id ON candidate_startups(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_collected_pages_run_id ON collected_pages(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_collected_pages_run_candidate_key ON collected_pages(run_id, candidate_key)",
        "CREATE INDEX IF NOT EXISTS idx_startup_profiles_run_id ON startup_profiles(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_startup_profiles_run_profile_key ON startup_profiles(run_id, profile_key)",
        "CREATE INDEX IF NOT EXISTS idx_field_evidences_run_id ON field_evidences(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_field_evidences_run_profile_key ON field_evidences(run_id, profile_key)",
        "CREATE INDEX IF NOT EXISTS idx_collection_quality_summaries_run_id ON collection_quality_summaries(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_ai_native_assessments_run_id ON ai_native_assessments(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_downstream_retrievals_run_startup ON downstream_retrievals(run_id, startup_identifier)",
        "CREATE INDEX IF NOT EXISTS idx_downstream_recommendations_run_startup ON downstream_recommendations(run_id, startup_identifier)",
        "CREATE INDEX IF NOT EXISTS idx_downstream_briefings_run_startup ON downstream_briefings(run_id, startup_identifier)",
    )


def _nvidia_knowledge_table_statements(id_column_type: str) -> tuple[str, ...]:
    return (
        f"""
        CREATE TABLE IF NOT EXISTS nvidia_knowledge_documents (
            id {id_column_type},
            schema_version TEXT NOT NULL,
            corpus_version TEXT NOT NULL,
            document_id TEXT NOT NULL,
            title TEXT NOT NULL,
            source_url TEXT NOT NULL,
            source_type TEXT NOT NULL,
            ingested_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            UNIQUE (corpus_version, document_id)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS nvidia_knowledge_chunks (
            id {id_column_type},
            schema_version TEXT NOT NULL,
            corpus_version TEXT NOT NULL,
            chunk_id TEXT NOT NULL,
            document_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            topic TEXT NOT NULL,
            text TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            UNIQUE (corpus_version, chunk_id),
            FOREIGN KEY (corpus_version, document_id)
                REFERENCES nvidia_knowledge_documents(corpus_version, document_id)
                ON DELETE CASCADE
        )
        """,
    )


def _nvidia_knowledge_index_statements() -> tuple[str, ...]:
    return (
        "CREATE INDEX IF NOT EXISTS idx_nvidia_knowledge_documents_corpus ON nvidia_knowledge_documents(corpus_version)",
        "CREATE INDEX IF NOT EXISTS idx_nvidia_knowledge_chunks_corpus_topic ON nvidia_knowledge_chunks(corpus_version, topic)",
    )


def _nvidia_knowledge_schema_statements(id_column_type: str) -> tuple[str, ...]:
    return (
        *_nvidia_knowledge_table_statements(id_column_type),
        *_nvidia_knowledge_index_statements(),
    )


def _pgvector_schema_statements(id_column_type: str) -> tuple[str, ...]:
    return (
        *_nvidia_knowledge_table_statements(id_column_type),
        f"""
        CREATE TABLE IF NOT EXISTS nvidia_chunk_embeddings (
            id {id_column_type},
            corpus_version TEXT NOT NULL,
            chunk_id TEXT NOT NULL,
            embedding_provider TEXT NOT NULL,
            embedding_model TEXT NOT NULL,
            embedding_version TEXT NOT NULL,
            vector_dimension INTEGER NOT NULL,
            distance_metric TEXT NOT NULL,
            index_parameters_json TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            embedding vector NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK (vector_dims(embedding) = vector_dimension),
            UNIQUE (
                corpus_version,
                chunk_id,
                embedding_provider,
                embedding_model,
                embedding_version,
                vector_dimension
            ),
            FOREIGN KEY (corpus_version, chunk_id)
                REFERENCES nvidia_knowledge_chunks(corpus_version, chunk_id)
                ON DELETE CASCADE
        )
        """,
        *_nvidia_knowledge_index_statements(),
        "CREATE INDEX IF NOT EXISTS idx_nvidia_chunk_embeddings_lookup ON nvidia_chunk_embeddings(corpus_version, embedding_model, embedding_version, vector_dimension)",
        "CREATE INDEX IF NOT EXISTS idx_nvidia_chunk_embeddings_chunk ON nvidia_chunk_embeddings(corpus_version, chunk_id)",
    )


SQLITE_SCHEMA_STATEMENTS = (
    *_schema_statements("INTEGER PRIMARY KEY AUTOINCREMENT"),
    *_nvidia_knowledge_schema_statements("INTEGER PRIMARY KEY AUTOINCREMENT"),
)
POSTGRES_SCHEMA_STATEMENTS = (
    "CREATE EXTENSION IF NOT EXISTS vector",
    *_schema_statements("BIGSERIAL PRIMARY KEY"),
    *_pgvector_schema_statements("BIGSERIAL PRIMARY KEY"),
)


def _dumps(value: Any) -> str:
    return json.dumps(_to_jsonable(value), ensure_ascii=False, sort_keys=True)


def _loads_optional(value: str | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return json.loads(value)


def _column_value(column: str, value: Any) -> Any:
    if column in {"is_error", "ready_for_evaluation", "ready_for_recommendation"}:
        return bool(value)
    return value


def _lookup_key(keys: Mapping[str, str] | None, name: str) -> str:
    if keys is None:
        return name
    return keys.get(name, name)


def _downstream_startup_identifier(
    *,
    recommendation_set: Any,
    executive_briefing: Any,
    human_review_briefing: Any,
    briefing_narrative: Any = None,
) -> str:
    return downstream_startup_identifier(
        recommendation_set=recommendation_set,
        executive_briefing=executive_briefing,
        human_review_briefing=human_review_briefing,
        briefing_narrative=briefing_narrative,
    )


def _retrieval_strategy(retrieval: Any) -> str:
    return downstream_retrieval_strategy(retrieval)


def _briefing_type(briefing: Any) -> str:
    return downstream_briefing_type(briefing)


def _briefing_status(briefing: Any) -> str:
    return downstream_briefing_status(briefing)


def _briefing_payload(briefing: Any) -> dict[str, object]:
    return downstream_briefing_payload(briefing)


def _nvidia_knowledge_validation_error(issues: Sequence[Any]) -> str:
    reasons = ", ".join(f"{issue.document_id}:{issue.reason}" for issue in issues)
    return f"invalid_nvidia_knowledge_corpus:{reasons}"


def _nvidia_document_from_payload(payload_json: object) -> NVIDIAKnowledgeDocument:
    payload = _loads_mapping(payload_json)
    return NVIDIAKnowledgeDocument(
        schema_version=str(payload["schema_version"]),
        corpus_version=str(payload["corpus_version"]),
        document_id=str(payload["document_id"]),
        title=str(payload["title"]),
        source_url=str(payload["source_url"]),
        source_type=str(payload["source_type"]),
        ingested_at=str(payload["ingested_at"]),
        metadata=dict(payload.get("metadata", {})),
    )


def _nvidia_chunk_from_payload(payload_json: object) -> NVIDIAKnowledgeChunk:
    payload = _loads_mapping(payload_json)
    return NVIDIAKnowledgeChunk(
        schema_version=str(payload["schema_version"]),
        corpus_version=str(payload["corpus_version"]),
        chunk_id=str(payload["chunk_id"]),
        document_id=str(payload["document_id"]),
        chunk_index=int(payload["chunk_index"]),
        topic=str(payload["topic"]),
        text=str(payload["text"]),
        metadata=dict(payload.get("metadata", {})),
    )


def _loads_mapping(payload_json: object) -> dict[str, object]:
    if isinstance(payload_json, str):
        return dict(json.loads(payload_json))
    return dict(payload_json)  # type: ignore[arg-type]


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _to_jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item) for item in value]
    return value


def _new_run_id() -> str:
    now = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"run-{now}-{uuid4().hex[:8]}"


def _format_time(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()
