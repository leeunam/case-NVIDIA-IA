"""Framework adapter contracts for future RAG and LLM integrations.

Adapters convert framework/provider objects into project-owned domain
contracts before Knowledge, Recommendation, Workflow, or Briefing consume
them. The default local path remains deterministic and framework-free.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Protocol

from nvidia_startup_intel.ai_native_assessment import TechnicalGap
from nvidia_startup_intel.nvidia_knowledge import (
    NVIDIACitation,
    NVIDIAKnowledgeChunk,
    NVIDIAKnowledgeCorpus,
    NVIDIAKnowledgeRetrieval,
    RetrievedNVIDIAKnowledge,
    retrieve_nvidia_knowledge_by_gap,
)


LLM_REQUEST_SCHEMA_VERSION = "llm_generation_request.v1"
LLM_RESPONSE_SCHEMA_VERSION = "llm_generation_response.v1"
RERANK_SCHEMA_VERSION = "nvidia_rerank.v1"


class NVIDIAKnowledgeRetriever(Protocol):
    """Project-owned retrieval seam for LlamaIndex, LangChain, or local BM25 adapters."""

    def retrieve_for_gap(
        self,
        *,
        run_id: str,
        gap: TechnicalGap,
        startup_signals: tuple[str, ...],
        top_k: int,
    ) -> NVIDIAKnowledgeRetrieval: ...


@dataclass(frozen=True)
class LocalBM25NVIDIAKnowledgeRetriever:
    """Adapter over the existing deterministic NVIDIA Knowledge retrieval contract."""

    corpus: NVIDIAKnowledgeCorpus

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
class LLMGenerationRequest:
    schema_version: str
    purpose: str
    system_prompt: str
    user_prompt: str
    structured_output_schema: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMGenerationResponse:
    schema_version: str
    request_purpose: str
    provider: str
    model: str
    model_version: str
    content: str
    structured_output_schema: str
    finish_reason: str
    usage: dict[str, object] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)


class LLMClient(Protocol):
    """Project-owned seam for LangChain, LiteLLM, local, or provider LLM clients."""

    def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse: ...


@dataclass(frozen=True)
class DeterministicFakeLLMClient:
    """Local fake for contract tests; it does not call LangChain, LiteLLM, or a model."""

    provider: str = "local_fake"
    model: str = "deterministic-fake-llm"
    model_version: str = "v1"

    def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        return LLMGenerationResponse(
            schema_version=LLM_RESPONSE_SCHEMA_VERSION,
            request_purpose=request.purpose,
            provider=self.provider,
            model=self.model,
            model_version=self.model_version,
            content=(
                f"deterministic_response:{request.purpose}:"
                f"{request.structured_output_schema}"
            ),
            structured_output_schema=request.structured_output_schema,
            finish_reason="stop",
            usage={
                "system_prompt_characters": len(request.system_prompt),
                "user_prompt_characters": len(request.user_prompt),
            },
            metadata=dict(request.metadata),
        )


def llm_generation_response_to_dict(response: LLMGenerationResponse) -> dict[str, object]:
    """Convert an LLM adapter response to JSON-serializable data."""

    return _to_plain_data(response)


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
    return reranker.rerank(request)


def nvidia_rerank_result_to_dict(result: NVIDIARerankResult) -> dict[str, object]:
    """Convert a reranking adapter result to JSON-serializable data."""

    return _to_plain_data(result)


def _reranked_candidate(
    candidate: RetrievedNVIDIAKnowledge,
    *,
    score: float,
    rerank_rank: int,
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
        rerank_rationale="deterministic_fixture_rerank_score",
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


def _to_plain_data(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: _to_plain_data(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, dict):
        return {key: _to_plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain_data(item) for item in value]
    return value
