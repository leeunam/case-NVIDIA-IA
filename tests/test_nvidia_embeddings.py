from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
import unittest

from nvidia_startup_intel.nvidia_embeddings import (
    DeterministicFakeEmbeddingClient,
    EmbeddingModelMetadata,
    SentenceTransformersEmbeddingClient,
    assess_nvidia_embedding_index_rebuild,
    build_nvidia_embedding_index,
    embed_nvidia_query,
    embedding_client_from_config,
    embedding_provider_config_from_env,
    nvidia_embedding_index_to_dict,
    nvidia_query_embedding_to_dict,
    retrieve_nvidia_knowledge_by_vector,
)
from nvidia_startup_intel.nvidia_knowledge import (
    NVIDIAKnowledgeChunk,
    NVIDIAKnowledgeCorpus,
    NVIDIAKnowledgeDocument,
    load_nvidia_knowledge_corpus,
    nvidia_knowledge_retrieval_to_dict,
    summarize_nvidia_retrieval_quality,
)


class NVIDIAEmbeddingContractTests(unittest.TestCase):
    def test_fake_embedding_client_returns_deterministic_vectors_with_contract_metadata(self) -> None:
        client = DeterministicFakeEmbeddingClient(dimension=6)

        first_vector = client.embed_texts(("NVIDIA NIM inference microservices",))[0]
        second_vector = client.embed_texts(("NVIDIA NIM inference microservices",))[0]

        self.assertEqual(client.metadata.embedding_provider, "local_fake")
        self.assertEqual(client.metadata.embedding_model, "deterministic-fake-embedding")
        self.assertEqual(client.metadata.embedding_version, "v1")
        self.assertEqual(client.metadata.dimension, 6)
        self.assertEqual(client.metadata.expected_language_behavior, "deterministic multilingual fixture text")
        self.assertEqual(first_vector, second_vector)
        self.assertEqual(len(first_vector), 6)

    def test_sentence_transformers_embedding_client_embeds_chunks_through_project_contract(self) -> None:
        corpus = load_nvidia_knowledge_corpus(_fixture_path())
        model = _SentenceTransformerLikeModel(dimension=3)
        client = SentenceTransformersEmbeddingClient(
            model_name="intfloat/multilingual-e5-base",
            model_version="local-fixture",
            expected_language_behavior="multilingual Portuguese and English technical retrieval",
            model=model,
        )

        index = build_nvidia_embedding_index(corpus, client)

        self.assertEqual(index.metadata.embedding_provider, "sentence_transformers")
        self.assertEqual(index.metadata.embedding_model, "intfloat/multilingual-e5-base")
        self.assertEqual(index.metadata.embedding_version, "local-fixture")
        self.assertEqual(index.metadata.dimension, 3)
        self.assertEqual(
            index.metadata.expected_language_behavior,
            "multilingual Portuguese and English technical retrieval",
        )
        self.assertEqual(len(index.chunk_embeddings), len(corpus.chunks))
        self.assertEqual(index.chunk_embeddings[0].vector, (1.0, 0.0, 0.0))

    def test_embedding_client_from_env_config_builds_sentence_transformers_adapter(self) -> None:
        config = embedding_provider_config_from_env(
            {
                "NVIDIA_STARTUP_INTEL_EMBEDDING_PROVIDER": "sentence-transformers",
                "NVIDIA_STARTUP_INTEL_EMBEDDING_MODEL": "BAAI/bge-m3",
                "NVIDIA_STARTUP_INTEL_EMBEDDING_MODEL_VERSION": "local-snapshot",
                "NVIDIA_STARTUP_INTEL_EMBEDDING_EXPECTED_LANGUAGE_BEHAVIOR": (
                    "multilingual Portuguese and English technical retrieval"
                ),
                "NVIDIA_STARTUP_INTEL_EMBEDDING_BATCH_SIZE": "16",
                "NVIDIA_STARTUP_INTEL_EMBEDDING_NORMALIZE": "false",
            }
        )
        loaded_models: list[str] = []

        client = embedding_client_from_config(
            config,
            model_loader=lambda model_name: _loaded_sentence_transformer(
                loaded_models,
                model_name,
                dimension=2,
            ),
        )

        self.assertEqual(loaded_models, ["BAAI/bge-m3"])
        self.assertEqual(client.metadata.embedding_provider, "sentence_transformers")
        self.assertEqual(client.metadata.embedding_model, "BAAI/bge-m3")
        self.assertEqual(client.metadata.embedding_version, "local-snapshot")
        self.assertEqual(client.metadata.dimension, 2)
        self.assertEqual(client.embed_texts(("NVIDIA NIM",)), ((1.0, 0.0),))

    def test_query_embedding_uses_same_contract_metadata_as_chunk_embeddings(self) -> None:
        client = DeterministicFakeEmbeddingClient(dimension=6)

        query_embedding = embed_nvidia_query("lower latency inference", client)

        self.assertEqual(query_embedding.schema_version, "nvidia_embedding.v1")
        self.assertEqual(query_embedding.query, "lower latency inference")
        self.assertEqual(query_embedding.metadata, client.metadata)
        self.assertEqual(query_embedding.vector, client.embed_texts(("lower latency inference",))[0])

        serialized = nvidia_query_embedding_to_dict(query_embedding)
        json.dumps(serialized)
        self.assertEqual(serialized["metadata"]["embedding_model"], "deterministic-fake-embedding")
        self.assertNotIn("llm_model", serialized["metadata"])

    def test_embedding_index_preserves_corpus_chunk_and_embedding_metadata(self) -> None:
        corpus = load_nvidia_knowledge_corpus(_fixture_path())
        client = DeterministicFakeEmbeddingClient(dimension=6)

        index = build_nvidia_embedding_index(corpus, client)

        self.assertEqual(index.schema_version, "nvidia_embedding.v1")
        self.assertEqual(index.metadata.corpus_version, "official-nvidia-fixture.v1")
        self.assertEqual(index.metadata.embedding_provider, "local_fake")
        self.assertEqual(index.metadata.embedding_model, "deterministic-fake-embedding")
        self.assertEqual(index.metadata.embedding_version, "v1")
        self.assertEqual(index.metadata.dimension, 6)
        self.assertEqual(index.metadata.expected_language_behavior, "deterministic multilingual fixture text")
        self.assertEqual(index.metadata.index_parameters, {"distance_metric": "cosine", "index_type": "exact_in_memory"})
        self.assertEqual(index.metadata.chunk_count, len(corpus.chunks))
        self.assertTrue(index.metadata.chunking_fingerprint.startswith("sha256:"))
        self.assertEqual(
            index.metadata.rebuild_requirements,
            (
                "corpus_version",
                "chunking_fingerprint",
                "embedding_provider",
                "embedding_model",
                "embedding_version",
                "dimension",
                "index_parameters",
            ),
        )
        self.assertEqual(len(index.chunk_embeddings), len(corpus.chunks))
        self.assertEqual(index.chunk_embeddings[0].chunk, corpus.chunks[0])
        self.assertEqual(len(index.chunk_embeddings[0].vector), 6)

        serialized = nvidia_embedding_index_to_dict(index)
        json.dumps(serialized)
        self.assertEqual(serialized["chunk_embeddings"][0]["chunk"]["chunk_id"], corpus.chunks[0].chunk_id)
        self.assertNotIn("llm_model", serialized["metadata"])
        self.assertNotIn("generator_model", serialized["metadata"])

    def test_embedding_index_rejects_vectors_with_wrong_dimension(self) -> None:
        corpus = load_nvidia_knowledge_corpus(_fixture_path())

        with self.assertRaisesRegex(
            ValueError,
            "embedding_dimension_mismatch:nvidia-nim-developers:0:expected_3:actual_2",
        ):
            build_nvidia_embedding_index(corpus, _WrongDimensionEmbeddingClient())

    def test_rebuild_assessment_reports_metadata_changes(self) -> None:
        corpus = load_nvidia_knowledge_corpus(_fixture_path())
        current_client = DeterministicFakeEmbeddingClient(dimension=6)
        current_index = build_nvidia_embedding_index(corpus, current_client)

        matching = assess_nvidia_embedding_index_rebuild(current_index.metadata, corpus, current_client)

        self.assertFalse(matching.rebuild_required)
        self.assertEqual(matching.reasons, ())

        changed_corpus = replace(corpus, corpus_version="official-nvidia-fixture.v2")
        changed_client = DeterministicFakeEmbeddingClient(
            dimension=7,
            embedding_model="deterministic-fake-embedding-next",
            embedding_version="v2",
        )

        changed = assess_nvidia_embedding_index_rebuild(
            current_index.metadata,
            changed_corpus,
            changed_client,
            index_parameters={"distance_metric": "dot_product", "index_type": "exact_in_memory"},
        )

        self.assertTrue(changed.rebuild_required)
        self.assertEqual(
            changed.reasons,
            (
                "corpus_version_changed",
                "embedding_model_changed",
                "embedding_version_changed",
                "dimension_changed",
                "index_parameters_changed",
            ),
        )

    def test_rebuild_assessment_reports_chunking_changes_even_when_corpus_version_is_unchanged(self) -> None:
        corpus = load_nvidia_knowledge_corpus(_fixture_path())
        client = DeterministicFakeEmbeddingClient(dimension=6)
        current_index = build_nvidia_embedding_index(corpus, client)
        changed_chunking = replace(corpus, chunks=tuple(reversed(corpus.chunks)))

        assessment = assess_nvidia_embedding_index_rebuild(
            current_index.metadata,
            changed_chunking,
            client,
        )

        self.assertTrue(assessment.rebuild_required)
        self.assertEqual(assessment.reasons, ("chunking_changed",))

    def test_vector_retrieval_finds_semantic_citation_for_model_serving_gap(self) -> None:
        corpus = load_nvidia_knowledge_corpus(_fixture_path())
        client = DeterministicFakeEmbeddingClient(dimension=6)
        index = build_nvidia_embedding_index(corpus, client)

        retrieval = retrieve_nvidia_knowledge_by_vector(
            corpus,
            index,
            client,
            run_id="run-vector-001",
            gap_type="model_serving",
            description="Need lower latency inference deployment.",
            startup_signals=("self-hosted inference",),
            top_k=2,
        )

        self.assertEqual(retrieval.schema_version, "nvidia_knowledge.v1")
        self.assertEqual(retrieval.run_id, "run-vector-001")
        self.assertEqual(retrieval.corpus_version, "official-nvidia-fixture.v1")
        self.assertEqual(retrieval.results[0].chunk.topic, "model_serving")
        self.assertIn(
            retrieval.results[0].citation.document_id,
            {"nvidia-api-catalog", "nvidia-nim-developers"},
        )
        self.assertEqual(retrieval.results[0].rank, 1)
        self.assertEqual(retrieval.results[0].retrieval_strategy, "vector_semantic")
        self.assertEqual(retrieval.results[0].bm25_score, 0.0)
        self.assertEqual(retrieval.results[0].vector_score, retrieval.results[0].score)
        self.assertGreater(retrieval.results[0].vector_score, 0.0)
        self.assertEqual(retrieval.results[0].embedding_metadata["schema_version"], "nvidia_embedding.v1")
        self.assertEqual(
            retrieval.results[0].embedding_metadata["corpus_version"],
            "official-nvidia-fixture.v1",
        )
        self.assertEqual(retrieval.results[0].embedding_metadata["chunk_count"], len(corpus.chunks))
        self.assertTrue(
            str(retrieval.results[0].embedding_metadata["chunking_fingerprint"]).startswith("sha256:")
        )
        self.assertEqual(retrieval.results[0].embedding_metadata["embedding_provider"], "local_fake")
        self.assertEqual(
            retrieval.results[0].embedding_metadata["embedding_model"],
            "deterministic-fake-embedding",
        )
        self.assertEqual(retrieval.results[0].embedding_metadata["embedding_version"], "v1")
        self.assertEqual(retrieval.results[0].embedding_metadata["dimension"], 6)
        self.assertEqual(
            retrieval.results[0].embedding_metadata["expected_language_behavior"],
            "deterministic multilingual fixture text",
        )
        self.assertEqual(
            retrieval.results[0].index_parameters,
            {"distance_metric": "cosine", "index_type": "exact_in_memory"},
        )
        self.assertEqual(retrieval.results[0].ranking_strategy, "cosine_similarity_desc")
        self.assertEqual(retrieval.results[0].tie_breakers, ("document_id", "chunk_index", "chunk_id"))

    def test_vector_retrieval_returns_no_results_for_unmatched_normalized_query(self) -> None:
        corpus = load_nvidia_knowledge_corpus(_fixture_path())
        client = DeterministicFakeEmbeddingClient(dimension=6)
        index = build_nvidia_embedding_index(corpus, client)

        retrieval = retrieve_nvidia_knowledge_by_vector(
            corpus,
            index,
            client,
            run_id="run-vector-002",
            normalized_query="tax invoicing accounts payable workflow",
            top_k=3,
        )

        self.assertEqual(retrieval.query, "tax invoicing accounts payable workflow")
        self.assertEqual(retrieval.results, ())
        self.assertEqual(retrieval.documents, ())

        quality = summarize_nvidia_retrieval_quality(retrieval)
        self.assertFalse(quality.has_sufficient_citation)
        self.assertEqual(quality.reasons, ("no_retrieved_citation",))

    def test_vector_retrieval_orders_ties_by_stable_chunk_metadata(self) -> None:
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
                    text="NIM inference microservices.",
                ),
                NVIDIAKnowledgeChunk(
                    schema_version="nvidia_knowledge.v1",
                    corpus_version="test-corpus.v1",
                    chunk_id="doc-a:0",
                    document_id="doc-a",
                    chunk_index=0,
                    topic="model_serving",
                    text="NIM inference microservices.",
                ),
            ),
        )
        client = DeterministicFakeEmbeddingClient(dimension=6)
        index = build_nvidia_embedding_index(corpus, client)

        retrieval = retrieve_nvidia_knowledge_by_vector(
            corpus,
            index,
            client,
            run_id="run-vector-003",
            normalized_query="inference microservices",
            top_k=2,
        )

        self.assertEqual([result.citation.document_id for result in retrieval.results], ["doc-a", "doc-b"])
        self.assertEqual([result.rank for result in retrieval.results], [1, 2])
        self.assertEqual(retrieval.results[0].vector_score, retrieval.results[1].vector_score)

    def test_vector_retrieval_serializes_metadata_for_commercial_opportunity_query(self) -> None:
        corpus = load_nvidia_knowledge_corpus(_fixture_path())
        client = DeterministicFakeEmbeddingClient(dimension=6)
        index = build_nvidia_embedding_index(corpus, client)

        retrieval = retrieve_nvidia_knowledge_by_vector(
            corpus,
            index,
            client,
            run_id="run-vector-004",
            opportunity_type="startup_program",
            description="Need startup program support with no fees, deadlines, or cohorts.",
            top_k=1,
        )

        serialized = nvidia_knowledge_retrieval_to_dict(retrieval)
        json.dumps(serialized)
        result = serialized["results"][0]

        self.assertIn("startup program", serialized["query"])
        self.assertEqual(result["chunk"]["chunk_id"], "nvidia-inception:0")
        self.assertEqual(result["citation"]["document_id"], "nvidia-inception")
        self.assertEqual(result["retrieval_strategy"], "vector_semantic")
        self.assertEqual(result["vector_score"], result["score"])
        self.assertEqual(result["embedding_metadata"]["embedding_model"], "deterministic-fake-embedding")
        self.assertEqual(result["embedding_metadata"]["embedding_version"], "v1")
        self.assertEqual(result["embedding_metadata"]["dimension"], 6)
        self.assertEqual(result["embedding_metadata"]["corpus_version"], "official-nvidia-fixture.v1")
        self.assertEqual(result["index_parameters"], {"distance_metric": "cosine", "index_type": "exact_in_memory"})
        self.assertEqual(result["ranking_strategy"], "cosine_similarity_desc")

        quality = summarize_nvidia_retrieval_quality(retrieval)
        self.assertTrue(quality.has_sufficient_citation)
        self.assertEqual(quality.reasons, ("citation_sufficient",))


