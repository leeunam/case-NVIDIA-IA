"""Relational persistence for scraping pipeline runs.

The repository stores auditable pipeline artifacts in normalized run tables,
while keeping each payload as JSON to avoid premature schema churn during the
walking skeleton phase. It accepts a DB-API connection, so tests run on SQLite
and development can use Postgres through the Docker Compose service.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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
from nvidia_startup_intel.evidence import FieldEvidenceGroup
from nvidia_startup_intel.page_collection import PageCollectionResult
from nvidia_startup_intel.pipeline import ScrapingPipelineResult
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


class SqlPipelineRepository:
    """Persist and load scraping pipeline runs using a DB-API connection."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection
        self._postgres = "psycopg" in type(connection).__module__

    def initialize_schema(self) -> None:
        statements = POSTGRES_SCHEMA_STATEMENTS if self._postgres else SQLITE_SCHEMA_STATEMENTS
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
        self.connection.commit()
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
        self.connection.commit()

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
        self.connection.commit()

    def save_candidate_startups(self, run_id: str, candidates: Sequence[CandidateStartup]) -> None:
        self._execute("DELETE FROM candidate_startups WHERE run_id = ?", (run_id,))
        for candidate in candidates:
            self._execute(
                """
                INSERT INTO candidate_startups
                (run_id, name, normalized_name, primary_url, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, candidate.name, candidate.normalized_name, candidate.primary_url, _dumps(candidate)),
            )
        self.connection.commit()

    def save_collected_pages(self, run_id: str, results_by_candidate: Mapping[str, PageCollectionResult]) -> None:
        self._execute("DELETE FROM collected_pages WHERE run_id = ?", (run_id,))
        for candidate_name, result in results_by_candidate.items():
            for page in result.pages:
                self._execute(
                    """
                    INSERT INTO collected_pages
                    (run_id, candidate_name, url, status_code, payload_json, is_error)
                    VALUES (?, ?, ?, ?, ?, 0)
                    """,
                    (run_id, candidate_name, page.url, page.status_code, _dumps(page)),
                )
            for error in result.errors:
                self._execute(
                    """
                    INSERT INTO collected_pages
                    (run_id, candidate_name, url, status_code, payload_json, is_error)
                    VALUES (?, ?, ?, ?, ?, 1)
                    """,
                    (run_id, candidate_name, error.url, error.status_code, _dumps(error)),
                )
        self.connection.commit()

    def save_startup_profiles(self, run_id: str, profiles: Sequence[StartupProfile]) -> None:
        self._execute("DELETE FROM startup_profiles WHERE run_id = ?", (run_id,))
        for profile in profiles:
            self._execute(
                """
                INSERT INTO startup_profiles
                (run_id, company_name, schema_version, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, profile.company_name.value, profile.schema_version, _dumps(profile)),
            )
        self.connection.commit()

    def save_field_evidences(
        self,
        run_id: str,
        evidences_by_profile: Mapping[str, Sequence[FieldEvidenceGroup]],
    ) -> None:
        self._execute("DELETE FROM field_evidences WHERE run_id = ?", (run_id,))
        for company_name, groups in evidences_by_profile.items():
            for group in groups:
                for evidence in group.evidences:
                    self._execute(
                        """
                        INSERT INTO field_evidences
                        (run_id, company_name, field_name, evidence_url, payload_json)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (run_id, company_name, group.field_name, evidence.url, _dumps({"group": group, "evidence": evidence})),
                    )
        self.connection.commit()

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
        self.connection.commit()

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
        self.connection.commit()

    def save_pipeline_result(
        self,
        run_id: str,
        result: ScrapingPipelineResult,
        *,
        raw_discovery_results: Sequence[RawDiscoveryResult] = (),
    ) -> None:
        self._execute(
            "UPDATE pipeline_runs SET search_params_json = ? WHERE run_id = ?",
            (_dumps(result.search_params), run_id),
        )
        self.save_search_plan(run_id, result.search_plan)
        self.save_raw_discovery_results(run_id, raw_discovery_results)
        self.save_candidate_startups(run_id, result.candidates)
        self.save_collected_pages(run_id, result.collected_pages_by_candidate)
        self.save_startup_profiles(run_id, result.profiles)
        self.save_field_evidences(run_id, result.evidence_groups_by_profile)
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
            search_plan_items=self._payloads("search_plan_items", run_id, order_by="priority"),
            raw_discovery_results=self._payloads("raw_discovery_results", run_id, order_by="position"),
            candidate_startups=self._payloads("candidate_startups", run_id, order_by="name"),
            collected_pages=self._payloads("collected_pages", run_id, order_by="id"),
            startup_profiles=self._payloads("startup_profiles", run_id, order_by="company_name"),
            field_evidences=self._payloads("field_evidences", run_id, order_by="id"),
            collection_quality_summaries=self._payloads("collection_quality_summaries", run_id, order_by="id"),
            ai_native_assessments=self._payloads("ai_native_assessments", run_id, order_by="company_name"),
        )

    def _payloads(self, table: str, run_id: str, *, order_by: str) -> tuple[dict[str, Any], ...]:
        rows = self._execute(
            f"SELECT payload_json FROM {table} WHERE run_id = ? ORDER BY {order_by}",
            (run_id,),
        ).fetchall()
        return tuple(json.loads(row[0]) for row in rows)

    def _execute(self, sql: str, params: tuple[Any, ...]) -> Any:
        if self._postgres:
            sql = sql.replace("?", "%s")
        return self.connection.execute(sql, params)


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


SQLITE_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS pipeline_runs (
        run_id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        search_params_json TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS search_plan_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        priority INTEGER NOT NULL,
        term TEXT NOT NULL,
        target_source TEXT NOT NULL,
        scope TEXT NOT NULL,
        payload_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS raw_discovery_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        position INTEGER NOT NULL,
        title TEXT NOT NULL,
        url TEXT NOT NULL,
        source_name TEXT NOT NULL,
        payload_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS candidate_startups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        name TEXT NOT NULL,
        normalized_name TEXT NOT NULL,
        primary_url TEXT NOT NULL,
        payload_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS collected_pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        candidate_name TEXT NOT NULL,
        url TEXT NOT NULL,
        status_code INTEGER,
        is_error INTEGER NOT NULL,
        payload_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS startup_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        company_name TEXT NOT NULL,
        schema_version TEXT NOT NULL,
        payload_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS field_evidences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        company_name TEXT NOT NULL,
        field_name TEXT NOT NULL,
        evidence_url TEXT NOT NULL,
        payload_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS collection_quality_summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        ready_for_evaluation INTEGER NOT NULL,
        payload_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_native_assessments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        company_name TEXT NOT NULL,
        classification TEXT NOT NULL,
        ready_for_recommendation INTEGER NOT NULL,
        payload_json TEXT NOT NULL
    )
    """,
)

POSTGRES_SCHEMA_STATEMENTS = tuple(
    statement.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
    for statement in SQLITE_SCHEMA_STATEMENTS
)


def _dumps(value: Any) -> str:
    return json.dumps(_to_jsonable(value), ensure_ascii=False, sort_keys=True)


def _loads_optional(value: str | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return json.loads(value)


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
