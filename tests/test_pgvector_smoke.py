from __future__ import annotations

import json
from pathlib import Path

from nvidia_startup_intel.pgvector_smoke import run_pgvector_smoke


def test_pgvector_smoke_applies_project_schema_and_round_trips_fixture() -> None:
    connection = _SmokeConnection()

    result = run_pgvector_smoke(
        database_url="postgresql://user:secret@localhost:5432/db",
        connect=lambda _database_url: connection,
    )

    assert result.schema_path == Path("db/schema.sql")
    assert result.corpus_version == "official-nvidia-fixture.v1"
    assert result.vector_extension_available is True
    assert result.persisted_documents > 0
    assert result.persisted_chunks > 0
    assert result.persisted_embeddings == result.persisted_chunks
    assert result.retrieved_chunk_id == "nvidia-nim-developers:0"
    assert result.retrieval_strategy == "vector_semantic"

    executed_sql = "\n".join(connection.sql_statements).lower()
    assert "create extension if not exists vector" in executed_sql
    assert "select exists" in executed_sql


def test_pgvector_smoke_can_use_configured_sentence_transformers_embeddings() -> None:
    connection = _SmokeConnection()

    result = run_pgvector_smoke(
        database_url="postgresql://user:secret@localhost:5432/db",
        connect=lambda _database_url: connection,
        embedding_env={
            "NVIDIA_STARTUP_INTEL_EMBEDDING_PROVIDER": "sentence-transformers",
            "NVIDIA_STARTUP_INTEL_EMBEDDING_MODEL": "intfloat/multilingual-e5-base",
            "NVIDIA_STARTUP_INTEL_EMBEDDING_MODEL_VERSION": "local-snapshot",
        },
        embedding_model_loader=lambda _model_name: _SentenceTransformerLikeModel(dimension=2),
    )

    metadata = json.loads(connection.embedding_metadata_json)
    assert result.persisted_embeddings == result.persisted_chunks
    assert metadata["embedding_provider"] == "sentence_transformers"
    assert metadata["embedding_model"] == "intfloat/multilingual-e5-base"
    assert metadata["embedding_version"] == "local-snapshot"
    assert metadata["dimension"] == 2


class _SmokeConnection:
    def __init__(self) -> None:
        self.sql_statements: list[str] = []
        self.document_payloads_by_id: dict[str, str] = {}
        self.chunk_payload_json = ""
        self.index_parameters_json = ""
        self.embedding_metadata_json = ""

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> "_SmokeCursor":
        self.sql_statements.append(sql)
        normalized_sql = " ".join(sql.lower().split())
        if "select exists" in normalized_sql and "pg_extension" in normalized_sql:
            return _SmokeCursor(((True,),))
        if "insert into nvidia_knowledge_documents" in normalized_sql:
            payload_json = str(params[7])
            payload = json.loads(payload_json)
            self.document_payloads_by_id[str(payload["document_id"])] = payload_json
        elif "insert into nvidia_knowledge_chunks" in normalized_sql and not self.chunk_payload_json:
            self.chunk_payload_json = str(params[7])
        elif "insert into nvidia_chunk_embeddings" in normalized_sql:
            self.index_parameters_json = str(params[7])
            self.embedding_metadata_json = str(params[8])
        elif "from nvidia_chunk_embeddings" in normalized_sql:
            chunk_payload = json.loads(self.chunk_payload_json)
            document_payload_json = self.document_payloads_by_id[str(chunk_payload["document_id"])]
            return _SmokeCursor(
                (
                    (
                        document_payload_json,
                        self.chunk_payload_json,
                        0.91,
                        self.index_parameters_json,
                        self.embedding_metadata_json,
                    ),
                )
            )
        return _SmokeCursor(())

    def commit(self) -> None:
        pass

    def close(self) -> None:
        pass


class _SmokeCursor:
    def __init__(self, rows: tuple[tuple[object, ...], ...]) -> None:
        self._rows = rows

    def fetchone(self) -> tuple[object, ...] | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> tuple[tuple[object, ...], ...]:
        return self._rows


class _SentenceTransformerLikeModel:
    def __init__(self, *, dimension: int) -> None:
        self._dimension = dimension

    def get_sentence_embedding_dimension(self) -> int:
        return self._dimension

    def encode(self, texts: list[str], **_: object) -> list[list[float]]:
        vectors: list[list[float]] = []
        for index, _text in enumerate(texts):
            vectors.append([1.0 if index == component else 0.0 for component in range(self._dimension)])
        return vectors


def test_pgvector_smoke_command_is_documented() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "PYTHONPATH=src python -m nvidia_startup_intel.pgvector_smoke" in readme
    assert "NVIDIA_STARTUP_INTEL_RUN_PGVECTOR_SMOKE=1" in readme


def test_pgvector_smoke_result_is_json_serializable() -> None:
    connection = _SmokeConnection()

    result = run_pgvector_smoke(
        database_url="postgresql://user:secret@localhost:5432/db",
        connect=lambda _database_url: connection,
    )

    payload = result.to_dict()
    json.dumps(payload)
    assert payload["retrieved_document_id"] == "nvidia-nim-developers"