def _fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "nvidia_knowledge_official_fixture.json"


class _WrongDimensionEmbeddingClient:
    @property
    def metadata(self) -> EmbeddingModelMetadata:
        return EmbeddingModelMetadata(
            schema_version="nvidia_embedding.v1",
            embedding_provider="local_fake",
            embedding_model="wrong-dimension-fake",
            embedding_version="v1",
            dimension=3,
            expected_language_behavior="deterministic multilingual fixture text",
        )

    def embed_texts(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple((0.1, 0.2) for _ in texts)


class _SentenceTransformerLikeModel:
    def __init__(self, *, dimension: int) -> None:
        self._dimension = dimension

    def get_sentence_embedding_dimension(self) -> int:
        return self._dimension

    def encode(self, texts: list[str], **_: object) -> list[list[float]]:
        vectors: list[list[float]] = []
        for index, _text in enumerate(texts):
            vectors.append([1.0 if index == component else 0.0 for component in range(self._dimension)])
        return vectors


def _loaded_sentence_transformer(
    loaded_models: list[str],
    model_name: str,
    *,
    dimension: int,
) -> _SentenceTransformerLikeModel:
    loaded_models.append(model_name)
    return _SentenceTransformerLikeModel(dimension=dimension)


if __name__ == "__main__":
    unittest.main()
