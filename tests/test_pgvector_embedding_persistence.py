from dataclasses import dataclass
import json
from pathlib import Path
import unittest

from nvidia_startup_intel.nvidia_embeddings import (
    DeterministicFakeEmbeddingClient,
    build_nvidia_embedding_index,
)
from nvidia_startup_intel.nvidia_knowledge import (
    load_nvidia_knowledge_corpus,
    nvidia_knowledge_corpus_to_dict,
)
from nvidia_startup_intel.nvidia_pgvector import PgvectorNVIDIAEmbeddingStore


class PgvectorEmbeddingPersistenceTests(unittest.TestCase):
    def test_postgres_schema_declares_pgvector_embedding_persistence_without_approximate_indexes(self) -> None:
        schema = Path("db/schema.sql").read_text(encoding="utf-8")
        normalized_schema = " ".join(schema.lower().split())

        self.assertIn("create extension if not exists vector", normalized_schema)
        self.assertIn("create table if not exists nvidia_knowledge_documents", normalized_schema)
        self.assertIn("create table if not exists nvidia_knowledge_chunks", normalized_schema)
        self.assertIn("create table if not exists nvidia_chunk_embeddings", normalized_schema)
        self.assertIn("embedding vector not null", normalized_schema)
        self.assertIn("vector_dimension integer not null", normalized_schema)
        self.assertIn("embedding_model text not null", normalized_schema)
        self.assertIn("embedding_version text not null", normalized_schema)
        self.assertIn("index_parameters_json text not null", normalized_schema)
        self.assertIn("metadata_json text not null", normalized_schema)
        self.assertNotIn("hnsw", normalized_schema)
        self.assertNotIn("ivfflat", normalized_schema)

    def test_docker_compose_uses_pgvector_postgres_image_for_optional_integration_path(self) -> None:
        compose = Path("docker-compose.yml").read_text(encoding="utf-8")

        self.assertIn("image: pgvector/pgvector:pg16", compose)

    def test_pgvector_store_persists_embedding_index_with_auditable_metadata(self) -> None:
        corpus = load_nvidia_knowledge_corpus(_fixture_path())
        client = DeterministicFakeEmbeddingClient(dimension=6)
        index = build_nvidia_embedding_index(corpus, client)
        connection = _RecordingPgvectorConnection()

        PgvectorNVIDIAEmbeddingStore(connection).save_embedding_index(corpus, index)

        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.count_sql("INSERT INTO nvidia_knowledge_documents"), len(corpus.documents))
        self.assertEqual(connection.count_sql("INSERT INTO nvidia_knowledge_chunks"), len(corpus.chunks))
        self.assertEqual(connection.count_sql("INSERT INTO nvidia_chunk_embeddings"), len(corpus.chunks))

        embedding_insert = connection.first_sql("INSERT INTO nvidia_chunk_embeddings")
        self.assertIn("official-nvidia-fixture.v1", embedding_insert.params)
        self.assertIn("deterministic-fake-embedding", embedding_insert.params)
        self.assertIn("v1", embedding_insert.params)
        self.assertIn(6, embedding_insert.params)
        self.assertIn("cosine", embedding_insert.params)
        self.assertIn("[1.0,0.0,0.0,0.0,0.0,0.0]", embedding_insert.params)

        metadata = _first_json_param_with_key(embedding_insert.params, "embedding_model")
        self.assertEqual(metadata["corpus_version"], "official-nvidia-fixture.v1")
        self.assertEqual(metadata["embedding_provider"], "local_fake")
        self.assertEqual(metadata["embedding_model"], "deterministic-fake-embedding")
        self.assertEqual(metadata["embedding_version"], "v1")
        self.assertEqual(metadata["dimension"], 6)

        index_parameters = _first_json_param_with_key(embedding_insert.params, "index_type")
        self.assertEqual(index_parameters["distance_metric"], "cosine")
        self.assertEqual(index_parameters["index_type"], "exact_pgvector_sql")
        self.assertEqual(index_parameters["approximate_index"], "none")

    def test_pgvector_store_retrieves_nvidia_knowledge_with_sql_similarity(self) -> None:
        corpus = load_nvidia_knowledge_corpus(_fixture_path())
        corpus_payload = nvidia_knowledge_corpus_to_dict(corpus)
        client = DeterministicFakeEmbeddingClient(dimension=6)
        document_payload = corpus_payload["documents"][0]
        chunk_payload = corpus_payload["chunks"][0]
        connection = _RecordingPgvectorConnection(
            rows=(
                (
                    json.dumps(document_payload),
                    json.dumps(chunk_payload),
                    0.91,
                    json.dumps(
                        {
                            "distance_metric": "cosine",
                            "index_type": "exact_pgvector_sql",
                            "storage": "postgres_pgvector",
                            "approximate_index": "none",
                        },
                        sort_keys=True,
                    ),
                    json.dumps(
                        {
                            "schema_version": "nvidia_embedding.v1",
                            "corpus_version": "official-nvidia-fixture.v1",
                            "embedding_provider": "local_fake",
                            "embedding_model": "deterministic-fake-embedding",
                            "embedding_version": "v1",
                            "dimension": 6,
                            "expected_language_behavior": "deterministic multilingual fixture text",
                        },
                        sort_keys=True,
                    ),
                ),
            )
        )

        retrieval = PgvectorNVIDIAEmbeddingStore(connection).retrieve_by_vector(
            client,
            run_id="run-pgvector-001",
            corpus_version="official-nvidia-fixture.v1",
            gap_type="model_serving",
            description="Need lower latency inference deployment.",
            startup_signals=("self-hosted inference",),
            top_k=1,
        )

        select_execution = connection.first_sql("SELECT")
        self.assertIn("<=>", select_execution.sql)
        self.assertIn("ORDER BY e.embedding <=>", select_execution.sql)
        self.assertEqual(retrieval.schema_version, "nvidia_knowledge.v1")
        self.assertEqual(retrieval.run_id, "run-pgvector-001")
        self.assertEqual(retrieval.corpus_version, "official-nvidia-fixture.v1")
        self.assertIn("lower latency inference", retrieval.query)
        self.assertEqual(len(retrieval.results), 1)
        result = retrieval.results[0]
        self.assertEqual(result.chunk.chunk_id, "nvidia-nim-developers:0")
        self.assertEqual(result.citation.document_id, "nvidia-nim-developers")
        self.assertEqual(result.rank, 1)
        self.assertEqual(result.score, 0.91)
        self.assertEqual(result.vector_score, 0.91)
        self.assertEqual(result.bm25_score, 0.0)
        self.assertEqual(result.retrieval_strategy, "vector_semantic")
        self.assertEqual(result.ranking_strategy, "cosine_similarity_desc")
        self.assertEqual(result.index_parameters["index_type"], "exact_pgvector_sql")
        self.assertEqual(result.embedding_metadata["embedding_model"], "deterministic-fake-embedding")


