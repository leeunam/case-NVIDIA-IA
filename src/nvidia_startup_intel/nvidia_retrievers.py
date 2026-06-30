"""NVIDIA Knowledge retriever adapter seams."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import re
from typing import Protocol

from nvidia_startup_intel.ai_native_assessment import TechnicalGap
from nvidia_startup_intel.normalization import normalize_text
from nvidia_startup_intel.nvidia_embeddings import (
    EmbeddingClient,
    merge_nvidia_knowledge_retrievals_hybrid,
)
from nvidia_startup_intel.nvidia_knowledge import (
    NVIDIAKnowledgeCorpus,
    NVIDIAKnowledgeQuery,
    NVIDIAKnowledgeRetrieval,
    RetrievedNVIDIAKnowledge,
    build_nvidia_knowledge_query,
    nvidia_citation_from_chunk,
    retrieve_nvidia_knowledge,
    retrieve_nvidia_knowledge_by_gap,
)


class NVIDIAKnowledgeRetriever(Protocol):
    """Project-owned retrieval seam for LlamaIndex, LangChain, or local BM25 adapters."""

    def retrieve_for_query(
        self,
        *,
        run_id: str,
        query: NVIDIAKnowledgeQuery,
        top_k: int,
    ) -> NVIDIAKnowledgeRetrieval: ...

    def retrieve_for_gap(
        self,
        *,
        run_id: str,
        gap: TechnicalGap,
        startup_signals: tuple[str, ...],
        top_k: int,
    ) -> NVIDIAKnowledgeRetrieval: ...


class NVIDIAVectorKnowledgeStore(Protocol):
    """Project-owned seam for pgvector-backed semantic NVIDIA Knowledge retrieval."""

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
    ) -> NVIDIAKnowledgeRetrieval: ...


@dataclass(frozen=True)
class LocalBM25NVIDIAKnowledgeRetriever:
    """Adapter over the existing deterministic NVIDIA Knowledge retrieval contract."""

    corpus: NVIDIAKnowledgeCorpus

    def retrieve_for_query(
        self,
        *,
        run_id: str,
        query: NVIDIAKnowledgeQuery,
        top_k: int,
    ) -> NVIDIAKnowledgeRetrieval:
        return retrieve_nvidia_knowledge(
            self.corpus,
            run_id=run_id,
            query_request=query,
            top_k=top_k,
        )

    def retrieve_for_gap(
        self,
        *,
        run_id: str,
        gap: TechnicalGap,
        startup_signals: tuple[str, ...],
        top_k: int,
    ) -> NVIDIAKnowledgeRetrieval:
        return retrieve_nvidia_knowledge_by_gap(
            self.corpus,
            run_id=run_id,
            gap_type=gap.gap_type,
            description=gap.description,
            startup_signals=startup_signals,
            top_k=top_k,
        )


@dataclass(frozen=True)
class HybridNVIDIAPgvectorKnowledgeRetriever:
    """Adapter that fuses local BM25 with pgvector semantic retrieval."""

    corpus: NVIDIAKnowledgeCorpus
    embedding_client: EmbeddingClient
    vector_store: NVIDIAVectorKnowledgeStore
    lexical_retriever: NVIDIAKnowledgeRetriever | None = None
    lexical_top_k: int = 3
    vector_top_k: int = 3
    lexical_weight: float = 1.0
    vector_weight: float = 1.0
    rrf_k: int = 60
    min_vector_score: float = 0.0

    def retrieve_for_query(
        self,
        *,
        run_id: str,
        query: NVIDIAKnowledgeQuery,
        top_k: int,
    ) -> NVIDIAKnowledgeRetrieval:
        lexical_retrieval = (self.lexical_retriever or LocalBM25NVIDIAKnowledgeRetriever(self.corpus)).retrieve_for_query(
            run_id=run_id,
            query=query,
            top_k=self.lexical_top_k,
        )
        vector_retrieval = self.vector_store.retrieve_by_vector(
            self.embedding_client,
            run_id=run_id,
            corpus_version=self.corpus.corpus_version,
            gap_type=query.gap_type,
            opportunity_type=query.opportunity_type,
            description=query.description,
            startup_signals=query.startup_signals,
            query_terms=query.query_terms,
            top_k=self.vector_top_k,
            min_vector_score=self.min_vector_score,
        )
        return merge_nvidia_knowledge_retrievals_hybrid(
            lexical_retrieval,
            vector_retrieval,
            lexical_top_k=self.lexical_top_k,
            vector_top_k=self.vector_top_k,
            top_k=top_k,
            lexical_weight=self.lexical_weight,
            vector_weight=self.vector_weight,
            rrf_k=self.rrf_k,
        )

    def retrieve_for_gap(
        self,
        *,
        run_id: str,
        gap: TechnicalGap,
        startup_signals: tuple[str, ...],
        top_k: int,
    ) -> NVIDIAKnowledgeRetrieval:
        lexical_retrieval = (self.lexical_retriever or LocalBM25NVIDIAKnowledgeRetriever(self.corpus)).retrieve_for_gap(
            run_id=run_id,
            gap=gap,
            startup_signals=startup_signals,
            top_k=self.lexical_top_k,
        )
        vector_retrieval = self.vector_store.retrieve_by_vector(
            self.embedding_client,
            run_id=run_id,
            corpus_version=self.corpus.corpus_version,
            gap_type=gap.gap_type,
            description=gap.description,
            startup_signals=startup_signals,
            top_k=self.vector_top_k,
            min_vector_score=self.min_vector_score,
        )
        return merge_nvidia_knowledge_retrievals_hybrid(
            lexical_retrieval,
            vector_retrieval,
            lexical_top_k=self.lexical_top_k,
            vector_top_k=self.vector_top_k,
            top_k=top_k,
            lexical_weight=self.lexical_weight,
            vector_weight=self.vector_weight,
            rrf_k=self.rrf_k,
        )


@dataclass(frozen=True)
class RankBM25NVIDIAKnowledgeRetriever:
    """Optional rank-bm25 adapter that returns project-owned retrieval contracts."""

    corpus: NVIDIAKnowledgeCorpus
    bm25_factory: Callable[[list[list[str]]], object] | None = None

    def retrieve_for_query(
        self,
        *,
        run_id: str,
        query: NVIDIAKnowledgeQuery,
        top_k: int,
    ) -> NVIDIAKnowledgeRetrieval:
        return self._retrieve(run_id=run_id, query=query.query, top_k=top_k)

    def retrieve_for_gap(
        self,
        *,
        run_id: str,
        gap: TechnicalGap,
        startup_signals: tuple[str, ...],
        top_k: int,
    ) -> NVIDIAKnowledgeRetrieval:
        query = build_nvidia_knowledge_query(
            gap_type=gap.gap_type,
            description=gap.description,
            startup_signals=startup_signals,
        )
        return self._retrieve(run_id=run_id, query=query, top_k=top_k)

    def _retrieve(self, *, run_id: str, query: str, top_k: int) -> NVIDIAKnowledgeRetrieval:
        query_tokens = _lexical_tokens(query)
        if not self.corpus.chunks or not query_tokens:
            return NVIDIAKnowledgeRetrieval(
                schema_version="nvidia_knowledge.v1",
                run_id=run_id,
                corpus_version=self.corpus.corpus_version,
                query=query,
                results=(),
                documents=(),
            )

        tokenized_corpus = [
            list(_lexical_tokens(f"{chunk.topic.replace('_', ' ')} {chunk.text}"))
            for chunk in self.corpus.chunks
        ]
        bm25 = (self.bm25_factory or _load_rank_bm25_okapi())(tokenized_corpus)
        raw_scores = list(_rank_bm25_scores(bm25, query_tokens))
        documents_by_id = {document.document_id: document for document in self.corpus.documents}
        ranked_chunks = sorted(
            (
                (chunk, float(score))
                for chunk, score in zip(self.corpus.chunks, raw_scores, strict=True)
                if float(score) > 0
            ),
            key=lambda item: (-item[1], item[0].document_id, item[0].chunk_index, item[0].chunk_id),
        )

        results: list[RetrievedNVIDIAKnowledge] = []
        result_documents: dict[str, object] = {}
        for chunk, score in ranked_chunks[:top_k]:
            document = documents_by_id.get(chunk.document_id)
            if document is None:
                continue
            rounded_score = round(score, 6)
            result_documents[document.document_id] = document
            results.append(
                RetrievedNVIDIAKnowledge(
                    chunk=chunk,
                    citation=nvidia_citation_from_chunk(document, chunk),
                    score=rounded_score,
                    retrieval_strategy="rank_bm25_lexical",
                    rationale="Chunk topic and text matched the rank-bm25 lexical query.",
                    rank=len(results) + 1,
                    bm25_score=rounded_score,
                    index_parameters={
                        "library": "rank_bm25",
                        "implementation": "BM25Okapi",
                        "tokenizer": "normalize_text_regex_alnum",
                    },
                    ranking_strategy="rank_bm25.BM25Okapi",
                    tie_breakers=("bm25_score_desc", "document_id", "chunk_index", "chunk_id"),
                )
            )

        return NVIDIAKnowledgeRetrieval(
            schema_version="nvidia_knowledge.v1",
            run_id=run_id,
            corpus_version=self.corpus.corpus_version,
            query=query,
            results=tuple(results),
            documents=tuple(result_documents.values()),
        )


def _load_rank_bm25_okapi() -> Callable[[list[list[str]]], object]:
    try:
        from rank_bm25 import BM25Okapi  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("Install rank-bm25 to use RankBM25NVIDIAKnowledgeRetriever") from exc
    return BM25Okapi


def _rank_bm25_scores(bm25: object, query_tokens: tuple[str, ...]) -> tuple[float, ...]:
    get_scores = getattr(bm25, "get_scores", None)
    if not callable(get_scores):
        raise TypeError("rank_bm25_object_missing_get_scores")
    return tuple(float(score) for score in get_scores(list(query_tokens)))


def _lexical_tokens(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", normalize_text(value)))
