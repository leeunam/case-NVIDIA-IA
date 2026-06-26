"""Optional Postgres/pgvector persistence adapter for NVIDIA embeddings.

This module is an integration boundary. It consumes the project-owned
NVIDIA Knowledge and embedding contracts, and returns those same contracts.
The default local suite can keep using in-memory indexes and fakes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
from typing import Any

from nvidia_startup_intel.nvidia_embeddings import (
    EmbeddingClient,
    EmbeddingVector,
    NVIDIAEmbeddingIndex,
    VECTOR_RANKING_STRATEGY,
    VECTOR_RETRIEVAL_STRATEGY,
    VECTOR_TIE_BREAKERS,
    embed_nvidia_query,
)
from nvidia_startup_intel.nvidia_knowledge import (
    NVIDIAKnowledgeChunk,
    NVIDIAKnowledgeCorpus,
    NVIDIAKnowledgeDocument,
    NVIDIAKnowledgeRetrieval,
    RetrievedNVIDIAKnowledge,
    SCHEMA_VERSION as KNOWLEDGE_SCHEMA_VERSION,
    build_nvidia_knowledge_query,
    nvidia_citation_from_chunk,
)


PGVECTOR_INDEX_PARAMETERS: dict[str, object] = {
    "distance_metric": "cosine",
    "index_type": "exact_pgvector_sql",
    "storage": "postgres_pgvector",
    "approximate_index": "none",
}


class PgvectorNVIDIAEmbeddingStore:
    """Persist and query NVIDIA Knowledge embeddings through pgvector SQL."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def save_embedding_index(
        self,
        corpus: NVIDIAKnowledgeCorpus,
        embedding_index: NVIDIAEmbeddingIndex,
    ) -> None:
        """Persist documents, chunks, vectors and audit metadata for a corpus."""

        _validate_index_matches_corpus(corpus, embedding_index)
        for document in corpus.documents:
            self.connection.execute(
                """
                INSERT INTO nvidia_knowledge_documents
                (
                    corpus_version,
                    document_id,
                    title,
                    source_url,
                    source_type,
                    ingested_at,
                    metadata_json,
                    payload_json,
                    schema_version
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (corpus_version, document_id)
                DO UPDATE SET
                    schema_version = EXCLUDED.schema_version,
                    title = EXCLUDED.title,
                    source_url = EXCLUDED.source_url,
                    source_type = EXCLUDED.source_type,
                    ingested_at = EXCLUDED.ingested_at,
                    metadata_json = EXCLUDED.metadata_json,
                    payload_json = EXCLUDED.payload_json
                """,
                (
                    document.corpus_version,
                    document.document_id,
                    document.title,
                    document.source_url,
                    document.source_type,
                    document.ingested_at,
                    _dumps(document.metadata),
                    _dumps(document),
                    document.schema_version,
                ),
            )

        for chunk in corpus.chunks:
            self.connection.execute(
                """
                INSERT INTO nvidia_knowledge_chunks
                (
                    corpus_version,
                    chunk_id,
                    document_id,
                    chunk_index,
                    topic,
                    text,
                    metadata_json,
                    payload_json,
                    schema_version
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (corpus_version, chunk_id)
                DO UPDATE SET
                    schema_version = EXCLUDED.schema_version,
                    document_id = EXCLUDED.document_id,
                    chunk_index = EXCLUDED.chunk_index,
                    topic = EXCLUDED.topic,
                    text = EXCLUDED.text,
                    metadata_json = EXCLUDED.metadata_json,
                    payload_json = EXCLUDED.payload_json
                """,
                (
                    chunk.corpus_version,
                    chunk.chunk_id,
                    chunk.document_id,
                    chunk.chunk_index,
                    chunk.topic,
                    chunk.text,
                    _dumps(chunk.metadata),
                    _dumps(chunk),
                    chunk.schema_version,
                ),
            )

        metadata = _embedding_metadata_payload(embedding_index)
        index_parameters = _pgvector_index_parameters(embedding_index.metadata.index_parameters)
        for chunk_embedding in embedding_index.chunk_embeddings:
            chunk = chunk_embedding.chunk
            self.connection.execute(
                """
                INSERT INTO nvidia_chunk_embeddings
                (
                    corpus_version,
                    chunk_id,
                    embedding_provider,
                    embedding_model,
                    embedding_version,
                    vector_dimension,
                    distance_metric,
                    index_parameters_json,
                    metadata_json,
                    payload_json,
                    embedding
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
                ON CONFLICT (
                    corpus_version,
                    chunk_id,
                    embedding_provider,
                    embedding_model,
                    embedding_version,
                    vector_dimension
                )
                DO UPDATE SET
                    distance_metric = EXCLUDED.distance_metric,
                    index_parameters_json = EXCLUDED.index_parameters_json,
                    metadata_json = EXCLUDED.metadata_json,
                    payload_json = EXCLUDED.payload_json,
                    embedding = EXCLUDED.embedding
                """,
                (
                    embedding_index.metadata.corpus_version,
                    chunk.chunk_id,
                    embedding_index.metadata.embedding_provider,
                    embedding_index.metadata.embedding_model,
                    embedding_index.metadata.embedding_version,
                    embedding_index.metadata.dimension,
                    str(index_parameters["distance_metric"]),
                    _dumps(index_parameters),
                    _dumps(metadata),
                    _dumps(
                        {
                            "schema_version": embedding_index.schema_version,
                            "chunk_id": chunk.chunk_id,
                            "chunk": chunk,
                            "metadata": metadata,
                            "index_parameters": index_parameters,
                            "vector": chunk_embedding.vector,
                        }
                    ),
                    _pgvector_literal(chunk_embedding.vector),
                ),
            )

        self.connection.commit()

    def retrieve_by_vector(
        self,
        embedding_client: EmbeddingClient,
        *,
        run_id: str,
        corpus_version: str,
        gap_type: str = "",
        opportunity_type: str = "",
        description: str = "",
        startup_signals: tuple[str, ...] = (),
        query_terms: tuple[str, ...] = (),
        normalized_query: str = "",
        top_k: int = 3,
        min_vector_score: float = 0.0,
    ) -> NVIDIAKnowledgeRetrieval:
        """Retrieve NVIDIA Knowledge by exact pgvector cosine similarity."""

        all_query_terms = (*query_terms, normalized_query) if normalized_query else query_terms
        query = build_nvidia_knowledge_query(
            gap_type=gap_type,
            opportunity_type=opportunity_type,
            description=description,
            startup_signals=startup_signals,
            query_terms=all_query_terms,
        )
        if not query:
            return NVIDIAKnowledgeRetrieval(
                schema_version=KNOWLEDGE_SCHEMA_VERSION,
                run_id=run_id,
                corpus_version=corpus_version,
                query=query,
                results=(),
                documents=(),
            )

        query_embedding = embed_nvidia_query(query, embedding_client)
        query_vector = _pgvector_literal(query_embedding.vector)
        cursor = self.connection.execute(
            """
            SELECT
                d.payload_json,
                c.payload_json,
                1 - (e.embedding <=> %s::vector) AS vector_score,
                e.index_parameters_json,
                e.metadata_json
            FROM nvidia_chunk_embeddings e
            JOIN nvidia_knowledge_chunks c
                ON c.corpus_version = e.corpus_version
                AND c.chunk_id = e.chunk_id
            JOIN nvidia_knowledge_documents d
                ON d.corpus_version = c.corpus_version
                AND d.document_id = c.document_id
            WHERE e.corpus_version = %s
                AND e.embedding_provider = %s
                AND e.embedding_model = %s
                AND e.embedding_version = %s
                AND e.vector_dimension = %s
                AND e.distance_metric = %s
                AND 1 - (e.embedding <=> %s::vector) > %s
            ORDER BY e.embedding <=> %s::vector ASC,
                c.document_id ASC,
                c.chunk_index ASC,
                c.chunk_id ASC
            LIMIT %s
            """,
            (
                query_vector,
                corpus_version,
                embedding_client.metadata.embedding_provider,
                embedding_client.metadata.embedding_model,
                embedding_client.metadata.embedding_version,
                embedding_client.metadata.dimension,
                "cosine",
                query_vector,
                min_vector_score,
                query_vector,
                top_k,
            ),
        )

        result_documents: dict[str, NVIDIAKnowledgeDocument] = {}
        results: list[RetrievedNVIDIAKnowledge] = []
        for row in cursor.fetchall():
            document = _document_from_payload(row[0])
            chunk = _chunk_from_payload(row[1])
            vector_score = round(float(row[2]), 6)
            if vector_score <= min_vector_score:
                continue
            result_documents[document.document_id] = document
            results.append(
                RetrievedNVIDIAKnowledge(
                    chunk=chunk,
                    citation=nvidia_citation_from_chunk(document, chunk),
                    score=vector_score,
                    retrieval_strategy=VECTOR_RETRIEVAL_STRATEGY,
                    rationale="Chunk embedding was nearest to the persisted pgvector NVIDIA Knowledge query.",
                    rank=len(results) + 1,
                    bm25_score=0.0,
                    vector_score=vector_score,
                    embedding_metadata=_loads_mapping(row[4]),
                    index_parameters=_loads_mapping(row[3]),
                    ranking_strategy=VECTOR_RANKING_STRATEGY,
                    tie_breakers=VECTOR_TIE_BREAKERS,
                )
            )

        return NVIDIAKnowledgeRetrieval(
            schema_version=KNOWLEDGE_SCHEMA_VERSION,
            run_id=run_id,
            corpus_version=corpus_version,
            query=query,
            results=tuple(results),
            documents=tuple(result_documents.values()),
        )


