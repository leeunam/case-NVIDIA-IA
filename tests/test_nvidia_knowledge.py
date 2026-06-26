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
    nvidia_stack_profiles_from_corpus,
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

    def test_document_validation_rejects_unsupported_official_source_type(self) -> None:
        unsupported_document = NVIDIAKnowledgeDocument(
            schema_version="nvidia_knowledge.v1",
            corpus_version="official-nvidia-fixture.v1",
            document_id="nvidia-community-summary",
            title="NVIDIA Community Summary",
            source_url="https://developer.nvidia.com/community-summary",
            source_type="community_summary",
            ingested_at="2026-06-23T00:00:00Z",
        )

        validation = validate_nvidia_knowledge_documents((unsupported_document,))

        self.assertFalse(validation.is_valid)
        self.assertEqual(validation.accepted_documents, ())
        self.assertEqual(len(validation.issues), 1)
        self.assertEqual(validation.issues[0].document_id, "nvidia-community-summary")
        self.assertEqual(validation.issues[0].reason, "unsupported_source_type")

    def test_document_validation_accepts_curated_nvidia_ecosystem_sources(self) -> None:
        documents = (
            NVIDIAKnowledgeDocument(
                schema_version="nvidia_knowledge.v1",
                corpus_version="official-nvidia-fixture.v1",
                document_id="nemo-guardrails",
                title="NeMo Guardrails",
                source_url="https://github.com/NVIDIA/NeMo-Guardrails",
                source_type="official_nvidia_code_repository",
                ingested_at="2026-06-23T00:00:00Z",
            ),
            NVIDIAKnowledgeDocument(
                schema_version="nvidia_knowledge.v1",
                corpus_version="official-nvidia-fixture.v1",
                document_id="rapids",
                title="NVIDIA RAPIDS",
                source_url="https://rapids.ai/",
                source_type="official_nvidia_project_page",
                ingested_at="2026-06-23T00:00:00Z",
            ),
            NVIDIAKnowledgeDocument(
                schema_version="nvidia_knowledge.v1",
                corpus_version="official-nvidia-fixture.v1",
                document_id="inception-benefits-video",
                title="NVIDIA Inception Benefits",
                source_url="https://www.youtube.com/live/fWfkE6cibwQ",
                source_type="official_nvidia_video",
                ingested_at="2026-06-23T00:00:00Z",
            ),
        )

        validation = validate_nvidia_knowledge_documents(documents)

        self.assertTrue(validation.is_valid)
        self.assertEqual(validation.accepted_documents, documents)
        self.assertEqual(validation.issues, ())

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

    def test_official_fixture_exposes_structured_stack_profiles(self) -> None:
        fixture_path = Path(__file__).parent / "fixtures" / "nvidia_knowledge_official_fixture.json"
        corpus = load_nvidia_knowledge_corpus(fixture_path)

        profiles = nvidia_stack_profiles_from_corpus(corpus)

        profiles_by_topic = {profile.topic: profile for profile in profiles}
        profiles_by_stack_name = {profile.stack_name: profile for profile in profiles}
        self.assertTrue(
            {
                "model_serving",
                "llm_customization",
                "data_acceleration",
                "computer_vision",
                "voice_ai",
                "robotics_simulation",
                "healthcare_ai",
                "cybersecurity_ai",
                "startup_program",
            }
            <= set(profiles_by_topic)
        )

        nim_profile = profiles_by_stack_name["NVIDIA NIM"]
        self.assertEqual(nim_profile.schema_version, "nvidia_knowledge.v1")
        self.assertEqual(nim_profile.corpus_version, "official-nvidia-fixture.v1")
        self.assertEqual(nim_profile.stack_name, "NVIDIA NIM")
        self.assertEqual(
            nim_profile.source_url,
            "https://www.nvidia.com/en-us/ai-data-science/products/nim-microservices/",
        )
        self.assertEqual(nim_profile.source_type, "official_nvidia_product_page")
        self.assertIn("model_serving", nim_profile.supported_gap_types)
        self.assertIn("inference", nim_profile.categories)
        self.assertIn("production model serving", nim_profile.use_cases)
        self.assertTrue(nim_profile.brief_description)
        self.assertTrue(nim_profile.technical_description)
        self.assertIn("nvidia-nim-developers:0", nim_profile.citation_chunk_ids)

    def test_official_fixture_includes_requested_nvidia_stack_sources(self) -> None:
        fixture_path = Path(__file__).parent / "fixtures" / "nvidia_knowledge_official_fixture.json"
        corpus = load_nvidia_knowledge_corpus(fixture_path)

        profiles = nvidia_stack_profiles_from_corpus(corpus)
        sources_by_stack = {profile.stack_name: profile.source_url for profile in profiles}

        expected_sources = {
            "NVIDIA Inception": "https://www.nvidia.com/en-us/startups/",
            "NVIDIA NIM": "https://www.nvidia.com/en-us/ai-data-science/products/nim-microservices/",
            "NVIDIA API Catalog": "https://build.nvidia.com/",
            "NVIDIA NeMo": "https://www.nvidia.com/en-us/ai-data-science/products/nemo/",
            "NeMo Guardrails": "https://github.com/NVIDIA/NeMo-Guardrails",
            "NVIDIA Triton Inference Server": "https://developer.nvidia.com/triton-inference-server",
            "TensorRT-LLM": "https://github.com/NVIDIA/TensorRT-LLM",
            "NVIDIA RAPIDS": "https://rapids.ai/",
            "cuDF": "https://docs.rapids.ai/api/cudf/stable/",
            "cuML": "https://docs.rapids.ai/api/cuml/stable/",
            "CUDA Toolkit": "https://developer.nvidia.com/cuda-toolkit",
            "NVIDIA Riva": "https://developer.nvidia.com/riva",
            "NVIDIA Omniverse": "https://www.nvidia.com/en-us/omniverse/",
            "NVIDIA Isaac": "https://developer.nvidia.com/isaac",
            "NVIDIA Clara": "https://www.nvidia.com/en-us/clara/",
            "NVIDIA Morpheus": "https://developer.nvidia.com/morpheus-cybersecurity",
            "NVIDIA AI Enterprise": "https://www.nvidia.com/en-us/data-center/products/ai-enterprise/",
            "NVIDIA AI 5-Layer Cake": "https://blogs.nvidia.com/blog/ai-5-layer-cake/",
            "NVIDIA Technology Playlist": "https://youtube.com/playlist?list=PLBaUJRFQ-j_WJZdZfFNsgUWDWF1Ldjp_X",
            "NVIDIA Startup Community": "https://youtu.be/NmZDQSdUVUQ",
            "NVIDIA Inception Benefits": "https://www.youtube.com/live/fWfkE6cibwQ",
        }

        for stack_name, source_url in expected_sources.items():
            with self.subTest(stack_name=stack_name):
                self.assertEqual(sources_by_stack[stack_name], source_url)

    def test_loaded_corpus_serializes_auditable_citation_metadata(self) -> None:
        fixture_path = Path(__file__).parent / "fixtures" / "nvidia_knowledge_official_fixture.json"
        corpus = load_nvidia_knowledge_corpus(fixture_path)

        serialized = nvidia_knowledge_corpus_to_dict(corpus)
        document = serialized["documents"][0]
        chunk = serialized["chunks"][0]
        citation = nvidia_citation_from_chunk(corpus.documents[0], corpus.chunks[0])

        json.dumps(serialized)
        self.assertEqual(document["metadata"]["official_source"], True)
        self.assertEqual(chunk["metadata"]["source_type"], "official_nvidia_product_page")
        self.assertEqual(citation.schema_version, "nvidia_knowledge.v1")
        self.assertEqual(citation.corpus_version, "official-nvidia-fixture.v1")
        self.assertEqual(citation.chunk_id, "nvidia-nim-developers:0")
        self.assertEqual(citation.source_type, "official_nvidia_product_page")
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

    def test_bm25_retrieval_maps_representative_gaps_to_expected_stack_topics(self) -> None:
        fixture_path = Path(__file__).parent / "fixtures" / "nvidia_knowledge_official_fixture.json"
        corpus = load_nvidia_knowledge_corpus(fixture_path)

        cases = (
            (
                "model_serving",
                "Need lower latency production inference and hosted model serving.",
                "model_serving",
                "nvidia-nim-developers",
            ),
            (
                "llm_customization",
                "Need LLM fine-tuning, model evaluation, and domain adaptation.",
                "llm_customization",
                "nvidia-nemo-framework",
            ),
            (
                "data_acceleration",
                "Need faster dataframe processing and GPU data acceleration for ML pipelines.",
                "data_acceleration",
                "nvidia-cuda-x-data-science",
            ),
            (
                "computer_vision",
                "Need video analytics, OCR, visual inspection, and edge camera inference.",
                "computer_vision",
                "nvidia-deepstream-sdk",
            ),
            (
                "voice_ai",
                "Need speech AI, ASR, TTS, and conversational voice assistant deployment.",
                "voice_ai",
                "nvidia-riva",
            ),
            (
                "robotics_simulation",
                "Need robotics simulation, synthetic data, and digital twin validation.",
                "robotics_simulation",
                "nvidia-isaac-sim",
            ),
            (
                "healthcare_ai",
                "Need medical imaging AI, genomics acceleration, and digital health workflows.",
                "healthcare_ai",
                "nvidia-healthcare-ai",
            ),
            (
                "cybersecurity_ai",
                "Need cybersecurity AI for threat detection and streaming security telemetry.",
                "cybersecurity_ai",
                "nvidia-morpheus",
            ),
        )

        for gap_type, description, expected_topic, expected_document_id in cases:
            with self.subTest(gap_type=gap_type):
                retrieval = retrieve_nvidia_knowledge_by_gap(
                    corpus,
                    run_id=f"run-{gap_type}",
                    gap_type=gap_type,
                    description=description,
                    top_k=1,
                )

                self.assertEqual(retrieval.results[0].chunk.topic, expected_topic)
                self.assertEqual(retrieval.results[0].citation.document_id, expected_document_id)

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
