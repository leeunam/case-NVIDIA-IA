"""Optional real Postgres/pgvector smoke validation.

This module is intentionally outside the default validation path. It proves
that the project schema and PgvectorNVIDIAEmbeddingStore can round-trip the
local official NVIDIA corpus through a real pgvector database.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
import argparse
import os
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from nvidia_startup_intel.nvidia_embeddings import (
    DeterministicFakeEmbeddingClient,
    EmbeddingClient,
    build_nvidia_embedding_index,
    embedding_client_from_config,
    embedding_provider_config_from_env,
)
from nvidia_startup_intel.nvidia_knowledge import load_nvidia_knowledge_corpus
from nvidia_startup_intel.nvidia_pgvector import PgvectorNVIDIAEmbeddingStore


DEFAULT_DATABASE_URL = (
    "postgresql://nvidia_startup_intel:nvidia_startup_intel"
    "@localhost:5432/nvidia_startup_intel"
)
DEFAULT_SCHEMA_PATH = Path("db/schema.sql")
DEFAULT_CORPUS_PATH = Path("tests/fixtures/nvidia_knowledge_official_fixture.json")
DEFAULT_RUN_ID = "run-pgvector-smoke"


class PgvectorSmokeError(RuntimeError):
    """Actionable failure for the optional pgvector smoke path."""


@dataclass(frozen=True)
class PgvectorSmokeResult:
    schema_path: Path
    corpus_path: Path
    corpus_version: str
    vector_extension_available: bool
    persisted_documents: int
    persisted_chunks: int
    persisted_embeddings: int
    retrieved_document_id: str
    retrieved_chunk_id: str
    retrieval_strategy: str
    vector_score: float

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["schema_path"] = str(self.schema_path)
        payload["corpus_path"] = str(self.corpus_path)
        return payload


def run_pgvector_smoke(
    *,
    database_url: str | None = None,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    corpus_path: Path = DEFAULT_CORPUS_PATH,
    connect: Callable[[str], Any] | None = None,
    embedding_client: EmbeddingClient | None = None,
    embedding_env: Mapping[str, str] | None = None,
    embedding_model_loader: Callable[[str], object] | None = None,
) -> PgvectorSmokeResult:
    """Apply the project pgvector schema and round-trip fixture embeddings."""

    resolved_database_url = database_url or _database_url_from_env()
    connection = _connect(resolved_database_url, connect)
    try:
        _apply_project_schema(connection, schema_path)
        vector_extension_available = _validate_vector_extension(connection)
        corpus = load_nvidia_knowledge_corpus(corpus_path)
        resolved_embedding_client = embedding_client or _embedding_client_from_env_or_fake(
            embedding_env=embedding_env,
            embedding_model_loader=embedding_model_loader,
        )
        embedding_index = build_nvidia_embedding_index(corpus, resolved_embedding_client)

        store = PgvectorNVIDIAEmbeddingStore(connection)
        try:
            store.save_embedding_index(corpus, embedding_index)
        except Exception as exc:  # pragma: no cover - exercised by optional real smoke
            raise PgvectorSmokeError(
                "Optional pgvector smoke failed while persisting the official NVIDIA "
                "corpus fixture. Check that db/schema.sql was applied to a pgvector "
                f"Postgres database. Original error: {exc}"
            ) from exc

        try:
            retrieval = store.retrieve_by_vector(
                resolved_embedding_client,
                run_id=DEFAULT_RUN_ID,
                corpus_version=corpus.corpus_version,
                gap_type="model_serving",
                description="Need lower latency inference deployment.",
                startup_signals=("self-hosted inference",),
                top_k=1,
            )
        except Exception as exc:  # pragma: no cover - exercised by optional real smoke
            raise PgvectorSmokeError(
                "Optional pgvector smoke failed while retrieving by vector similarity. "
                "Check the pgvector extension, embedding column type and vector_dimension "
                f"constraint. Original error: {exc}"
            ) from exc

        if not retrieval.results:
            raise PgvectorSmokeError(
                "Optional pgvector smoke persisted embeddings but retrieved no NVIDIA "
                "Knowledge chunks by vector similarity. Check fixture embeddings and "
                "the nvidia_chunk_embeddings rows."
            )

        first_result = retrieval.results[0]
        return PgvectorSmokeResult(
            schema_path=schema_path,
            corpus_path=corpus_path,
            corpus_version=corpus.corpus_version,
            vector_extension_available=vector_extension_available,
            persisted_documents=len(corpus.documents),
            persisted_chunks=len(corpus.chunks),
            persisted_embeddings=len(embedding_index.chunk_embeddings),
            retrieved_document_id=first_result.citation.document_id,
            retrieved_chunk_id=first_result.chunk.chunk_id,
            retrieval_strategy=first_result.retrieval_strategy,
            vector_score=first_result.vector_score,
        )
    finally:
        close = getattr(connection, "close", None)
        if callable(close):
            close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run optional real Postgres/pgvector smoke.")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    args = parser.parse_args(argv)

    try:
        result = run_pgvector_smoke(
            database_url=args.database_url,
            schema_path=args.schema,
            corpus_path=args.corpus,
        )
    except PgvectorSmokeError as exc:
        print(f"OPTIONAL PGVECTOR SMOKE FAILED: {exc}", file=sys.stderr)
        return 2

    print("OPTIONAL PGVECTOR SMOKE PASSED")
    for key, value in result.to_dict().items():
        print(f"{key}: {value}")
    return 0


def _database_url_from_env() -> str:
    return (
        os.environ.get("NVIDIA_STARTUP_INTEL_PGVECTOR_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or DEFAULT_DATABASE_URL
    )


def _embedding_client_from_env_or_fake(
    *,
    embedding_env: Mapping[str, str] | None,
    embedding_model_loader: Callable[[str], object] | None,
) -> EmbeddingClient:
    source = os.environ if embedding_env is None else embedding_env
    if source.get("NVIDIA_STARTUP_INTEL_EMBEDDING_PROVIDER", "").strip():
        return embedding_client_from_config(
            embedding_provider_config_from_env(source),
            model_loader=embedding_model_loader,
        )
    return DeterministicFakeEmbeddingClient(dimension=6)


def _connect(database_url: str, connect: Callable[[str], Any] | None) -> Any:
    if connect is not None:
        return connect(database_url)

    try:
        import psycopg  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - depends on optional dependency
        raise PgvectorSmokeError(
            "Optional pgvector smoke requires psycopg in the active Python environment. "
            "Install psycopg to run this smoke; the default local suite does not require it."
        ) from exc

    try:
        return psycopg.connect(database_url)
    except Exception as exc:  # pragma: no cover - depends on local Postgres
        raise PgvectorSmokeError(
            "Could not connect to optional pgvector Postgres at "
            f"{_redact_database_url(database_url)}. Start it with "
            "`docker compose up -d postgres` or set "
            "NVIDIA_STARTUP_INTEL_PGVECTOR_DATABASE_URL. "
            f"Original error: {exc}"
        ) from exc


def _apply_project_schema(connection: Any, schema_path: Path) -> None:
    try:
        schema_sql = schema_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PgvectorSmokeError(f"Could not read pgvector schema file {schema_path}: {exc}") from exc

    normalized_schema = " ".join(schema_sql.lower().split())
    if "create extension if not exists vector" not in normalized_schema:
        raise PgvectorSmokeError(
            f"{schema_path} must include CREATE EXTENSION IF NOT EXISTS vector "
            "for the optional pgvector smoke."
        )

    try:
        for statement in _schema_statements(schema_sql):
            connection.execute(statement)
        connection.commit()
    except Exception as exc:  # pragma: no cover - exercised by optional real smoke
        raise PgvectorSmokeError(
            f"Failed to apply project schema from {schema_path} to pgvector Postgres. "
            "Check that the database user can create extensions and tables. "
            f"Original error: {exc}"
        ) from exc


def _validate_vector_extension(connection: Any) -> bool:
    try:
        cursor = connection.execute(
            "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')"
        )
        row = cursor.fetchone()
    except Exception as exc:  # pragma: no cover - exercised by optional real smoke
        raise PgvectorSmokeError(
            "Failed to validate pgvector extension after applying db/schema.sql. "
            f"Original error: {exc}"
        ) from exc

    available = bool(row and row[0])
    if not available:
        raise PgvectorSmokeError(
            "db/schema.sql ran, but pg_extension does not contain vector. "
            "Check the Docker image is pgvector/pgvector:pg16 and that the "
            "database user can create extensions."
        )
    return available


def _schema_statements(schema_sql: str) -> tuple[str, ...]:
    return tuple(statement.strip() for statement in schema_sql.split(";") if statement.strip())


def _redact_database_url(database_url: str) -> str:
    parts = urlsplit(database_url)
    if not parts.password:
        return database_url
    username = parts.username or ""
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    netloc = f"{username}:***@{host}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


if __name__ == "__main__":
    raise SystemExit(main())
