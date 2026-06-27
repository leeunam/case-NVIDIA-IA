"""NVIDIA Knowledge reranking adapter seam."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Protocol

from nvidia_startup_intel.nvidia_knowledge import (
    NVIDIACitation,
    NVIDIAKnowledgeChunk,
    NVIDIAKnowledgeRetrieval,
    RetrievedNVIDIAKnowledge,
)


RERANK_SCHEMA_VERSION = "nvidia_rerank.v1"


@dataclass(frozen=True)
class NVIDIARerankRequest:
    schema_version: str
    run_id: str
    corpus_version: str
    query: str
    candidates: tuple[RetrievedNVIDIAKnowledge, ...]
    candidate_top_k: int


@dataclass(frozen=True)
class RerankedNVIDIAKnowledge:
    chunk: NVIDIAKnowledgeChunk
    citation: NVIDIACitation
    original_score: float
    original_bm25_score: float
    original_vector_score: float
    original_hybrid_score: float
    original_retrieval_rank: int
    original_retrieval_strategy: str
    original_rationale: str
    rerank_score: float
    rerank_rank: int
    rerank_rationale: str


@dataclass(frozen=True)
class NVIDIARerankResult:
    schema_version: str
    run_id: str
    corpus_version: str
    query: str
    candidate_top_k: int
    results: tuple[RerankedNVIDIAKnowledge, ...]
    ranking_strategy: str
    audit_reasons: tuple[str, ...]


class NVIDIAReranker(Protocol):
    """Project-owned seam for future cross-encoder, LLM, or framework rerankers."""

    def rerank(self, request: NVIDIARerankRequest) -> NVIDIARerankResult: ...


@dataclass(frozen=True)
class SentenceTransformersCrossEncoderReranker:
    """Optional sentence-transformers cross-encoder adapter behind NVIDIAReranker."""

    model_name: str
    model_version: str = "unknown"
    cross_encoder: object | None = None

    def rerank(self, request: NVIDIARerankRequest) -> NVIDIARerankResult:
        model = self.cross_encoder or _load_sentence_transformers_cross_encoder(self.model_name)
        scores = _cross_encoder_scores(
            model,
            [(request.query, candidate.chunk.text) for candidate in request.candidates],
        )
        ranked = sorted(
            (
                _reranked_candidate(
                    candidate,
                    score=score,
                    rerank_rank=0,
                    rerank_rationale="Cross-encoder scored query and candidate chunk text.",
                )
                for candidate, score in zip(request.candidates, scores, strict=True)
            ),
            key=lambda result: (
                -result.rerank_score,
                result.original_retrieval_rank,
                result.chunk.document_id,
                result.chunk.chunk_index,
                result.chunk.chunk_id,
            ),
        )
        return NVIDIARerankResult(
            schema_version=RERANK_SCHEMA_VERSION,
            run_id=request.run_id,
            corpus_version=request.corpus_version,
            query=request.query,
            candidate_top_k=request.candidate_top_k,
            results=tuple(
                _with_rerank_rank(result, rerank_rank=rank)
                for rank, result in enumerate(ranked, start=1)
            ),
            ranking_strategy="sentence_transformers_cross_encoder_score_desc",
            audit_reasons=(
                "reranked_only_supplied_top_k_candidates",
                f"reranker_model:{self.model_name}",
                f"reranker_model_version:{self.model_version}",
            ),
        )


@dataclass(frozen=True)
class DeterministicTopKReranker:
    """Local reranker fake that only reorders the candidates provided in the request."""

    rerank_scores_by_chunk_id: Mapping[str, float] = field(default_factory=dict)

    def rerank(self, request: NVIDIARerankRequest) -> NVIDIARerankResult:
        ranked = sorted(
            (
                _reranked_candidate(
                    candidate,
                    score=float(self.rerank_scores_by_chunk_id.get(candidate.chunk.chunk_id, 0.0)),
                    rerank_rank=0,
                )
                for candidate in request.candidates
            ),
            key=lambda result: (
                -result.rerank_score,
                result.original_retrieval_rank,
                result.chunk.document_id,
                result.chunk.chunk_index,
                result.chunk.chunk_id,
            ),
        )
        return NVIDIARerankResult(
            schema_version=RERANK_SCHEMA_VERSION,
            run_id=request.run_id,
            corpus_version=request.corpus_version,
            query=request.query,
            candidate_top_k=request.candidate_top_k,
            results=tuple(
                _with_rerank_rank(result, rerank_rank=rank)
                for rank, result in enumerate(ranked, start=1)
            ),
            ranking_strategy="deterministic_fixture_score_desc",
            audit_reasons=("reranked_only_supplied_top_k_candidates",),
        )


def rerank_nvidia_retrieval(
    retrieval: NVIDIAKnowledgeRetrieval,
    reranker: NVIDIAReranker,
    *,
    candidate_top_k: int,
) -> NVIDIARerankResult:
    """Rerank only the top K retrieved candidates without creating new facts."""

    bounded_top_k = max(candidate_top_k, 0)
    request = NVIDIARerankRequest(
        schema_version=RERANK_SCHEMA_VERSION,
        run_id=retrieval.run_id,
        corpus_version=retrieval.corpus_version,
        query=retrieval.query,
        candidates=tuple(retrieval.results[:bounded_top_k]),
        candidate_top_k=bounded_top_k,
    )
    return _validated_rerank_result(reranker.rerank(request), request)


def nvidia_rerank_result_to_dict(result: NVIDIARerankResult) -> dict[str, object]:
    """Convert a reranking adapter result to JSON-serializable data."""

    return _to_plain_data(result)


def _load_sentence_transformers_cross_encoder(model_name: str) -> object:
    try:
        from sentence_transformers import CrossEncoder  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "Install sentence-transformers to use SentenceTransformersCrossEncoderReranker"
        ) from exc
    return CrossEncoder(model_name)


def _cross_encoder_scores(
    cross_encoder: object,
    pairs: list[tuple[str, str]],
) -> tuple[float, ...]:
    predict = getattr(cross_encoder, "predict", None)
    if not callable(predict):
        raise TypeError("cross_encoder_object_missing_predict")

    raw_scores = predict(pairs)
    if hasattr(raw_scores, "tolist"):
        raw_scores = raw_scores.tolist()
    scores = tuple(float(score) for score in raw_scores)
    if len(scores) != len(pairs):
        raise ValueError(f"cross_encoder_score_count_mismatch:expected_{len(pairs)}:actual_{len(scores)}")
    return scores


def _validated_rerank_result(
    result: NVIDIARerankResult,
    request: NVIDIARerankRequest,
) -> NVIDIARerankResult:
    candidates_by_chunk_id = {candidate.chunk.chunk_id: candidate for candidate in request.candidates}
    seen_chunk_ids: set[str] = set()

    for item in result.results:
        chunk_id = item.chunk.chunk_id
        if chunk_id not in candidates_by_chunk_id:
            raise ValueError(f"reranker_returned_unknown_chunk:{chunk_id}")
        if chunk_id in seen_chunk_ids:
            raise ValueError(f"reranker_returned_duplicate_chunk:{chunk_id}")
        seen_chunk_ids.add(chunk_id)

        candidate = candidates_by_chunk_id[chunk_id]
        if item.chunk != candidate.chunk or item.citation != candidate.citation:
            raise ValueError(f"reranker_changed_candidate_payload:{chunk_id}")
        if (
            item.original_score != candidate.score
            or item.original_bm25_score != candidate.bm25_score
            or item.original_vector_score != candidate.vector_score
            or item.original_hybrid_score != candidate.hybrid_score
            or item.original_retrieval_rank != candidate.rank
            or item.original_retrieval_strategy != candidate.retrieval_strategy
            or item.original_rationale != candidate.rationale
        ):
            raise ValueError(f"reranker_changed_original_retrieval_fields:{chunk_id}")

    return result


def _reranked_candidate(
    candidate: RetrievedNVIDIAKnowledge,
    *,
    score: float,
    rerank_rank: int,
    rerank_rationale: str = "deterministic_fixture_rerank_score",
) -> RerankedNVIDIAKnowledge:
    return RerankedNVIDIAKnowledge(
        chunk=candidate.chunk,
        citation=candidate.citation,
        original_score=candidate.score,
        original_bm25_score=candidate.bm25_score,
        original_vector_score=candidate.vector_score,
        original_hybrid_score=candidate.hybrid_score,
        original_retrieval_rank=candidate.rank,
        original_retrieval_strategy=candidate.retrieval_strategy,
        original_rationale=candidate.rationale,
        rerank_score=score,
        rerank_rank=rerank_rank,
        rerank_rationale=rerank_rationale,
    )


def _with_rerank_rank(
    result: RerankedNVIDIAKnowledge,
    *,
    rerank_rank: int,
) -> RerankedNVIDIAKnowledge:
    return RerankedNVIDIAKnowledge(
        chunk=result.chunk,
        citation=result.citation,
        original_score=result.original_score,
        original_bm25_score=result.original_bm25_score,
        original_vector_score=result.original_vector_score,
        original_hybrid_score=result.original_hybrid_score,
        original_retrieval_rank=result.original_retrieval_rank,
        original_retrieval_strategy=result.original_retrieval_strategy,
        original_rationale=result.original_rationale,
        rerank_score=result.rerank_score,
        rerank_rank=rerank_rank,
        rerank_rationale=result.rerank_rationale,
    )


def _to_plain_data(value: object) -> dict[str, object]:
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: _to_plain_value(getattr(value, item.name)) for item in fields(value)}
    raise TypeError(f"unsupported_rerank_serialization_type:{type(value).__name__}")


def _to_plain_value(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: _to_plain_value(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, dict):
        return {key: _to_plain_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain_value(item) for item in value]
    return value
