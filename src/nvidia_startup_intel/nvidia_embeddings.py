"""Embedding contracts for NVIDIA Knowledge.

The domain depends on this project-owned contract, not on provider SDKs,
LLMs, vector databases, or framework-specific retriever objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from hashlib import sha256
from typing import Mapping, Protocol

from nvidia_startup_intel.nvidia_knowledge import NVIDIAKnowledgeChunk, NVIDIAKnowledgeCorpus
from nvidia_startup_intel.normalization import normalize_text


SCHEMA_VERSION = "nvidia_embedding.v1"
EmbeddingVector = tuple[float, ...]
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
        normalized_text = normalize_text(text)
        return tuple(
            _stable_unit_float(
                "|".join(
                    (
                        self.metadata.embedding_provider,
                        self.metadata.embedding_model,
                        self.metadata.embedding_version,
                        normalized_text,
                        str(index),
                    )
                )
            )
            for index in range(self.metadata.dimension)
        )


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


def _stable_unit_float(value: str) -> float:
    integer = int.from_bytes(sha256(value.encode("utf-8")).digest()[:8], byteorder="big")
    scaled = (integer / ((1 << 64) - 1)) * 2 - 1
    return round(scaled, 6)


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
