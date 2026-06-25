from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
import unittest

from nvidia_startup_intel.nvidia_embeddings import (
    DeterministicFakeEmbeddingClient,
    EmbeddingModelMetadata,
    assess_nvidia_embedding_index_rebuild,
    build_nvidia_embedding_index,
    embed_nvidia_query,
    nvidia_embedding_index_to_dict,
    nvidia_query_embedding_to_dict,
)
from nvidia_startup_intel.nvidia_knowledge import load_nvidia_knowledge_corpus


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
        self.assertEqual(
            index.metadata.rebuild_requirements,
            (
                "corpus_version",
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


if __name__ == "__main__":
    unittest.main()
