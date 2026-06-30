from __future__ import annotations

import unittest

from nvidia_startup_intel.downstream_metrics import (
    RetrievalMetricExpectation,
    compare_rerank_retrieval_quality,
    rerank_quality_comparison_to_dict,
)
from nvidia_startup_intel.nvidia_reranking import (
    DeterministicTopKReranker,
    NVIDIARerankRequest,
    NVIDIARerankResult,
    RerankedNVIDIAKnowledge,
    SentenceTransformersCrossEncoderReranker,
    rerank_nvidia_retrieval,
)
from nvidia_startup_intel.nvidia_knowledge import (
    NVIDIACitation,
    NVIDIAKnowledgeChunk,
    NVIDIAKnowledgeCorpus,
    NVIDIAKnowledgeDocument,
    NVIDIAKnowledgeRetrieval,
    RetrievedNVIDIAKnowledge,
    retrieve_nvidia_knowledge,
)


class NVIDIARerankingTests(unittest.TestCase):
    def test_cross_encoder_reranker_reorders_supplied_top_k_and_preserves_audit_fields(self) -> None:
        corpus = _rerank_test_corpus()
        retrieval = _hybrid_rerank_retrieval(
            corpus,
            run_id="run-rerank-001",
            query="inference deployment",
        )
        original_by_chunk_id = {result.chunk.chunk_id: result for result in retrieval.results}
        reranker = SentenceTransformersCrossEncoderReranker(
            model_name="local-cross-encoder",
            model_version="fixture-v1",
            cross_encoder=_CrossEncoderLikeModel(
                scores_by_chunk_text={
                    "NVIDIA NIM provides inference microservices.": 0.21,
                    "NVIDIA Triton deployment guide for optimized inference.": 0.97,
                }
            ),
        )

        result = rerank_nvidia_retrieval(retrieval, reranker, candidate_top_k=2)

        self.assertEqual(result.schema_version, "nvidia_rerank.v1")
        self.assertEqual(result.run_id, "run-rerank-001")
        self.assertEqual(result.corpus_version, "test-corpus.v1")
        self.assertEqual(result.candidate_top_k, 2)
        self.assertEqual(result.ranking_strategy, "sentence_transformers_cross_encoder_score_desc")
        self.assertEqual(result.reranker_model_name, "local-cross-encoder")
        self.assertEqual(result.reranker_model_version, "fixture-v1")
        self.assertEqual(
            result.reranker_parameters,
            {
                "provider": "sentence-transformers",
                "candidate_top_k": 2,
                "score_function": "cross_encoder_predict",
                "tie_breakers": (
                    "rerank_score_desc",
                    "original_retrieval_rank",
                    "document_id",
                    "chunk_index",
                    "chunk_id",
                ),
            },
        )
        self.assertIn("reranked_only_supplied_top_k_candidates", result.audit_reasons)
        self.assertEqual([item.chunk.chunk_id for item in result.results], ["doc-b:0", "doc-a:0"])
        self.assertEqual([item.rerank_rank for item in result.results], [1, 2])

        top = result.results[0]
        original = original_by_chunk_id[top.chunk.chunk_id]
        self.assertEqual(top.citation, original.citation)
        self.assertEqual(top.original_score, original.score)
        self.assertEqual(top.original_retrieval_rank, original.rank)
        self.assertEqual(top.original_retrieval_strategy, original.retrieval_strategy)
        self.assertEqual(top.original_bm25_score, original.bm25_score)
        self.assertEqual(top.original_vector_score, original.vector_score)
        self.assertEqual(top.original_hybrid_score, original.hybrid_score)
        self.assertEqual(top.original_rationale, original.rationale)
        self.assertEqual(top.rerank_score, 0.97)
        self.assertEqual(top.rerank_rationale, "Cross-encoder scored query and candidate chunk text.")

    def test_reranking_rejects_adapter_result_that_introduces_a_new_chunk(self) -> None:
        corpus = _rerank_test_corpus()
        retrieval = _hybrid_rerank_retrieval(
            corpus,
            run_id="run-rerank-002",
            query="inference deployment",
        )

        with self.assertRaisesRegex(ValueError, "reranker_returned_unknown_chunk:doc-c:0"):
            rerank_nvidia_retrieval(retrieval, _InventingReranker(), candidate_top_k=1)

    def test_reranking_rejects_non_hybrid_candidate_top_k(self) -> None:
        corpus = _rerank_test_corpus()
        retrieval = retrieve_nvidia_knowledge(
            corpus,
            run_id="run-rerank-non-hybrid",
            description="inference deployment",
            top_k=1,
        )

        with self.assertRaisesRegex(
            ValueError,
            "reranker_requires_hybrid_candidate_top_k:bm25_lexical",
        ):
            rerank_nvidia_retrieval(
                retrieval,
                DeterministicTopKReranker(),
                candidate_top_k=1,
            )

    def test_rerank_metrics_compare_retrieval_quality_before_and_after_reranking(self) -> None:
        corpus = _rerank_test_corpus()
        retrieval = _hybrid_rerank_retrieval(
            corpus,
            run_id="run-rerank-003",
            query="inference",
        )
        self.assertEqual([item.chunk.chunk_id for item in retrieval.results], ["doc-a:0", "doc-b:0"])
        rerank_result = rerank_nvidia_retrieval(
            retrieval,
            SentenceTransformersCrossEncoderReranker(
                model_name="local-cross-encoder",
                model_version="fixture-v1",
                cross_encoder=_CrossEncoderLikeModel(
                    scores_by_chunk_text={
                        "NVIDIA NIM provides inference microservices.": 0.21,
                        "NVIDIA Triton deployment guide for optimized inference.": 0.97,
                    }
                ),
            ),
            candidate_top_k=2,
        )

        comparison = compare_rerank_retrieval_quality(
            run_id="run-rerank-003",
            baseline_retrievals=(retrieval,),
            rerank_results=(rerank_result,),
            expectations=(
                RetrievalMetricExpectation(
                    expectation_id="model-serving-triton",
                    target_type="technical_gap",
                    target="model_serving",
                    expected_chunk_ids=("doc-b:0",),
                ),
            ),
        )

        self.assertEqual(comparison.schema_version, "downstream_metrics.v1")
        self.assertEqual(comparison.rerank_ranking_strategy, "sentence_transformers_cross_encoder_score_desc")
        self.assertEqual(comparison.before.recall, 1.0)
        self.assertEqual(comparison.after.recall, 1.0)
        self.assertEqual(comparison.before.precision, 0.5)
        self.assertEqual(comparison.after.precision, 0.5)
        self.assertEqual(comparison.before_top_1_expected_count, 0)
        self.assertEqual(comparison.after_top_1_expected_count, 1)
        self.assertEqual(comparison.top_1_expected_delta, 1)
        self.assertEqual(comparison.f1_delta, 0.0)
        self.assertEqual(
            rerank_quality_comparison_to_dict(comparison)["after"]["cases"][0]["retrieved_chunk_ids"][0],
            "doc-b:0",
        )


