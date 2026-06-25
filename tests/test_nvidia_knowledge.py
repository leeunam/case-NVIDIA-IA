from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from nvidia_startup_intel.nvidia_knowledge import (
    NVIDIACitation,
    NVIDIAKnowledgeChunk,
    NVIDIAKnowledgeCorpus,
    NVIDIAKnowledgeDocument,
    NVIDIAKnowledgeRetrieval,
    RetrievedNVIDIAKnowledge,
    chunk_nvidia_knowledge_document,
    load_nvidia_knowledge_corpus,
    nvidia_citation_from_chunk,
    nvidia_knowledge_corpus_to_dict,
    nvidia_knowledge_retrieval_to_dict,
    retrieve_nvidia_knowledge,
    retrieve_nvidia_knowledge_by_gap,
    summarize_nvidia_retrieval_quality,
    validate_nvidia_knowledge_documents,
)


class NVIDIAKnowledgeSchemaTests(unittest.TestCase):
    def test_retrieval_serializes_citable_official_source_context(self) -> None:
        document = NVIDIAKnowledgeDocument(
            schema_version="nvidia_knowledge.v1",
            corpus_version="official-nvidia-fixture.v1",
            document_id="nvidia-inception",
            title="NVIDIA Inception",
            source_url="https://www.nvidia.com/en-us/startups/",
            source_type="official_nvidia_program_page",
            ingested_at="2026-06-23T00:00:00Z",
        )
        chunk = NVIDIAKnowledgeChunk(
            schema_version="nvidia_knowledge.v1",
            corpus_version="official-nvidia-fixture.v1",
            chunk_id="nvidia-inception:0",
            document_id="nvidia-inception",
            chunk_index=0,
            topic="inception",
            text="NVIDIA Inception is a program for startups.",
        )
        citation = NVIDIACitation(
            schema_version="nvidia_knowledge.v1",
            corpus_version="official-nvidia-fixture.v1",
            document_id="nvidia-inception",
            document_title="NVIDIA Inception",
            source_url="https://www.nvidia.com/en-us/startups/",
            source_type="official_nvidia_program_page",
            ingested_at="2026-06-23T00:00:00Z",
            chunk_id="nvidia-inception:0",
            excerpt="NVIDIA Inception is a program for startups.",
            chunk_index=0,
        )
        retrieval = NVIDIAKnowledgeRetrieval(
            schema_version="nvidia_knowledge.v1",
            run_id="run-001",
            corpus_version="official-nvidia-fixture.v1",
            query="go_to_market startup support",
            results=(
                RetrievedNVIDIAKnowledge(
                    chunk=chunk,
                    citation=citation,
                    score=1.25,
                    retrieval_strategy="fixture",
                    rationale="Program support matched the commercial opportunity.",
                    rank=1,
                    bm25_score=1.25,
                ),
            ),
            documents=(document,),
        )

        self.assertEqual(
            nvidia_knowledge_retrieval_to_dict(retrieval),
            {
                "schema_version": "nvidia_knowledge.v1",
                "run_id": "run-001",
                "corpus_version": "official-nvidia-fixture.v1",
                "query": "go_to_market startup support",
                "results": [
                    {
                        "chunk": {
                            "schema_version": "nvidia_knowledge.v1",
                            "corpus_version": "official-nvidia-fixture.v1",
                            "chunk_id": "nvidia-inception:0",
                            "document_id": "nvidia-inception",
                            "chunk_index": 0,
                            "topic": "inception",
                            "text": "NVIDIA Inception is a program for startups.",
                            "metadata": {},
                        },
                        "citation": {
                            "schema_version": "nvidia_knowledge.v1",
                            "corpus_version": "official-nvidia-fixture.v1",
                            "document_id": "nvidia-inception",
                            "document_title": "NVIDIA Inception",
                            "source_url": "https://www.nvidia.com/en-us/startups/",
                            "source_type": "official_nvidia_program_page",
                            "ingested_at": "2026-06-23T00:00:00Z",
                            "chunk_id": "nvidia-inception:0",
                            "excerpt": "NVIDIA Inception is a program for startups.",
                            "chunk_index": 0,
                        },
                        "score": 1.25,
                        "retrieval_strategy": "fixture",
                        "rationale": "Program support matched the commercial opportunity.",
                        "rank": 1,
                        "bm25_score": 1.25,
                        "vector_score": 0.0,
                        "hybrid_score": 0.0,
                        "embedding_metadata": {},
                        "index_parameters": {},
                        "ranking_strategy": "",
                        "tie_breakers": [],
                    }
                ],
                "documents": [
                    {
                        "schema_version": "nvidia_knowledge.v1",
                        "corpus_version": "official-nvidia-fixture.v1",
                        "document_id": "nvidia-inception",
                        "title": "NVIDIA Inception",
                        "source_url": "https://www.nvidia.com/en-us/startups/",
                        "source_type": "official_nvidia_program_page",
                        "ingested_at": "2026-06-23T00:00:00Z",
                        "metadata": {},
                    }
                ],
            },
        )

    def test_document_validation_marks_non_nvidia_sources_invalid(self) -> None:
        official_document = NVIDIAKnowledgeDocument(
            schema_version="nvidia_knowledge.v1",
            corpus_version="official-nvidia-fixture.v1",
            document_id="tensorrt-llm",
            title="TensorRT-LLM",
            source_url="https://developer.nvidia.com/tensorrt",
            source_type="official_nvidia_developer_page",
            ingested_at="2026-06-23T00:00:00Z",
        )
        non_official_document = NVIDIAKnowledgeDocument(
            schema_version="nvidia_knowledge.v1",
            corpus_version="official-nvidia-fixture.v1",
            document_id="third-party-summary",
            title="Third-party NVIDIA Summary",
            source_url="https://example.com/nvidia-summary",
            source_type="third_party_article",
            ingested_at="2026-06-23T00:00:00Z",
        )

        validation = validate_nvidia_knowledge_documents((official_document, non_official_document))

        self.assertFalse(validation.is_valid)
        self.assertEqual(validation.accepted_documents, (official_document,))
        self.assertEqual(len(validation.issues), 1)
        self.assertEqual(validation.issues[0].document_id, "third-party-summary")
        self.assertEqual(validation.issues[0].reason, "source_url_not_official_nvidia")

    def test_corpus_load_rejects_missing_source_reference_with_auditable_reason(self) -> None:
        corpus_payload = {
            "schema_version": "nvidia_knowledge.v1",
            "corpus_version": "official-nvidia-fixture.v1",
            "documents": [
                {
                    "schema_version": "nvidia_knowledge.v1",
                    "corpus_version": "official-nvidia-fixture.v1",
                    "document_id": "missing-origin",
                    "title": "Missing Origin",
                    "source_type": "official_nvidia_documentation",
                    "ingested_at": "2026-06-23T00:00:00Z",
                }
            ],
            "chunks": [],
        }

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json") as corpus_file:
            json.dump(corpus_payload, corpus_file)
            corpus_file.flush()

            with self.assertRaisesRegex(ValueError, "missing-origin:missing_source_url"):
                load_nvidia_knowledge_corpus(corpus_file.name)

    def test_citation_from_chunk_preserves_document_source_and_excerpt(self) -> None:
        document = NVIDIAKnowledgeDocument(
            schema_version="nvidia_knowledge.v1",
            corpus_version="official-nvidia-fixture.v1",
            document_id="nim",
            title="NVIDIA NIM",
            source_url="https://www.nvidia.com/en-us/ai/",
            source_type="official_nvidia_product_page",
            ingested_at="2026-06-23T00:00:00Z",
        )
        chunk = NVIDIAKnowledgeChunk(
            schema_version="nvidia_knowledge.v1",
            corpus_version="official-nvidia-fixture.v1",
            chunk_id="nim:2",
            document_id="nim",
            chunk_index=2,
            topic="model_serving",
            text="NVIDIA NIM provides optimized inference microservices.",
        )

        citation = nvidia_citation_from_chunk(document, chunk)

        self.assertEqual(citation.document_id, "nim")
        self.assertEqual(citation.document_title, "NVIDIA NIM")
        self.assertEqual(citation.source_url, "https://www.nvidia.com/en-us/ai/")
        self.assertEqual(citation.excerpt, "NVIDIA NIM provides optimized inference microservices.")
        self.assertEqual(citation.chunk_index, 2)

    def test_official_fixture_corpus_loads_with_four_recommendation_topics(self) -> None:
        fixture_path = Path(__file__).parent / "fixtures" / "nvidia_knowledge_official_fixture.json"

        corpus = load_nvidia_knowledge_corpus(fixture_path)

        topics = {chunk.topic for chunk in corpus.chunks}
        self.assertEqual(corpus.schema_version, "nvidia_knowledge.v1")
        self.assertEqual(corpus.corpus_version, "official-nvidia-fixture.v1")
        self.assertGreaterEqual(len(corpus.documents), 4)
        self.assertGreaterEqual(len(corpus.chunks), 4)
        self.assertTrue({"model_serving", "llm_customization", "data_acceleration", "computer_vision"} <= topics)
        self.assertTrue(validate_nvidia_knowledge_documents(corpus.documents).is_valid)

    def test_loaded_corpus_serializes_auditable_citation_metadata(self) -> None:
        fixture_path = Path(__file__).parent / "fixtures" / "nvidia_knowledge_official_fixture.json"
        corpus = load_nvidia_knowledge_corpus(fixture_path)

        serialized = nvidia_knowledge_corpus_to_dict(corpus)
        document = serialized["documents"][0]
        chunk = serialized["chunks"][0]
        citation = nvidia_citation_from_chunk(corpus.documents[0], corpus.chunks[0])

        json.dumps(serialized)
        self.assertEqual(document["metadata"]["official_source"], True)
        self.assertEqual(chunk["metadata"]["source_type"], "official_nvidia_developer_page")
        self.assertEqual(citation.schema_version, "nvidia_knowledge.v1")
        self.assertEqual(citation.corpus_version, "official-nvidia-fixture.v1")
        self.assertEqual(citation.chunk_id, "nvidia-nim-developers:0")
        self.assertEqual(citation.source_type, "official_nvidia_developer_page")
        self.assertEqual(citation.ingested_at, "2026-06-23T00:00:00Z")

    def test_chunking_discards_empty_blocks_and_preserves_stable_order(self) -> None:
        document = NVIDIAKnowledgeDocument(
            schema_version="nvidia_knowledge.v1",
            corpus_version="official-nvidia-fixture.v1",
            document_id="nvidia-nim-developers",
            title="NVIDIA NIM for Developers",
            source_url="https://developer.nvidia.com/nim",
            source_type="official_nvidia_developer_page",
            ingested_at="2026-06-23T00:00:00Z",
        )

        chunks = chunk_nvidia_knowledge_document(
            document,
            topic="model_serving",
            text_blocks=(
                "NIM provides GPU-accelerated inferencing microservices.",
                "   ",
                "NIM supports deployment across clouds and data centers.",
            ),
        )

        self.assertEqual(
            chunks,
            (
                NVIDIAKnowledgeChunk(
                    schema_version="nvidia_knowledge.v1",
                    corpus_version="official-nvidia-fixture.v1",
                    chunk_id="nvidia-nim-developers:0",
                    document_id="nvidia-nim-developers",
                    chunk_index=0,
                    topic="model_serving",
                    text="NIM provides GPU-accelerated inferencing microservices.",
                    metadata={
                        "document_title": "NVIDIA NIM for Developers",
                        "source_url": "https://developer.nvidia.com/nim",
                        "source_type": "official_nvidia_developer_page",
                        "ingested_at": "2026-06-23T00:00:00Z",
                    },
                ),
                NVIDIAKnowledgeChunk(
                    schema_version="nvidia_knowledge.v1",
                    corpus_version="official-nvidia-fixture.v1",
                    chunk_id="nvidia-nim-developers:1",
                    document_id="nvidia-nim-developers",
                    chunk_index=1,
                    topic="model_serving",
                    text="NIM supports deployment across clouds and data centers.",
                    metadata={
                        "document_title": "NVIDIA NIM for Developers",
                        "source_url": "https://developer.nvidia.com/nim",
                        "source_type": "official_nvidia_developer_page",
                        "ingested_at": "2026-06-23T00:00:00Z",
                    },
                ),
            ),
        )

    def test_bm25_retrieval_finds_citation_for_model_serving_gap(self) -> None:
        fixture_path = Path(__file__).parent / "fixtures" / "nvidia_knowledge_official_fixture.json"
        corpus = load_nvidia_knowledge_corpus(fixture_path)

        retrieval = retrieve_nvidia_knowledge_by_gap(
            corpus,
            run_id="run-001",
            gap_type="model_serving",
            description="Need lower latency inference and production model serving.",
            startup_signals=("inference", "latency"),
            top_k=2,
        )

        self.assertEqual(retrieval.schema_version, "nvidia_knowledge.v1")
        self.assertEqual(retrieval.run_id, "run-001")
        self.assertEqual(retrieval.corpus_version, "official-nvidia-fixture.v1")
        self.assertEqual(retrieval.results[0].chunk.topic, "model_serving")
        self.assertEqual(retrieval.results[0].citation.document_id, "nvidia-nim-developers")
        self.assertEqual(retrieval.results[0].rank, 1)
        self.assertEqual(retrieval.results[0].bm25_score, retrieval.results[0].score)
        self.assertEqual(retrieval.results[0].retrieval_strategy, "bm25_lexical")
        self.assertGreater(retrieval.results[0].score, 0)

    def test_bm25_retrieval_accepts_opportunity_type_and_query_terms(self) -> None:
        fixture_path = Path(__file__).parent / "fixtures" / "nvidia_knowledge_official_fixture.json"
        corpus = load_nvidia_knowledge_corpus(fixture_path)

        retrieval = retrieve_nvidia_knowledge(
            corpus,
            run_id="run-005",
            opportunity_type="startup_program",
            description="Need startup program support without cohort deadlines.",
            query_terms=("application fees", "deadlines", "cohorts"),
            top_k=1,
        )

        self.assertIn("startup program", retrieval.query)
        self.assertEqual(retrieval.results[0].citation.document_id, "nvidia-inception")

    def test_bm25_retrieval_orders_equal_scores_by_stable_metadata(self) -> None:
        document_b = NVIDIAKnowledgeDocument(
            schema_version="nvidia_knowledge.v1",
            corpus_version="test-corpus.v1",
            document_id="doc-b",
            title="Document B",
            source_url="https://developer.nvidia.com/doc-b",
            source_type="official_nvidia_developer_page",
            ingested_at="2026-06-23T00:00:00Z",
        )
        document_a = NVIDIAKnowledgeDocument(
            schema_version="nvidia_knowledge.v1",
            corpus_version="test-corpus.v1",
            document_id="doc-a",
            title="Document A",
            source_url="https://developer.nvidia.com/doc-a",
            source_type="official_nvidia_developer_page",
            ingested_at="2026-06-23T00:00:00Z",
        )
        corpus = NVIDIAKnowledgeCorpus(
            schema_version="nvidia_knowledge.v1",
            corpus_version="test-corpus.v1",
            documents=(document_b, document_a),
            chunks=(
                NVIDIAKnowledgeChunk(
                    schema_version="nvidia_knowledge.v1",
                    corpus_version="test-corpus.v1",
                    chunk_id="doc-b:0",
                    document_id="doc-b",
                    chunk_index=0,
                    topic="model_serving",
                    text="shared inference support",
                ),
                NVIDIAKnowledgeChunk(
                    schema_version="nvidia_knowledge.v1",
                    corpus_version="test-corpus.v1",
                    chunk_id="doc-a:0",
                    document_id="doc-a",
                    chunk_index=0,
                    topic="model_serving",
                    text="shared inference support",
                ),
            ),
        )

        retrieval = retrieve_nvidia_knowledge(
            corpus,
            run_id="run-006",
            query_terms=("shared inference support",),
            top_k=2,
        )

        self.assertEqual([result.citation.document_id for result in retrieval.results], ["doc-a", "doc-b"])
        self.assertEqual([result.rank for result in retrieval.results], [1, 2])

    def test_bm25_retrieval_deduplicates_duplicate_chunks(self) -> None:
        document = NVIDIAKnowledgeDocument(
            schema_version="nvidia_knowledge.v1",
            corpus_version="test-corpus.v1",
            document_id="doc-a",
            title="Document A",
            source_url="https://developer.nvidia.com/doc-a",
            source_type="official_nvidia_developer_page",
            ingested_at="2026-06-23T00:00:00Z",
        )
        chunk = NVIDIAKnowledgeChunk(
            schema_version="nvidia_knowledge.v1",
            corpus_version="test-corpus.v1",
            chunk_id="doc-a:0",
            document_id="doc-a",
            chunk_index=0,
            topic="model_serving",
            text="shared inference support",
        )
        corpus = NVIDIAKnowledgeCorpus(
            schema_version="nvidia_knowledge.v1",
            corpus_version="test-corpus.v1",
            documents=(document,),
            chunks=(chunk, chunk),
        )

        retrieval = retrieve_nvidia_knowledge(
            corpus,
            run_id="run-007",
            query_terms=("shared inference support",),
            top_k=3,
        )

        self.assertEqual(len(retrieval.results), 1)
        self.assertEqual(retrieval.results[0].citation.chunk_id, "doc-a:0")

    def test_bm25_retrieval_returns_no_results_when_gap_has_no_source_match(self) -> None:
        fixture_path = Path(__file__).parent / "fixtures" / "nvidia_knowledge_official_fixture.json"
        corpus = load_nvidia_knowledge_corpus(fixture_path)

        retrieval = retrieve_nvidia_knowledge_by_gap(
            corpus,
            run_id="run-002",
            gap_type="quantum_billing",
            description="Need tax invoicing workflow support.",
            startup_signals=("accounts payable",),
            top_k=2,
        )

        self.assertEqual(retrieval.results, ())
        self.assertEqual(retrieval.documents, ())

    def test_retrieval_quality_is_ready_when_result_has_official_citation(self) -> None:
        fixture_path = Path(__file__).parent / "fixtures" / "nvidia_knowledge_official_fixture.json"
        corpus = load_nvidia_knowledge_corpus(fixture_path)
        retrieval = retrieve_nvidia_knowledge_by_gap(
            corpus,
            run_id="run-003",
            gap_type="model_serving",
            description="Need production inference support.",
            startup_signals=("inference",),
            top_k=1,
        )

        quality = summarize_nvidia_retrieval_quality(retrieval)

        self.assertTrue(quality.has_sufficient_citation)
        self.assertEqual(quality.reasons, ("citation_sufficient",))

    def test_retrieval_quality_records_reason_when_no_citation_is_found(self) -> None:
        fixture_path = Path(__file__).parent / "fixtures" / "nvidia_knowledge_official_fixture.json"
        corpus = load_nvidia_knowledge_corpus(fixture_path)
        retrieval = retrieve_nvidia_knowledge_by_gap(
            corpus,
            run_id="run-004",
            gap_type="quantum_billing",
            description="Need tax invoicing workflow support.",
            startup_signals=("accounts payable",),
            top_k=1,
        )

        quality = summarize_nvidia_retrieval_quality(retrieval)

        self.assertFalse(quality.has_sufficient_citation)
        self.assertEqual(quality.reasons, ("no_retrieved_citation",))


if __name__ == "__main__":
    unittest.main()
