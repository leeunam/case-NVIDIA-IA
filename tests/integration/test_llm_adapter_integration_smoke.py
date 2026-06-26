from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from nvidia_startup_intel.ai_native_assessment import TechnicalGap
from nvidia_startup_intel.framework_adapters import (
    DeterministicTopKReranker,
    LocalBM25NVIDIAKnowledgeRetriever,
    NVIDIARerankResult,
    nvidia_rerank_result_to_dict,
    rerank_nvidia_retrieval,
)
from nvidia_startup_intel.llm_adapter_smoke import (
    LLMAdapterSmokeError,
    run_langchain_adapter_smoke,
    run_litellm_adapter_smoke,
)
from nvidia_startup_intel.nvidia_knowledge import load_nvidia_knowledge_corpus


pytestmark = pytest.mark.llm_adapter_integration

_RUN_ENV = "NVIDIA_STARTUP_INTEL_RUN_LLM_ADAPTER_SMOKE"


def test_litellm_smoke_returns_project_owned_response() -> None:
    _skip_unless_enabled()
    if os.environ.get("NVIDIA_STARTUP_INTEL_LLM_PROVIDER") != "litellm":
        pytest.skip("set NVIDIA_STARTUP_INTEL_LLM_PROVIDER=litellm for the LiteLLM smoke")

    try:
        result = run_litellm_adapter_smoke()
    except LLMAdapterSmokeError as exc:
        pytest.fail(f"OPTIONAL LITELLM ADAPTER SMOKE FAILED: {exc}", pytrace=False)

    assert result.schema_version == "llm_generation_response.v1"
    assert result.provider == "litellm"
    assert result.request_purpose == "adapter_smoke"
    assert result.serialized_response["schema_version"] == "llm_generation_response.v1"
    assert result.serialized_response["metadata"]["adapter"] == "litellm"
    assert result.adapter_error is False
    assert "choices" not in result.serialized_response


def test_langchain_smoke_accepts_locally_supplied_chat_model() -> None:
    _skip_unless_enabled()
    if os.environ.get("NVIDIA_STARTUP_INTEL_LLM_PROVIDER") != "langchain":
        pytest.skip("set NVIDIA_STARTUP_INTEL_LLM_PROVIDER=langchain for the LangChain smoke")

    chat_model = _LocalSmokeChatModel(
        _LocalSmokeChatMessage(
            content="Local LangChain smoke response.",
            response_metadata={"finish_reason": "stop", "token_usage": {"total_tokens": 6}},
        )
    )

    try:
        result = run_langchain_adapter_smoke(chat_model=chat_model)
    except LLMAdapterSmokeError as exc:
        pytest.fail(f"OPTIONAL LANGCHAIN ADAPTER SMOKE FAILED: {exc}", pytrace=False)

    assert result.schema_version == "llm_generation_response.v1"
    assert result.provider == "langchain"
    assert result.request_purpose == "adapter_smoke"
    assert result.serialized_response["schema_version"] == "llm_generation_response.v1"
    assert result.serialized_response["metadata"]["adapter"] == "langchain"
    assert result.adapter_error is False
    assert "_LocalSmokeChatMessage" not in json.dumps(result.to_dict())


def test_rerank_smoke_returns_project_owned_contract() -> None:
    _skip_unless_enabled()
    corpus = load_nvidia_knowledge_corpus(
        Path("tests/fixtures/nvidia_knowledge_official_fixture.json")
    )
    gap = TechnicalGap(
        gap_type="model_serving",
        description="Need lower latency inference and production model serving.",
        severity="high",
        confidence=0.88,
        evidences=(),
    )
    retrieval = LocalBM25NVIDIAKnowledgeRetriever(corpus).retrieve_for_gap(
        run_id="run-llm-framework-adapter-smoke",
        gap=gap,
        startup_signals=("self-hosted inference", "latency"),
        top_k=2,
    )

    rerank_result = rerank_nvidia_retrieval(
        retrieval,
        DeterministicTopKReranker(),
        candidate_top_k=2,
    )

    assert isinstance(rerank_result, NVIDIARerankResult)
    assert rerank_result.schema_version == "nvidia_rerank.v1"
    assert rerank_result.results
    serialized = nvidia_rerank_result_to_dict(rerank_result)
    assert serialized["schema_version"] == "nvidia_rerank.v1"
    assert serialized["results"][0]["citation"]["source_type"].startswith("official_nvidia_")
    assert "framework_node" not in json.dumps(serialized)


def _skip_unless_enabled() -> None:
    if os.environ.get(_RUN_ENV) != "1":
        pytest.skip(
            "optional LLM/framework adapter smoke is disabled; set "
            f"{_RUN_ENV}=1 and configure NVIDIA_STARTUP_INTEL_LLM_PROVIDER"
        )


class _LocalSmokeChatMessage:
    def __init__(self, *, content: str, response_metadata: dict[str, object]) -> None:
        self.content = content
        self.response_metadata = response_metadata


class _LocalSmokeChatModel:
    def __init__(self, response: _LocalSmokeChatMessage) -> None:
        self.response = response

    def invoke(self, messages: list[tuple[str, str]]) -> _LocalSmokeChatMessage:
        return self.response