def _rerank_test_corpus() -> NVIDIAKnowledgeCorpus:
    document_a = NVIDIAKnowledgeDocument(
        schema_version="nvidia_knowledge.v1",
        corpus_version="test-corpus.v1",
        document_id="doc-a",
        title="NVIDIA NIM",
        source_url="https://developer.nvidia.com/nim",
        source_type="official_nvidia_developer_page",
        ingested_at="2026-06-26T00:00:00Z",
    )
    document_b = NVIDIAKnowledgeDocument(
        schema_version="nvidia_knowledge.v1",
        corpus_version="test-corpus.v1",
        document_id="doc-b",
        title="NVIDIA Triton",
        source_url="https://developer.nvidia.com/triton-inference-server",
        source_type="official_nvidia_developer_page",
        ingested_at="2026-06-26T00:00:00Z",
    )
    return NVIDIAKnowledgeCorpus(
        schema_version="nvidia_knowledge.v1",
        corpus_version="test-corpus.v1",
        documents=(document_a, document_b),
        chunks=(
            NVIDIAKnowledgeChunk(
                schema_version="nvidia_knowledge.v1",
                corpus_version="test-corpus.v1",
                chunk_id="doc-a:0",
                document_id="doc-a",
                chunk_index=0,
                topic="model_serving",
                text="NVIDIA NIM provides inference microservices.",
            ),
            NVIDIAKnowledgeChunk(
                schema_version="nvidia_knowledge.v1",
                corpus_version="test-corpus.v1",
                chunk_id="doc-b:0",
                document_id="doc-b",
                chunk_index=0,
                topic="model_serving",
                text="NVIDIA Triton deployment guide for optimized inference.",
            ),
        ),
    )


