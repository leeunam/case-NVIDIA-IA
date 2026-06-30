from __future__ import annotations

import unittest

from nvidia_startup_intel.nvidia_embeddings import (
    DeterministicFakeEmbeddingClient,
    build_nvidia_embedding_index,
    retrieve_nvidia_knowledge_hybrid,
)
from nvidia_startup_intel.nvidia_knowledge import (
    NVIDIAKnowledgeChunk,
    NVIDIAKnowledgeCorpus,
    NVIDIAKnowledgeDocument,
    summarize_nvidia_retrieval_quality,
)


class NVIDIAHybridRetrievalTests(unittest.TestCase):
    def test_hybrid_retrieval_can_rank_a_lexical_winner_first(self) -> None:
        corpus = _hybrid_test_corpus()
        client = DeterministicFakeEmbeddingClient(dimension=6)
        index = build_nvidia_embedding_index(corpus, client)

        retrieval = retrieve_nvidia_knowledge_hybrid(
            corpus,
            index,
            client,
            run_id="run-hybrid-001",
            normalized_query="proprietarytoken inference",
            lexical_top_k=2,
            vector_top_k=1,
            top_k=2,
            lexical_weight=5.0,
            vector_weight=1.0,
            rrf_k=0,
        )

        self.assertEqual(retrieval.schema_version, "nvidia_knowledge.v1")
        self.assertEqual(retrieval.run_id, "run-hybrid-001")
        self.assertEqual(retrieval.corpus_version, "test-corpus.v1")
        self.assertEqual([result.chunk.chunk_id for result in retrieval.results], ["doc-b:0", "doc-a:0"])
        self.assertEqual([result.rank for result in retrieval.results], [1, 2])

        top_result = retrieval.results[0]
        self.assertEqual(top_result.retrieval_strategy, "hybrid_bm25_vector")
        self.assertEqual(top_result.ranking_strategy, "reciprocal_rank_fusion")
        self.assertEqual(top_result.score, top_result.hybrid_score)
        self.assertGreater(top_result.hybrid_score, 0.0)
        self.assertGreater(top_result.bm25_score, 0.0)
        self.assertEqual(top_result.vector_score, 0.0)
        self.assertEqual(top_result.index_parameters["lexical_weight"], 5.0)
        self.assertEqual(top_result.index_parameters["vector_weight"], 1.0)
        self.assertEqual(top_result.index_parameters["rrf_k"], 0)
        self.assertEqual(top_result.index_parameters["fusion_config_version"], "nvidia_hybrid_retrieval.v1")
        self.assertEqual(top_result.index_parameters["lexical_top_k"], 2)
        self.assertEqual(top_result.index_parameters["vector_top_k"], 1)
        self.assertEqual(top_result.index_parameters["source_ranks"], {"bm25_lexical": 1})
        self.assertEqual(
            top_result.tie_breakers,
            ("hybrid_score_desc", "document_id", "chunk_index", "chunk_id"),
        )

    def test_hybrid_retrieval_can_rank_a_vector_winner_first(self) -> None:
        corpus = _hybrid_test_corpus()
        client = DeterministicFakeEmbeddingClient(dimension=6)
        index = build_nvidia_embedding_index(corpus, client)

        retrieval = retrieve_nvidia_knowledge_hybrid(
            corpus,
            index,
            client,
            run_id="run-hybrid-002",
            normalized_query="proprietarytoken inference",
            lexical_top_k=2,
            vector_top_k=1,
            top_k=2,
            lexical_weight=1.0,
            vector_weight=5.0,
            rrf_k=0,
        )

        self.assertEqual([result.chunk.chunk_id for result in retrieval.results], ["doc-a:0", "doc-b:0"])
        top_result = retrieval.results[0]
        self.assertGreater(top_result.bm25_score, 0.0)
        self.assertGreater(top_result.vector_score, 0.0)
        self.assertGreater(top_result.hybrid_score, retrieval.results[1].hybrid_score)
        self.assertEqual(top_result.index_parameters["source_ranks"], {"bm25_lexical": 2, "vector_semantic": 1})
        self.assertEqual(top_result.embedding_metadata["embedding_model"], "deterministic-fake-embedding")

    def test_hybrid_retrieval_merges_duplicate_chunks_with_original_scores_and_ranks(self) -> None:
        corpus = _hybrid_test_corpus()
        client = DeterministicFakeEmbeddingClient(dimension=6)
        index = build_nvidia_embedding_index(corpus, client)

        retrieval = retrieve_nvidia_knowledge_hybrid(
            corpus,
            index,
            client,
            run_id="run-hybrid-003",
            normalized_query="inference microservices",
            lexical_top_k=1,
            vector_top_k=1,
            top_k=3,
            rrf_k=0,
        )

        self.assertEqual(len(retrieval.results), 1)
        result = retrieval.results[0]
        self.assertEqual(result.chunk.chunk_id, "doc-a:0")
        self.assertGreater(result.bm25_score, 0.0)
        self.assertGreater(result.vector_score, 0.0)
        self.assertEqual(result.index_parameters["source_ranks"], {"bm25_lexical": 1, "vector_semantic": 1})
        self.assertEqual(result.hybrid_score, 2.0)
        self.assertEqual(result.rank, 1)

    def test_hybrid_retrieval_quality_reports_no_sufficient_support(self) -> None:
        corpus = _hybrid_test_corpus()
        client = DeterministicFakeEmbeddingClient(dimension=6)
        index = build_nvidia_embedding_index(corpus, client)

        retrieval = retrieve_nvidia_knowledge_hybrid(
            corpus,
            index,
            client,
            run_id="run-hybrid-004",
            normalized_query="tax invoicing accounts payable",
            lexical_top_k=2,
            vector_top_k=2,
            top_k=2,
        )

        self.assertEqual(retrieval.results, ())
        self.assertEqual(retrieval.documents, ())
        quality = summarize_nvidia_retrieval_quality(retrieval)
        self.assertFalse(quality.has_sufficient_citation)
        self.assertEqual(quality.reasons, ("no_retrieved_citation",))

    def test_hybrid_retrieval_orders_equal_hybrid_scores_by_stable_metadata(self) -> None:
        corpus = _hybrid_test_corpus()
        client = DeterministicFakeEmbeddingClient(dimension=6)
        index = build_nvidia_embedding_index(corpus, client)

        retrieval = retrieve_nvidia_knowledge_hybrid(
            corpus,
            index,
            client,
            run_id="run-hybrid-005",
            normalized_query="proprietarytoken inference",
            lexical_top_k=1,
            vector_top_k=1,
            top_k=2,
            lexical_weight=1.0,
            vector_weight=1.0,
            rrf_k=0,
        )

        self.assertEqual([result.chunk.chunk_id for result in retrieval.results], ["doc-a:0", "doc-b:0"])
        self.assertEqual(retrieval.results[0].hybrid_score, retrieval.results[1].hybrid_score)
        self.assertEqual(
            retrieval.results[0].tie_breakers,
            ("hybrid_score_desc", "document_id", "chunk_index", "chunk_id"),
        )


def _hybrid_test_corpus() -> NVIDIAKnowledgeCorpus:
    document_a = NVIDIAKnowledgeDocument(
        schema_version="nvidia_knowledge.v1",
        corpus_version="test-corpus.v1",
        document_id="doc-a",
        title="Document A",
        source_url="https://developer.nvidia.com/doc-a",
        source_type="official_nvidia_developer_page",
        ingested_at="2026-06-23T00:00:00Z",
    )
    document_b = NVIDIAKnowledgeDocument(
        schema_version="nvidia_knowledge.v1",
        corpus_version="test-corpus.v1",
        document_id="doc-b",
        title="Document B",
        source_url="https://developer.nvidia.com/doc-b",
        source_type="official_nvidia_developer_page",
        ingested_at="2026-06-23T00:00:00Z",
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
                text="proprietarytoken proprietarytoken deployment guide.",
            ),
        ),
    )


if __name__ == "__main__":
    unittest.main()
