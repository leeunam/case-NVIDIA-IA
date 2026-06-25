"""Versioned NVIDIA knowledge contracts.

This module represents local, official NVIDIA source material and retrieved
citable chunks. It does not perform retrieval, call LLMs, use embeddings, or
touch the network.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import field, fields, is_dataclass, dataclass
import json
import math
from pathlib import Path
import re
from urllib.parse import urlparse

from nvidia_startup_intel.normalization import normalize_text


SCHEMA_VERSION = "nvidia_knowledge.v1"


@dataclass(frozen=True)
class NVIDIAKnowledgeDocument:
    schema_version: str
    corpus_version: str
    document_id: str
    title: str
    source_url: str
    source_type: str
    ingested_at: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class NVIDIAKnowledgeChunk:
    schema_version: str
    corpus_version: str
    chunk_id: str
    document_id: str
    chunk_index: int
    topic: str
    text: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class NVIDIACitation:
    schema_version: str
    corpus_version: str
    document_id: str
    document_title: str
    source_url: str
    source_type: str
    ingested_at: str
    chunk_id: str
    excerpt: str
    chunk_index: int


@dataclass(frozen=True)
class RetrievedNVIDIAKnowledge:
    chunk: NVIDIAKnowledgeChunk
    citation: NVIDIACitation
    score: float
    retrieval_strategy: str
    rationale: str
    rank: int = 0
    bm25_score: float = 0.0
    vector_score: float = 0.0
    hybrid_score: float = 0.0
    embedding_metadata: dict[str, object] = field(default_factory=dict)
    index_parameters: dict[str, object] = field(default_factory=dict)
    ranking_strategy: str = ""
    tie_breakers: tuple[str, ...] = ()


@dataclass(frozen=True)
class NVIDIAKnowledgeRetrieval:
    schema_version: str
    run_id: str
    corpus_version: str
    query: str
    results: tuple[RetrievedNVIDIAKnowledge, ...]
    documents: tuple[NVIDIAKnowledgeDocument, ...]


@dataclass(frozen=True)
class NVIDIAKnowledgeCorpus:
    schema_version: str
    corpus_version: str
    documents: tuple[NVIDIAKnowledgeDocument, ...]
    chunks: tuple[NVIDIAKnowledgeChunk, ...]


@dataclass(frozen=True)
class NVIDIAKnowledgeValidationIssue:
    document_id: str
    reason: str


@dataclass(frozen=True)
class NVIDIAKnowledgeDocumentValidation:
    is_valid: bool
    accepted_documents: tuple[NVIDIAKnowledgeDocument, ...]
    issues: tuple[NVIDIAKnowledgeValidationIssue, ...]


@dataclass(frozen=True)
class NVIDIAKnowledgeRetrievalQuality:
    has_sufficient_citation: bool
    reasons: tuple[str, ...]


def nvidia_knowledge_retrieval_to_dict(retrieval: NVIDIAKnowledgeRetrieval) -> dict[str, object]:
    """Convert retrieval output to a JSON-serializable dictionary."""

    return _to_plain_data(retrieval)


def nvidia_knowledge_corpus_to_dict(corpus: NVIDIAKnowledgeCorpus) -> dict[str, object]:
    """Convert a loaded NVIDIA knowledge corpus to a JSON-serializable dictionary."""

    return _to_plain_data(corpus)


def load_nvidia_knowledge_corpus(path: str | Path) -> NVIDIAKnowledgeCorpus:
    """Load a local NVIDIA knowledge corpus from JSON without network access."""

    with Path(path).open(encoding="utf-8") as corpus_file:
        data = json.load(corpus_file)

    documents = tuple(_document_from_dict(item) for item in data["documents"])
    validation = validate_nvidia_knowledge_documents(documents)
    if not validation.is_valid:
        reasons = ", ".join(f"{issue.document_id}:{issue.reason}" for issue in validation.issues)
        raise ValueError(f"invalid_nvidia_knowledge_corpus:{reasons}")

    return NVIDIAKnowledgeCorpus(
        schema_version=data["schema_version"],
        corpus_version=data["corpus_version"],
        documents=documents,
        chunks=tuple(_chunk_from_dict(item) for item in data["chunks"]),
    )


def chunk_nvidia_knowledge_document(
    document: NVIDIAKnowledgeDocument,
    *,
    topic: str,
    text_blocks: tuple[str, ...],
) -> tuple[NVIDIAKnowledgeChunk, ...]:
    """Create deterministic chunks from ordered document text blocks."""

    chunks: list[NVIDIAKnowledgeChunk] = []
    for text_block in text_blocks:
        text = " ".join(text_block.split())
        if not text:
            continue
        chunk_index = len(chunks)
        chunks.append(
            NVIDIAKnowledgeChunk(
                schema_version=SCHEMA_VERSION,
                corpus_version=document.corpus_version,
                chunk_id=f"{document.document_id}:{chunk_index}",
                document_id=document.document_id,
                chunk_index=chunk_index,
                topic=topic,
                text=text,
                metadata={
                    "document_title": document.title,
                    "source_url": document.source_url,
                    "source_type": document.source_type,
                    "ingested_at": document.ingested_at,
                },
            )
        )
    return tuple(chunks)


def retrieve_nvidia_knowledge(
    corpus: NVIDIAKnowledgeCorpus,
    *,
    run_id: str,
    gap_type: str = "",
    opportunity_type: str = "",
    description: str = "",
    startup_signals: tuple[str, ...] = (),
    query_terms: tuple[str, ...] = (),
    top_k: int = 3,
) -> NVIDIAKnowledgeRetrieval:
    """Retrieve citable NVIDIA chunks from gap, opportunity, or normalized terms."""

    query = build_nvidia_knowledge_query(
        gap_type=gap_type,
        opportunity_type=opportunity_type,
        description=description,
        startup_signals=startup_signals,
        query_terms=query_terms,
    )
    query_tokens = _tokenize(query)
    documents_by_id = {document.document_id: document for document in corpus.documents}
    scored_chunks = _deduplicate_scored_chunks(_bm25_score_chunks(corpus.chunks, query_tokens))
    results: list[RetrievedNVIDIAKnowledge] = []
    result_documents: dict[str, NVIDIAKnowledgeDocument] = {}

    for chunk, score in scored_chunks[:top_k]:
        document = documents_by_id.get(chunk.document_id)
        if document is None:
            continue
        result_documents[document.document_id] = document
        score = round(score, 6)
        results.append(
            RetrievedNVIDIAKnowledge(
                chunk=chunk,
                citation=nvidia_citation_from_chunk(document, chunk),
                score=score,
                retrieval_strategy="bm25_lexical",
                rationale="Chunk topic and text matched the BM25 lexical query.",
                rank=len(results) + 1,
                bm25_score=score,
            )
        )

    return NVIDIAKnowledgeRetrieval(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        corpus_version=corpus.corpus_version,
        query=query,
        results=tuple(results),
        documents=tuple(result_documents.values()),
    )


def retrieve_nvidia_knowledge_by_gap(
    corpus: NVIDIAKnowledgeCorpus,
    *,
    run_id: str,
    gap_type: str,
    description: str,
    startup_signals: tuple[str, ...] = (),
    top_k: int = 3,
) -> NVIDIAKnowledgeRetrieval:
    """Retrieve citable NVIDIA chunks for an assessed technical gap using BM25."""

    return retrieve_nvidia_knowledge(
        corpus,
        run_id=run_id,
        gap_type=gap_type,
        description=description,
        startup_signals=startup_signals,
        top_k=top_k,
    )


def build_nvidia_knowledge_query(
    *,
    gap_type: str = "",
    opportunity_type: str = "",
    description: str = "",
    startup_signals: tuple[str, ...] = (),
    query_terms: tuple[str, ...] = (),
) -> str:
    """Build the shared query text for NVIDIA Knowledge retrieval paths."""

    return _retrieval_query(
        gap_type=gap_type,
        opportunity_type=opportunity_type,
        description=description,
        startup_signals=startup_signals,
        query_terms=query_terms,
    )


def summarize_nvidia_retrieval_quality(
    retrieval: NVIDIAKnowledgeRetrieval,
) -> NVIDIAKnowledgeRetrievalQuality:
    """Summarize whether retrieval returned enough official citation support."""

    if not retrieval.results:
        return NVIDIAKnowledgeRetrievalQuality(
            has_sufficient_citation=False,
            reasons=("no_retrieved_citation",),
        )

    if any(_is_official_nvidia_url(result.citation.source_url) for result in retrieval.results):
        return NVIDIAKnowledgeRetrievalQuality(
            has_sufficient_citation=True,
            reasons=("citation_sufficient",),
        )

    return NVIDIAKnowledgeRetrievalQuality(
        has_sufficient_citation=False,
        reasons=("no_official_nvidia_citation",),
    )


def validate_nvidia_knowledge_documents(
    documents: tuple[NVIDIAKnowledgeDocument, ...],
) -> NVIDIAKnowledgeDocumentValidation:
    """Validate that local NVIDIA knowledge documents come from official NVIDIA URLs."""

    accepted_documents: list[NVIDIAKnowledgeDocument] = []
    issues: list[NVIDIAKnowledgeValidationIssue] = []
    for document in documents:
        if _is_official_nvidia_url(document.source_url):
            accepted_documents.append(document)
            continue
        issues.append(
            NVIDIAKnowledgeValidationIssue(
                document_id=document.document_id,
                reason="source_url_not_official_nvidia",
            )
        )

    return NVIDIAKnowledgeDocumentValidation(
        is_valid=not issues,
        accepted_documents=tuple(accepted_documents),
        issues=tuple(issues),
    )


def nvidia_citation_from_chunk(
    document: NVIDIAKnowledgeDocument,
    chunk: NVIDIAKnowledgeChunk,
) -> NVIDIACitation:
    """Create a citation from a document and one of its chunks."""

    if chunk.document_id != document.document_id:
        raise ValueError("chunk_document_id_does_not_match_document")

    return NVIDIACitation(
        schema_version=SCHEMA_VERSION,
        corpus_version=document.corpus_version,
        document_id=document.document_id,
        document_title=document.title,
        source_url=document.source_url,
        source_type=document.source_type,
        ingested_at=document.ingested_at,
        chunk_id=chunk.chunk_id,
        excerpt=chunk.text,
        chunk_index=chunk.chunk_index,
    )


def _is_official_nvidia_url(source_url: str) -> bool:
    host = urlparse(source_url).hostname or ""
    return host == "nvidia.com" or host.endswith(".nvidia.com")


def _document_from_dict(data: dict[str, object]) -> NVIDIAKnowledgeDocument:
    document_id = str(data.get("document_id", "unknown_document"))
    if not data.get("source_url"):
        raise ValueError(f"{document_id}:missing_source_url")

    return NVIDIAKnowledgeDocument(
        schema_version=str(data["schema_version"]),
        corpus_version=str(data["corpus_version"]),
        document_id=document_id,
        title=str(data["title"]),
        source_url=str(data["source_url"]),
        source_type=str(data["source_type"]),
        ingested_at=str(data["ingested_at"]),
        metadata=dict(data.get("metadata", {})),
    )


def _chunk_from_dict(data: dict[str, object]) -> NVIDIAKnowledgeChunk:
    return NVIDIAKnowledgeChunk(
        schema_version=str(data["schema_version"]),
        corpus_version=str(data["corpus_version"]),
        chunk_id=str(data["chunk_id"]),
        document_id=str(data["document_id"]),
        chunk_index=int(data["chunk_index"]),
        topic=str(data["topic"]),
        text=str(data["text"]),
        metadata=dict(data.get("metadata", {})),
    )


def _retrieval_query(
    *,
    gap_type: str,
    opportunity_type: str,
    description: str,
    startup_signals: tuple[str, ...],
    query_terms: tuple[str, ...],
) -> str:
    return " ".join(
        (
            gap_type.replace("_", " "),
            opportunity_type.replace("_", " "),
            description,
            *startup_signals,
            *query_terms,
        )
    ).strip()


def _bm25_score_chunks(
    chunks: tuple[NVIDIAKnowledgeChunk, ...],
    query_tokens: tuple[str, ...],
) -> list[tuple[NVIDIAKnowledgeChunk, float]]:
    if not chunks or not query_tokens:
        return []

    searchable_tokens = tuple(_tokenize(f"{chunk.topic.replace('_', ' ')} {chunk.text}") for chunk in chunks)
    average_length = sum(len(tokens) for tokens in searchable_tokens) / len(searchable_tokens)
    document_frequency = Counter(token for token in set(query_tokens) for tokens in searchable_tokens if token in tokens)
    query_counts = Counter(query_tokens)
    scored: list[tuple[NVIDIAKnowledgeChunk, float]] = []

    for chunk, chunk_tokens in zip(chunks, searchable_tokens, strict=True):
        token_counts = Counter(chunk_tokens)
        score = 0.0
        for token, query_weight in query_counts.items():
            frequency = token_counts[token]
            if frequency == 0:
                continue
            score += query_weight * _bm25_term_score(
                frequency=frequency,
                document_frequency=document_frequency[token],
                document_count=len(chunks),
                document_length=len(chunk_tokens),
                average_document_length=average_length,
            )
        if score > 0:
            scored.append((chunk, score))

    return sorted(scored, key=lambda item: (-item[1], item[0].document_id, item[0].chunk_index))


def _deduplicate_scored_chunks(
    scored_chunks: list[tuple[NVIDIAKnowledgeChunk, float]],
) -> list[tuple[NVIDIAKnowledgeChunk, float]]:
    deduplicated: list[tuple[NVIDIAKnowledgeChunk, float]] = []
    seen_chunk_ids: set[str] = set()
    for chunk, score in scored_chunks:
        if chunk.chunk_id in seen_chunk_ids:
            continue
        seen_chunk_ids.add(chunk.chunk_id)
        deduplicated.append((chunk, score))
    return deduplicated


def _bm25_term_score(
    *,
    frequency: int,
    document_frequency: int,
    document_count: int,
    document_length: int,
    average_document_length: float,
) -> float:
    k1 = 1.5
    b = 0.75
    idf = math.log(1 + (document_count - document_frequency + 0.5) / (document_frequency + 0.5))
    denominator = frequency + k1 * (1 - b + b * document_length / average_document_length)
    return idf * frequency * (k1 + 1) / denominator


def _tokenize(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", normalize_text(value)))


def _to_plain_data(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _to_plain_data(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {key: _to_plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain_data(item) for item in value]
    return value