def _fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "nvidia_knowledge_official_fixture.json"


@dataclass(frozen=True)
class _RecordedExecution:
    sql: str
    params: tuple[object, ...]


class _RecordingPgvectorConnection:
    def __init__(self, *, rows: tuple[tuple[object, ...], ...] = ()) -> None:
        self.rows = rows
        self.executions: list[_RecordedExecution] = []
        self.commits = 0

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> "_FakeCursor":
        self.executions.append(_RecordedExecution(sql=sql, params=tuple(params)))
        if sql.lstrip().upper().startswith("SELECT"):
            return _FakeCursor(self.rows)
        return _FakeCursor(())

    def commit(self) -> None:
        self.commits += 1

    def count_sql(self, pattern: str) -> int:
        return sum(1 for execution in self.executions if pattern in execution.sql)

    def first_sql(self, pattern: str) -> _RecordedExecution:
        for execution in self.executions:
            if pattern in execution.sql:
                return execution
        raise AssertionError(f"SQL pattern not executed: {pattern}")


class _FakeCursor:
    def __init__(self, rows: tuple[tuple[object, ...], ...]) -> None:
        self._rows = rows

    def fetchall(self) -> tuple[tuple[object, ...], ...]:
        return self._rows


def _first_json_param_with_key(params: tuple[object, ...], key: str) -> dict[str, object]:
    for param in params:
        if not isinstance(param, str) or not param.startswith("{"):
            continue
        payload = json.loads(param)
        if key in payload:
            return payload
    raise AssertionError(f"JSON param with key not found: {key}")


if __name__ == "__main__":
    unittest.main()
