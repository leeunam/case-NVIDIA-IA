"""Embedding contracts for NVIDIA Knowledge.

The domain depends on this project-owned contract, not on provider SDKs,
LLMs, vector databases, or framework-specific retriever objects.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, fields, is_dataclass
import math
import re
from typing import Protocol

from nvidia_startup_intel.nvidia_knowledge import (
    NVIDIAKnowledgeChunk,
    NVIDIAKnowledgeCorpus,
    NVIDIAKnowledgeDocument,
    NVIDIAKnowledgeRetrieval,
    RetrievedNVIDIAKnowledge,
    build_nvidia_knowledge_query,
    nvidia_citation_from_chunk,
)
from nvidia_startup_intel.normalization import normalize_text


SCHEMA_VERSION = "nvidia_embedding.v1"
EmbeddingVector = tuple[float, ...]
VECTOR_RETRIEVAL_STRATEGY = "vector_semantic"
VECTOR_RANKING_STRATEGY = "cosine_similarity_desc"
VECTOR_TIE_BREAKERS = ("document_id", "chunk_index", "chunk_id")
DEFAULT_INDEX_PARAMETERS: dict[str, object] = {
    "distance_metric": "cosine",
    "index_type": "exact_in_memory",
}
REBUILD_REQUIREMENTS = (
    "corpus_version",
    "embedding_provider",
    "embedding_model",
    "embedding_version",
    "dimension",
    "index_parameters",
)


@dataclass(frozen=True)
class EmbeddingModelMetadata:
    schema_version: str
    embedding_provider: str
    embedding_model: str
    embedding_version: str
    dimension: int
    expected_language_behavior: str


@dataclass(frozen=True)
class NVIDIAEmbeddingIndexMetadata:
    schema_version: str
    corpus_version: str
    embedding_provider: str
    embedding_model: str
    embedding_version: str
    dimension: int
    expected_language_behavior: str
    index_parameters: dict[str, object] = field(default_factory=dict)
    rebuild_requirements: tuple[str, ...] = REBUILD_REQUIREMENTS


@dataclass(frozen=True)
class NVIDIAChunkEmbedding:
    chunk: NVIDIAKnowledgeChunk
    vector: EmbeddingVector


@dataclass(frozen=True)
class NVIDIAEmbeddingIndex:
    schema_version: str
    metadata: NVIDIAEmbeddingIndexMetadata
    chunk_embeddings: tuple[NVIDIAChunkEmbedding, ...]


@dataclass(frozen=True)
class NVIDIAQueryEmbedding:
    schema_version: str
    query: str
    metadata: EmbeddingModelMetadata
    vector: EmbeddingVector


@dataclass(frozen=True)
class NVIDIAEmbeddingIndexRebuildAssessment:
    rebuild_required: bool
    reasons: tuple[str, ...]


class EmbeddingClient(Protocol):
    @property
    def metadata(self) -> EmbeddingModelMetadata: ...

    def embed_texts(self, texts: tuple[str, ...]) -> tuple[EmbeddingVector, ...]: ...


class DeterministicFakeEmbeddingClient:
    """Local deterministic embedding client for fixtures and tests."""

    def __init__(
        self,
        *,
        dimension: int = 8,
        embedding_provider: str = "local_fake",
        embedding_model: str = "deterministic-fake-embedding",
        embedding_version: str = "v1",
        expected_language_behavior: str = "deterministic multilingual fixture text",
    ) -> None:
        self._metadata = EmbeddingModelMetadata(
            schema_version=SCHEMA_VERSION,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            embedding_version=embedding_version,
            dimension=dimension,
            expected_language_behavior=expected_language_behavior,
        )

    @property
    def metadata(self) -> EmbeddingModelMetadata:
        return self._metadata

    def embed_texts(self, texts: tuple[str, ...]) -> tuple[EmbeddingVector, ...]:
        return tuple(self._embed_text(text) for text in texts)

    def _embed_text(self, text: str) -> EmbeddingVector:
        vector = [0.0 for _ in range(self.metadata.dimension)]
        tokens = set(_embedding_tokens(text))
        for feature_index, keywords in enumerate(_SEMANTIC_FIXTURE_FEATURES):
            if feature_index >= self.metadata.dimension:
                break
            matches = sum(1 for token in tokens if token in keywords)
            if matches:
                vector[feature_index] = float(matches)
        return _normalize_vector(tuple(vector))


def build_nvidia_embedding_index(
    corpus: NVIDIAKnowledgeCorpus,
    embedding_client: EmbeddingClient,
    *,
    index_parameters: Mapping[str, object] | None = None,
) -> NVIDIAEmbeddingIndex:
    """Embed NVIDIA Knowledge chunks into a deterministic local index payload."""

    chunk_vectors = embedding_client.embed_texts(tuple(chunk.text for chunk in corpus.chunks))
    _validate_embedding_vectors(
        corpus.chunks,
        chunk_vectors,
        expected_dimension=embedding_client.metadata.dimension,
    )
    return NVIDIAEmbeddingIndex(
        schema_version=SCHEMA_VERSION,
        metadata=nvidia_embedding_index_metadata(
            corpus,
            embedding_client,
            index_parameters=index_parameters,
        ),
        chunk_embeddings=tuple(
            NVIDIAChunkEmbedding(chunk=chunk, vector=vector)
            for chunk, vector in zip(corpus.chunks, chunk_vectors, strict=True)
        ),
    )


def embed_nvidia_query(query: str, embedding_client: EmbeddingClient) -> NVIDIAQueryEmbedding:
    """Embed a retrieval query using the same model contract as chunk embeddings."""

    vectors = embedding_client.embed_texts((query,))
    if len(vectors) != 1:
        raise ValueError(f"query_embedding_count_mismatch:expected_1:actual_{len(vectors)}")
    vector = vectors[0]
    _validate_embedding_vector(
        subject="query",
        vector=vector,
        expected_dimension=embedding_client.metadata.dimension,
    )
    return NVIDIAQueryEmbedding(
        schema_version=SCHEMA_VERSION,
        query=query,
        metadata=embedding_client.metadata,
        vector=vector,
    )


def retrieve_nvidia_knowledge_by_vector(
    corpus: NVIDIAKnowledgeCorpus,
    embedding_index: NVIDIAEmbeddingIndex,
    embedding_client: EmbeddingClient,
    *,
    run_id: str,
    gap_type: str = "",
    opportunity_type: str = "",
    description: str = "",
    startup_signals: tuple[str, ...] = (),
    query_terms: tuple[str, ...] = (),
    normalized_query: str = "",
    top_k: int = 3,
    min_vector_score: float = 0.0,
) -> NVIDIAKnowledgeRetrieval:
    """Retrieve citable NVIDIA chunks with exact in-memory vector search."""

    _validate_embedding_index_for_retrieval(corpus, embedding_index, embedding_client)
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
            schema_version="nvidia_knowledge.v1",
            run_id=run_id,
            corpus_version=corpus.corpus_version,
            query=query,
            results=(),
            documents=(),
        )

    query_embedding = embed_nvidia_query(query, embedding_client)
    documents_by_id = {document.document_id: document for document in corpus.documents}
    scored_embeddings = _deduplicate_vector_scores(
        (
            (
                chunk_embedding.chunk,
                _cosine_similarity(query_embedding.vector, chunk_embedding.vector),
            )
            for chunk_embedding in embedding_index.chunk_embeddings
        ),
        min_vector_score=min_vector_score,
    )
    results: list[RetrievedNVIDIAKnowledge] = []
    result_documents: dict[str, NVIDIAKnowledgeDocument] = {}

    for chunk, score in scored_embeddings[:top_k]:
        document = documents_by_id.get(chunk.document_id)
        if document is None:
            continue
        result_documents[document.document_id] = document
        vector_score = round(score, 6)
        results.append(
            RetrievedNVIDIAKnowledge(
                chunk=chunk,
                citation=nvidia_citation_from_chunk(document, chunk),
                score=vector_score,
                retrieval_strategy=VECTOR_RETRIEVAL_STRATEGY,
                rationale="Chunk embedding was nearest to the vectorized NVIDIA Knowledge query.",
                rank=len(results) + 1,
                bm25_score=0.0,
                vector_score=vector_score,
                embedding_metadata=_embedding_result_metadata(embedding_index.metadata),
                index_parameters=dict(embedding_index.metadata.index_parameters),
                ranking_strategy=VECTOR_RANKING_STRATEGY,
                tie_breakers=VECTOR_TIE_BREAKERS,
            )
        )

    return NVIDIAKnowledgeRetrieval(
        schema_version="nvidia_knowledge.v1",
        run_id=run_id,
        corpus_version=corpus.corpus_version,
        query=query,
        results=tuple(results),
        documents=tuple(result_documents.values()),
    )


def nvidia_embedding_index_metadata(
    corpus: NVIDIAKnowledgeCorpus,
    embedding_client: EmbeddingClient,
    *,
    index_parameters: Mapping[str, object] | None = None,
) -> NVIDIAEmbeddingIndexMetadata:
    metadata = embedding_client.metadata
    return NVIDIAEmbeddingIndexMetadata(
        schema_version=SCHEMA_VERSION,
        corpus_version=corpus.corpus_version,
        embedding_provider=metadata.embedding_provider,
        embedding_model=metadata.embedding_model,
        embedding_version=metadata.embedding_version,
        dimension=metadata.dimension,
        expected_language_behavior=metadata.expected_language_behavior,
        index_parameters=_normalized_index_parameters(index_parameters),
    )


def assess_nvidia_embedding_index_rebuild(
    current_metadata: NVIDIAEmbeddingIndexMetadata,
    corpus: NVIDIAKnowledgeCorpus,
    embedding_client: EmbeddingClient,
    *,
    index_parameters: Mapping[str, object] | None = None,
) -> NVIDIAEmbeddingIndexRebuildAssessment:
    """Compare current index metadata with desired metadata for a corpus/client pair."""

    desired_metadata = nvidia_embedding_index_metadata(
        corpus,
        embedding_client,
        index_parameters=index_parameters,
    )
    reasons: list[str] = []

    if current_metadata.corpus_version != desired_metadata.corpus_version:
        reasons.append("corpus_version_changed")
    if current_metadata.embedding_provider != desired_metadata.embedding_provider:
        reasons.append("embedding_provider_changed")
    if current_metadata.embedding_model != desired_metadata.embedding_model:
        reasons.append("embedding_model_changed")
    if current_metadata.embedding_version != desired_metadata.embedding_version:
        reasons.append("embedding_version_changed")
    if current_metadata.dimension != desired_metadata.dimension:
        reasons.append("dimension_changed")
    if current_metadata.index_parameters != desired_metadata.index_parameters:
        reasons.append("index_parameters_changed")

    return NVIDIAEmbeddingIndexRebuildAssessment(
        rebuild_required=bool(reasons),
        reasons=tuple(reasons),
    )


def nvidia_embedding_index_to_dict(index: NVIDIAEmbeddingIndex) -> dict[str, object]:
    """Convert an embedding index payload to a JSON-serializable dictionary."""

    return _to_plain_data(index)


def nvidia_query_embedding_to_dict(query_embedding: NVIDIAQueryEmbedding) -> dict[str, object]:
    """Convert a query embedding payload to a JSON-serializable dictionary."""

    return _to_plain_data(query_embedding)


_SEMANTIC_FIXTURE_FEATURES: tuple[frozenset[str], ...] = (
    frozenset(
        {
            "containers",
            "deployment",
            "hosted",
            "inference",
            "inferencing",
            "latency",
            "microservices",
            "nim",
            "serving",
        }
    ),
    frozenset(
        {
            "customization",
            "customize",
            "generative",
            "llm",
            "models",
            "nemo",
        }
    ),
    frozenset({"cudf", "dataframe", "dataframes", "operations"}),
    frozenset({"computer", "deepstream", "sensor", "video", "vision"}),
    frozenset({"cohorts", "deadlines", "fees", "inception", "program", "startup", "startups"}),
)


def _embedding_tokens(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", normalize_text(value)))


def _normalize_vector(vector: EmbeddingVector) -> EmbeddingVector:
    magnitude = math.sqrt(sum(component * component for component in vector))
    if magnitude == 0:
        return vector
    return tuple(round(component / magnitude, 6) for component in vector)


def _cosine_similarity(left: EmbeddingVector, right: EmbeddingVector) -> float:
    left_magnitude = math.sqrt(sum(component * component for component in left))
    right_magnitude = math.sqrt(sum(component * component for component in right))
    if left_magnitude == 0 or right_magnitude == 0:
        return 0.0
    dot_product = sum(
        left_component * right_component
        for left_component, right_component in zip(left, right, strict=True)
    )
    return dot_product / (left_magnitude * right_magnitude)


def _deduplicate_vector_scores(
    scored_chunks: Iterable[tuple[NVIDIAKnowledgeChunk, float]],
    *,
    min_vector_score: float,
) -> list[tuple[NVIDIAKnowledgeChunk, float]]:
    best_scores_by_chunk_id: dict[str, tuple[NVIDIAKnowledgeChunk, float]] = {}
    for chunk, score in scored_chunks:
        if score <= min_vector_score:
            continue
        current = best_scores_by_chunk_id.get(chunk.chunk_id)
        if current is None or score > current[1]:
            best_scores_by_chunk_id[chunk.chunk_id] = (chunk, score)
    return sorted(
        best_scores_by_chunk_id.values(),
        key=lambda item: (-item[1], item[0].document_id, item[0].chunk_index, item[0].chunk_id),
    )


def _embedding_result_metadata(metadata: NVIDIAEmbeddingIndexMetadata) -> dict[str, object]:
    return {
        "schema_version": metadata.schema_version,
        "corpus_version": metadata.corpus_version,
        "embedding_provider": metadata.embedding_provider,
        "embedding_model": metadata.embedding_model,
        "embedding_version": metadata.embedding_version,
        "dimension": metadata.dimension,
        "expected_language_behavior": metadata.expected_language_behavior,
    }


def _validate_embedding_index_for_retrieval(
    corpus: NVIDIAKnowledgeCorpus,
    embedding_index: NVIDIAEmbeddingIndex,
    embedding_client: EmbeddingClient,
) -> None:
    if embedding_index.metadata.corpus_version != corpus.corpus_version:
        raise ValueError(
            "embedding_index_corpus_version_mismatch:"
            f"index_{embedding_index.metadata.corpus_version}:corpus_{corpus.corpus_version}"
        )
    if embedding_index.metadata.embedding_provider != embedding_client.metadata.embedding_provider:
        raise ValueError("embedding_index_provider_mismatch")
    if embedding_index.metadata.embedding_model != embedding_client.metadata.embedding_model:
        raise ValueError("embedding_index_model_mismatch")
    if embedding_index.metadata.embedding_version != embedding_client.metadata.embedding_version:
        raise ValueError("embedding_index_version_mismatch")
    if embedding_index.metadata.dimension != embedding_client.metadata.dimension:
        raise ValueError(
            "embedding_index_dimension_mismatch:"
            f"index_{embedding_index.metadata.dimension}:client_{embedding_client.metadata.dimension}"
        )
    if embedding_index.metadata.index_parameters.get("distance_metric") != "cosine":
        raise ValueError("unsupported_vector_distance_metric")


def _validate_embedding_vectors(
    chunks: tuple[NVIDIAKnowledgeChunk, ...],
    vectors: tuple[EmbeddingVector, ...],
    *,
    expected_dimension: int,
) -> None:
    for chunk, vector in zip(chunks, vectors, strict=True):
        _validate_embedding_vector(
            subject=chunk.chunk_id,
            vector=vector,
            expected_dimension=expected_dimension,
        )


def _validate_embedding_vector(
    *,
    subject: str,
    vector: EmbeddingVector,
    expected_dimension: int,
) -> None:
    actual_dimension = len(vector)
    if actual_dimension != expected_dimension:
        raise ValueError(
            "embedding_dimension_mismatch:"
            f"{subject}:expected_{expected_dimension}:actual_{actual_dimension}"
        )


def _normalized_index_parameters(index_parameters: Mapping[str, object] | None) -> dict[str, object]:
    parameters = DEFAULT_INDEX_PARAMETERS if index_parameters is None else index_parameters
    return {str(key): parameters[key] for key in sorted(parameters)}


def _to_plain_data(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: _to_plain_data(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, dict):
        return {key: _to_plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain_data(item) for item in value]
    return value
