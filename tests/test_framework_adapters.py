from __future__ import annotations

import json
import unittest

from nvidia_startup_intel.ai_native_assessment import TechnicalGap
from nvidia_startup_intel.framework_adapters import (
    DeterministicFakeLLMClient,
    DeterministicTopKReranker,
    LangChainLLMClient,
    LLMGenerationRequest,
    LiteLLMClient,
    RankBM25NVIDIAKnowledgeRetriever,
    llm_provider_config_from_env,
    llm_generation_response_to_dict,
    nvidia_rerank_result_to_dict,
    rerank_nvidia_retrieval,
)
from nvidia_startup_intel.nvidia_knowledge import (
    NVIDIACitation,
    NVIDIAKnowledgeChunk,
    NVIDIAKnowledgeCorpus,
    NVIDIAKnowledgeDocument,
    NVIDIAKnowledgeRetrieval,
    RetrievedNVIDIAKnowledge,
    nvidia_knowledge_retrieval_to_dict,
)


class FrameworkAdapterContractTests(unittest.TestCase):
    def test_rank_bm25_adapter_returns_project_retrieval_without_requiring_dependency_in_tests(
        self,
    ) -> None:
        corpus = _adapter_corpus()
        fake_ranker = _FakeBM25Okapi(scores=(0.2, 1.4, 0.0))
        adapter = RankBM25NVIDIAKnowledgeRetriever(
            corpus=corpus,
            bm25_factory=lambda tokenized_corpus: fake_ranker.capture(tokenized_corpus),
        )

        retrieval = adapter.retrieve_for_gap(
            run_id="run-rank-bm25-001",
            gap=TechnicalGap(
                gap_type="model_serving",
                description="Needs production inference with low latency.",
                severity="high",
                confidence=0.9,
                evidences=(),
            ),
            startup_signals=("inference", "latency"),
            top_k=2,
        )

        self.assertEqual(retrieval.schema_version, "nvidia_knowledge.v1")
        self.assertEqual(retrieval.run_id, "run-rank-bm25-001")
        self.assertEqual(retrieval.corpus_version, "test-corpus.v1")
        self.assertEqual([result.chunk.chunk_id for result in retrieval.results], ["doc-a:1", "doc-a:0"])
        self.assertEqual(retrieval.results[0].retrieval_strategy, "rank_bm25_lexical")
        self.assertEqual(retrieval.results[0].bm25_score, 1.4)
        self.assertEqual(retrieval.results[0].score, 1.4)
        self.assertEqual(retrieval.results[0].ranking_strategy, "rank_bm25.BM25Okapi")
        self.assertEqual(
            retrieval.results[0].tie_breakers,
            ("bm25_score_desc", "document_id", "chunk_index", "chunk_id"),
        )
        self.assertEqual(retrieval.results[0].index_parameters["library"], "rank_bm25")
        self.assertEqual(retrieval.results[0].citation.source_url, "https://developer.nvidia.com/doc-a")
        self.assertIn("model", fake_ranker.query_tokens)
        self.assertNotIn("_FakeBM25Okapi", json.dumps(nvidia_knowledge_retrieval_to_dict(retrieval)))

    def test_llm_client_response_is_swappable_and_decoupled_from_embedding_contracts(self) -> None:
        request = LLMGenerationRequest(
            schema_version="llm_generation_request.v1",
            purpose="briefing_narrative",
            system_prompt="Render only validated briefing claims.",
            user_prompt="Summarize the executive briefing without adding facts.",
            structured_output_schema="executive_briefing.v1",
            metadata={"run_id": "run-issue-19"},
        )
        grok_like_client = DeterministicFakeLLMClient(
            provider="local_fake_grok",
            model="grok-compatible-fixture",
            model_version="v1",
        )
        ollama_like_client = DeterministicFakeLLMClient(
            provider="local_fake_ollama",
            model="ollama-compatible-fixture",
            model_version="v1",
        )

        first_response = grok_like_client.generate(request)
        second_response = ollama_like_client.generate(request)

        self.assertEqual(first_response.schema_version, "llm_generation_response.v1")
        self.assertEqual(first_response.request_purpose, "briefing_narrative")
        self.assertEqual(first_response.structured_output_schema, "executive_briefing.v1")
        self.assertEqual(second_response.structured_output_schema, "executive_briefing.v1")
        self.assertEqual(first_response.content, second_response.content)
        self.assertNotEqual(first_response.provider, second_response.provider)
        self.assertNotEqual(first_response.model, second_response.model)

        serialized = llm_generation_response_to_dict(first_response)
        json.dumps(serialized)
        self.assertEqual(serialized["provider"], "local_fake_grok")
        self.assertNotIn("embedding_model", serialized)
        self.assertNotIn("embedding_version", serialized)

    def test_litellm_adapter_uses_explicit_config_and_returns_project_response(self) -> None:
        env = {
            "NVIDIA_STARTUP_INTEL_LLM_PROVIDER": "litellm",
            "NVIDIA_STARTUP_INTEL_LLM_MODEL": "openrouter/meta-llama-fixture",
            "NVIDIA_STARTUP_INTEL_LLM_MODEL_VERSION": "2026-06-26",
            "NVIDIA_STARTUP_INTEL_LLM_API_KEY_ENV": "OPENROUTER_API_KEY",
            "OPENROUTER_API_KEY": "secret-token-from-env",
        }
        config = llm_provider_config_from_env(env)
        request = LLMGenerationRequest(
            schema_version="llm_generation_request.v1",
            purpose="briefing_narrative",
            system_prompt="Use only validated briefing claims.",
            user_prompt="Draft a concise narrative.",
            structured_output_schema="briefing_narrative.v1",
            metadata={"run_id": "run-issue-38"},
        )
        captured_call: dict[str, object] = {}

        def fake_completion(**kwargs: object) -> dict[str, object]:
            captured_call.update(kwargs)
            return {
                "choices": [
                    {
                        "message": {"content": "Narrative from validated claims."},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"total_tokens": 17},
            }

        client = LiteLLMClient(config=config, completion=fake_completion, env=env)

        response = client.generate(request)

        self.assertEqual(response.schema_version, "llm_generation_response.v1")
        self.assertEqual(response.request_purpose, "briefing_narrative")
        self.assertEqual(response.provider, "litellm")
        self.assertEqual(response.model, "openrouter/meta-llama-fixture")
        self.assertEqual(response.model_version, "2026-06-26")
        self.assertEqual(response.content, "Narrative from validated claims.")
        self.assertEqual(response.finish_reason, "stop")
        self.assertEqual(response.structured_output_schema, "briefing_narrative.v1")
        self.assertEqual(response.usage["total_tokens"], 17)

        self.assertEqual(captured_call["model"], "openrouter/meta-llama-fixture")
        self.assertEqual(captured_call["api_key"], "secret-token-from-env")
        self.assertEqual(
            captured_call["messages"],
            [
                {"role": "system", "content": "Use only validated briefing claims."},
                {"role": "user", "content": "Draft a concise narrative."},
            ],
        )

        serialized = llm_generation_response_to_dict(response)
        serialized_json = json.dumps(serialized)
        self.assertNotIn("secret-token-from-env", serialized_json)
        self.assertNotIn("choices", serialized)
        self.assertEqual(serialized["metadata"]["adapter"], "litellm")
        self.assertEqual(serialized["metadata"]["configured_api_key_env_var"], "OPENROUTER_API_KEY")

    def test_langchain_adapter_maps_chat_model_result_without_leaking_framework_objects(self) -> None:
        env = {
            "NVIDIA_STARTUP_INTEL_LLM_PROVIDER": "langchain",
            "NVIDIA_STARTUP_INTEL_LLM_MODEL": "langchain-chat-fixture",
            "NVIDIA_STARTUP_INTEL_LLM_MODEL_VERSION": "v-test",
        }
        request = LLMGenerationRequest(
            schema_version="llm_generation_request.v1",
            purpose="briefing_narrative",
            system_prompt="Use only validated claims.",
            user_prompt="Draft the narrative.",
            structured_output_schema="briefing_narrative.v1",
            metadata={"run_id": "run-issue-38"},
        )
        chat_model = _FakeLangChainChatModel(
            _FakeLangChainMessage(
                content="Narrative generated by fake chat model.",
                response_metadata={"finish_reason": "stop", "token_usage": {"total_tokens": 11}},
            )
        )
        client = LangChainLLMClient(
            config=llm_provider_config_from_env(env),
            chat_model=chat_model,
        )

        response = client.generate(request)

        self.assertEqual(response.provider, "langchain")
        self.assertEqual(response.model, "langchain-chat-fixture")
        self.assertEqual(response.model_version, "v-test")
        self.assertEqual(response.content, "Narrative generated by fake chat model.")
        self.assertEqual(response.finish_reason, "stop")
        self.assertEqual(response.usage["total_tokens"], 11)
        self.assertEqual(
            chat_model.messages,
            (
                ("system", "Use only validated claims."),
                ("human", "Draft the narrative."),
            ),
        )

        serialized = llm_generation_response_to_dict(response)
        serialized_json = json.dumps(serialized)
        self.assertNotIn("_FakeLangChainMessage", serialized_json)
        self.assertNotIn("chat_model", serialized_json)
        self.assertEqual(serialized["metadata"]["adapter"], "langchain")

    def test_llm_adapter_errors_are_structured_adapter_responses(self) -> None:
        env = {
            "NVIDIA_STARTUP_INTEL_LLM_PROVIDER": "litellm",
            "NVIDIA_STARTUP_INTEL_LLM_MODEL": "openrouter/error-fixture",
        }
        request = LLMGenerationRequest(
            schema_version="llm_generation_request.v1",
            purpose="briefing_narrative",
            system_prompt="Use only validated claims.",
            user_prompt="Draft the narrative.",
            structured_output_schema="briefing_narrative.v1",
            metadata={"run_id": "run-issue-38"},
        )

        def failing_completion(**kwargs: object) -> object:
            raise RuntimeError("provider temporarily unavailable")

        response = LiteLLMClient(
            config=llm_provider_config_from_env(env),
            completion=failing_completion,
            env=env,
        ).generate(request)

        self.assertEqual(response.schema_version, "llm_generation_response.v1")
        self.assertEqual(response.provider, "litellm")
        self.assertEqual(response.model, "openrouter/error-fixture")
        self.assertEqual(response.content, "")
        self.assertEqual(response.finish_reason, "adapter_error")
        self.assertEqual(response.structured_output_schema, "briefing_narrative.v1")
        self.assertEqual(response.metadata["adapter_error"], True)
        self.assertEqual(response.metadata["error_type"], "RuntimeError")
        self.assertEqual(response.metadata["run_id"], "run-issue-38")

        serialized = llm_generation_response_to_dict(response)
        json.dumps(serialized)
        self.assertEqual(serialized["metadata"]["error_message"], "provider temporarily unavailable")
        self.assertNotIn("traceback", serialized["metadata"])

    def test_reranker_operates_only_on_top_k_and_preserves_original_retrieval_contract(self) -> None:
        retrieval = _retrieval_with_ranked_candidates()
        reranker = DeterministicTopKReranker(
            rerank_scores_by_chunk_id={
                "doc-a:0": 0.2,
                "doc-b:0": 0.9,
                "doc-c:0": 10.0,
            }
        )

        rerank_result = rerank_nvidia_retrieval(retrieval, reranker, candidate_top_k=2)

        self.assertEqual(rerank_result.schema_version, "nvidia_rerank.v1")
        self.assertEqual(rerank_result.run_id, "run-rerank-001")
        self.assertEqual(rerank_result.query, "model serving inference")
        self.assertEqual(rerank_result.candidate_top_k, 2)
        self.assertEqual([result.chunk.chunk_id for result in rerank_result.results], ["doc-b:0", "doc-a:0"])
        self.assertNotIn("doc-c:0", [result.chunk.chunk_id for result in rerank_result.results])

        top_result = rerank_result.results[0]
        original_second = retrieval.results[1]
        self.assertEqual(top_result.chunk, original_second.chunk)
        self.assertEqual(top_result.citation, original_second.citation)
        self.assertEqual(top_result.original_retrieval_rank, 2)
        self.assertEqual(top_result.original_score, original_second.score)
        self.assertEqual(top_result.original_bm25_score, original_second.bm25_score)
        self.assertEqual(top_result.original_vector_score, original_second.vector_score)
        self.assertEqual(top_result.original_hybrid_score, original_second.hybrid_score)
        self.assertEqual(top_result.original_rationale, original_second.rationale)
        self.assertEqual(top_result.rerank_rank, 1)
        self.assertEqual(top_result.rerank_score, 0.9)
        self.assertEqual(top_result.rerank_rationale, "deterministic_fixture_rerank_score")

        serialized = nvidia_rerank_result_to_dict(rerank_result)
        json.dumps(serialized)
        self.assertEqual(serialized["results"][0]["chunk"]["chunk_id"], "doc-b:0")
        self.assertEqual(serialized["results"][0]["original_retrieval_rank"], 2)
        self.assertNotIn("framework_node", serialized["results"][0])


def _retrieval_with_ranked_candidates() -> NVIDIAKnowledgeRetrieval:
    document = NVIDIAKnowledgeDocument(
        schema_version="nvidia_knowledge.v1",
        corpus_version="test-corpus.v1",
        document_id="doc-a",
        title="Document A",
        source_url="https://developer.nvidia.com/doc-a",
        source_type="official_nvidia_developer_page",
        ingested_at="2026-06-23T00:00:00Z",
    )
    chunks = (
        _chunk("doc-a:0", "doc-a", 0, "NVIDIA NIM inference microservices."),
        _chunk("doc-b:0", "doc-a", 1, "NVIDIA TensorRT optimizes inference latency."),
        _chunk("doc-c:0", "doc-a", 2, "NVIDIA Inception supports startup ecosystem access."),
    )
    return NVIDIAKnowledgeRetrieval(
        schema_version="nvidia_knowledge.v1",
        run_id="run-rerank-001",
        corpus_version="test-corpus.v1",
        query="model serving inference",
        results=(
            _retrieved(document, chunks[0], rank=1, score=0.7, vector_score=0.3),
            _retrieved(document, chunks[1], rank=2, score=0.6, vector_score=0.4),
            _retrieved(document, chunks[2], rank=3, score=0.5, vector_score=0.5),
        ),
        documents=(document,),
    )


def _adapter_corpus() -> NVIDIAKnowledgeCorpus:
    document = NVIDIAKnowledgeDocument(
        schema_version="nvidia_knowledge.v1",
        corpus_version="test-corpus.v1",
        document_id="doc-a",
        title="Document A",
        source_url="https://developer.nvidia.com/doc-a",
        source_type="official_nvidia_developer_page",
        ingested_at="2026-06-23T00:00:00Z",
    )
    return NVIDIAKnowledgeCorpus(
        schema_version="nvidia_knowledge.v1",
        corpus_version="test-corpus.v1",
        documents=(document,),
        chunks=(
            _chunk("doc-a:0", "doc-a", 0, "NVIDIA NIM inference microservices."),
            _chunk("doc-a:1", "doc-a", 1, "NVIDIA TensorRT optimizes inference latency."),
            _chunk("doc-a:2", "doc-a", 2, "NVIDIA Inception supports startup ecosystem access."),
        ),
    )


def _chunk(chunk_id: str, document_id: str, chunk_index: int, text: str) -> NVIDIAKnowledgeChunk:
    return NVIDIAKnowledgeChunk(
        schema_version="nvidia_knowledge.v1",
        corpus_version="test-corpus.v1",
        chunk_id=chunk_id,
        document_id=document_id,
        chunk_index=chunk_index,
        topic="model_serving",
        text=text,
    )


def _retrieved(
    document: NVIDIAKnowledgeDocument,
    chunk: NVIDIAKnowledgeChunk,
    *,
    rank: int,
    score: float,
    vector_score: float,
) -> RetrievedNVIDIAKnowledge:
    citation = NVIDIACitation(
        schema_version="nvidia_knowledge.v1",
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
    return RetrievedNVIDIAKnowledge(
        chunk=chunk,
        citation=citation,
        score=score,
        retrieval_strategy="hybrid_bm25_vector",
        rationale=f"original rationale rank {rank}",
        rank=rank,
        bm25_score=score,
        vector_score=vector_score,
        hybrid_score=score + vector_score,
    )


class _FakeLangChainMessage:
    def __init__(self, *, content: str, response_metadata: dict[str, object]) -> None:
        self.content = content
        self.response_metadata = response_metadata


class _FakeLangChainChatModel:
    def __init__(self, response: _FakeLangChainMessage) -> None:
        self.response = response
        self.messages: tuple[tuple[str, str], ...] = ()

    def invoke(self, messages: list[tuple[str, str]]) -> _FakeLangChainMessage:
        self.messages = tuple(messages)
        return self.response


class _FakeBM25Okapi:
    def __init__(self, *, scores: tuple[float, ...]) -> None:
        self.scores = scores
        self.tokenized_corpus: list[list[str]] = []
        self.query_tokens: list[str] = []

    def capture(self, tokenized_corpus: list[list[str]]) -> "_FakeBM25Okapi":
        self.tokenized_corpus = tokenized_corpus
        return self

    def get_scores(self, query_tokens: list[str]) -> tuple[float, ...]:
        self.query_tokens = query_tokens
        return self.scores


if __name__ == "__main__":
    unittest.main()