def _validate_index_matches_corpus(
    corpus: NVIDIAKnowledgeCorpus,
    embedding_index: NVIDIAEmbeddingIndex,
) -> None:
    if embedding_index.metadata.corpus_version != corpus.corpus_version:
        raise ValueError(
            "embedding_index_corpus_version_mismatch:"
            f"index_{embedding_index.metadata.corpus_version}:corpus_{corpus.corpus_version}"
        )
    corpus_chunk_ids = tuple(chunk.chunk_id for chunk in corpus.chunks)
    index_chunk_ids = tuple(chunk_embedding.chunk.chunk_id for chunk_embedding in embedding_index.chunk_embeddings)
    if index_chunk_ids != corpus_chunk_ids:
        raise ValueError("embedding_index_chunks_do_not_match_corpus")


def _pgvector_index_parameters(index_parameters: Mapping[str, object]) -> dict[str, object]:
    parameters = dict(index_parameters)
    parameters.update(PGVECTOR_INDEX_PARAMETERS)
    return {str(key): parameters[key] for key in sorted(parameters)}


def _embedding_metadata_payload(embedding_index: NVIDIAEmbeddingIndex) -> dict[str, object]:
    metadata = embedding_index.metadata
    return {
        "schema_version": metadata.schema_version,
        "corpus_version": metadata.corpus_version,
        "embedding_provider": metadata.embedding_provider,
        "embedding_model": metadata.embedding_model,
        "embedding_version": metadata.embedding_version,
        "dimension": metadata.dimension,
        "expected_language_behavior": metadata.expected_language_behavior,
    }


def _pgvector_literal(vector: EmbeddingVector) -> str:
    return f"[{','.join(str(float(component)) for component in vector)}]"


def _document_from_payload(payload_json: object) -> NVIDIAKnowledgeDocument:
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


def _chunk_from_payload(payload_json: object) -> NVIDIAKnowledgeChunk:
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


def _dumps(value: object) -> str:
    return json.dumps(_to_jsonable(value), ensure_ascii=False, sort_keys=True)


def _to_jsonable(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return _to_jsonable(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item) for item in value]
    return value
