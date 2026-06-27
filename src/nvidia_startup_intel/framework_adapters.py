"""Backward-compatible aggregate exports for framework adapter seams.

New code should import from the seam-local modules:

- ``llm_adapters`` for LLM requests, responses, and provider clients.
- ``nvidia_retrievers`` for NVIDIA Knowledge retriever adapters.
- ``nvidia_reranking`` for NVIDIA Knowledge reranker adapters.
"""

from __future__ import annotations

from nvidia_startup_intel.llm_adapters import (
    LLM_ENV_PREFIX,
    LLM_REQUEST_SCHEMA_VERSION,
    LLM_RESPONSE_SCHEMA_VERSION,
    DeterministicFakeLLMClient,
    LLMClient,
    LLMGenerationRequest,
    LLMGenerationResponse,
    LLMProviderConfig,
    LangChainLLMClient,
    LiteLLMClient,
    llm_generation_response_to_dict,
    llm_provider_config_from_env,
)
from nvidia_startup_intel.nvidia_reranking import (
    RERANK_SCHEMA_VERSION,
    DeterministicTopKReranker,
    NVIDIAReranker,
    NVIDIARerankRequest,
    NVIDIARerankResult,
    RerankedNVIDIAKnowledge,
    SentenceTransformersCrossEncoderReranker,
    nvidia_rerank_result_to_dict,
    rerank_nvidia_retrieval,
)
from nvidia_startup_intel.nvidia_retrievers import (
    HybridNVIDIAPgvectorKnowledgeRetriever,
    LocalBM25NVIDIAKnowledgeRetriever,
    NVIDIAKnowledgeRetriever,
    NVIDIAVectorKnowledgeStore,
    RankBM25NVIDIAKnowledgeRetriever,
)


__all__ = (
    "DeterministicFakeLLMClient",
    "DeterministicTopKReranker",
    "HybridNVIDIAPgvectorKnowledgeRetriever",
    "LLMClient",
    "LLMGenerationRequest",
    "LLMGenerationResponse",
    "LLMProviderConfig",
    "LLM_ENV_PREFIX",
    "LLM_REQUEST_SCHEMA_VERSION",
    "LLM_RESPONSE_SCHEMA_VERSION",
    "LangChainLLMClient",
    "LiteLLMClient",
    "LocalBM25NVIDIAKnowledgeRetriever",
    "NVIDIAKnowledgeRetriever",
    "NVIDIARerankRequest",
    "NVIDIARerankResult",
    "NVIDIAReranker",
    "NVIDIAVectorKnowledgeStore",
    "RERANK_SCHEMA_VERSION",
    "RankBM25NVIDIAKnowledgeRetriever",
    "RerankedNVIDIAKnowledge",
    "SentenceTransformersCrossEncoderReranker",
    "llm_generation_response_to_dict",
    "llm_provider_config_from_env",
    "nvidia_rerank_result_to_dict",
    "rerank_nvidia_retrieval",
)