def _hybrid_rerank_retrieval(
    corpus: NVIDIAKnowledgeCorpus,
    *,
    run_id: str,
    query: str,
) -> NVIDIAKnowledgeRetrieval:
    documents_by_id = {document.document_id: document for document in corpus.documents}
    results: list[RetrievedNVIDIAKnowledge] = []
    for rank, chunk in enumerate(corpus.chunks, start=1):
        document = documents_by_id[chunk.document_id]
        hybrid_score = round(1.0 - rank / 10, 6)
        results.append(
            RetrievedNVIDIAKnowledge(
                chunk=chunk,
                citation=NVIDIACitation(
                    schema_version="nvidia_knowledge.v1",
                    corpus_version=corpus.corpus_version,
                    document_id=document.document_id,
                    document_title=document.title,
                    source_url=document.source_url,
                    source_type=document.source_type,
                    ingested_at=document.ingested_at,
                    chunk_id=chunk.chunk_id,
                    excerpt=chunk.text,
                    chunk_index=chunk.chunk_index,
                ),
                score=hybrid_score,
                retrieval_strategy="hybrid_bm25_vector",
                rationale="Hybrid BM25/vector fixture candidate.",
                rank=rank,
                bm25_score=round(hybrid_score / 2, 6),
                vector_score=round(hybrid_score / 2, 6),
                hybrid_score=hybrid_score,
                index_parameters={"fusion_config_version": "nvidia_hybrid_retrieval.v1"},
                ranking_strategy="reciprocal_rank_fusion",
                tie_breakers=("hybrid_score_desc", "document_id", "chunk_index", "chunk_id"),
            )
        )

    return NVIDIAKnowledgeRetrieval(
        schema_version="nvidia_knowledge.v1",
        run_id=run_id,
        corpus_version=corpus.corpus_version,
        query=query,
        results=tuple(results),
        documents=corpus.documents,
    )


class _CrossEncoderLikeModel:
    def __init__(self, *, scores_by_chunk_text: dict[str, float]) -> None:
        self._scores_by_chunk_text = scores_by_chunk_text

    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        return [self._scores_by_chunk_text[candidate_text] for _query, candidate_text in pairs]


class _InventingReranker:
    def rerank(self, request: NVIDIARerankRequest) -> NVIDIARerankResult:
        chunk = NVIDIAKnowledgeChunk(
            schema_version="nvidia_knowledge.v1",
            corpus_version=request.corpus_version,
            chunk_id="doc-c:0",
            document_id="doc-c",
            chunk_index=0,
            topic="model_serving",
            text="Invented NVIDIA fact.",
        )
        citation = NVIDIACitation(
            schema_version="nvidia_knowledge.v1",
            corpus_version=request.corpus_version,
            document_id="doc-c",
            document_title="Invented Document",
            source_url="https://developer.nvidia.com/invented",
            source_type="official_nvidia_developer_page",
            ingested_at="2026-06-26T00:00:00Z",
            chunk_id="doc-c:0",
            excerpt="Invented NVIDIA fact.",
            chunk_index=0,
        )
        return NVIDIARerankResult(
            schema_version="nvidia_rerank.v1",
            run_id=request.run_id,
            corpus_version=request.corpus_version,
            query=request.query,
            candidate_top_k=request.candidate_top_k,
            results=(
                RerankedNVIDIAKnowledge(
                    chunk=chunk,
                    citation=citation,
                    original_score=1.0,
                    original_bm25_score=1.0,
                    original_vector_score=0.0,
                    original_hybrid_score=0.0,
                    original_retrieval_rank=1,
                    original_retrieval_strategy="bm25_lexical",
                    original_rationale="Invented by bad adapter.",
                    rerank_score=1.0,
                    rerank_rank=1,
                    rerank_rationale="Invented by bad adapter.",
                ),
            ),
            ranking_strategy="bad_adapter",
            audit_reasons=("bad_adapter_generated_new_chunk",),
        )


if __name__ == "__main__":
    unittest.main()
