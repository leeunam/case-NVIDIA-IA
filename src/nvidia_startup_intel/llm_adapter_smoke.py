"""Optional smoke validation for external LLM/framework adapter boundaries.

This module is intentionally outside the default validation path. It proves
that optional provider/framework objects are converted into project-owned
schemas before downstream Recommendation, Briefing, workflow state, or
persistence can consume them.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass

from nvidia_startup_intel.llm_adapters import (
    LLM_RESPONSE_SCHEMA_VERSION,
    LLMGenerationRequest,
    LLMGenerationResponse,
    LangChainLLMClient,
    LiteLLMClient,
    llm_generation_response_to_dict,
    llm_provider_config_from_env,
)


class LLMAdapterSmokeError(RuntimeError):
    """Actionable failure for the optional LLM/framework adapter smoke path."""

    def __init__(
        self,
        message: str,
        *,
        adapter_response: LLMGenerationResponse | None = None,
        serialized_response: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.adapter_response = adapter_response
        self.serialized_response = serialized_response or {}


@dataclass(frozen=True)
class LLMAdapterSmokeResult:
    provider: str
    model: str
    model_version: str
    schema_version: str
    request_purpose: str
    structured_output_schema: str
    finish_reason: str
    content_characters: int
    adapter_error: bool
    serialized_response: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def run_litellm_adapter_smoke(
    *,
    env: Mapping[str, str] | None = None,
    completion: Callable[..., object] | None = None,
) -> LLMAdapterSmokeResult:
    """Run a LiteLLM adapter smoke through the project-owned response schema."""

    config = llm_provider_config_from_env(env)
    if config.provider != "litellm":
        raise LLMAdapterSmokeError(
            "LiteLLM adapter smoke requires NVIDIA_STARTUP_INTEL_LLM_PROVIDER=litellm."
        )

    response = LiteLLMClient(config=config, completion=completion, env=env).generate(
        _smoke_request(adapter="litellm")
    )
    return _validated_llm_result(response, expected_provider="litellm")


def run_langchain_adapter_smoke(
    *,
    chat_model: object,
    env: Mapping[str, str] | None = None,
) -> LLMAdapterSmokeResult:
    """Run a locally supplied LangChain chat model through the project schema."""

    config = llm_provider_config_from_env(env)
    if config.provider != "langchain":
        raise LLMAdapterSmokeError(
            "LangChain adapter smoke requires NVIDIA_STARTUP_INTEL_LLM_PROVIDER=langchain."
        )

    response = LangChainLLMClient(config=config, chat_model=chat_model).generate(
        _smoke_request(adapter="langchain")
    )
    return _validated_llm_result(response, expected_provider="langchain")


def _smoke_request(*, adapter: str) -> LLMGenerationRequest:
    return LLMGenerationRequest(
        schema_version="llm_generation_request.v1",
        purpose="adapter_smoke",
        system_prompt="Return a short response using only the smoke-test request.",
        user_prompt="Confirm the adapter boundary without adding external facts.",
        structured_output_schema="llm_adapter_smoke.v1",
        metadata={"adapter_smoke": True, "adapter": adapter},
    )


def _validated_llm_result(
    response: LLMGenerationResponse,
    *,
    expected_provider: str,
) -> LLMAdapterSmokeResult:
    if not isinstance(response, LLMGenerationResponse):
        raise LLMAdapterSmokeError(
            "LLM adapter returned a provider/framework object instead of LLMGenerationResponse."
        )

    serialized = llm_generation_response_to_dict(response)
    if response.schema_version != LLM_RESPONSE_SCHEMA_VERSION:
        raise LLMAdapterSmokeError(
            f"LLM adapter returned unexpected schema version: {response.schema_version}",
            adapter_response=response,
            serialized_response=serialized,
        )
    if response.provider != expected_provider:
        raise LLMAdapterSmokeError(
            f"LLM adapter returned provider {response.provider!r}, expected {expected_provider!r}.",
            adapter_response=response,
            serialized_response=serialized,
        )
    if response.finish_reason == "adapter_error":
        raise LLMAdapterSmokeError(
            "LLM adapter returned a structured adapter_error response.",
            adapter_response=response,
            serialized_response=serialized,
        )

    return LLMAdapterSmokeResult(
        provider=response.provider,
        model=response.model,
        model_version=response.model_version,
        schema_version=response.schema_version,
        request_purpose=response.request_purpose,
        structured_output_schema=response.structured_output_schema,
        finish_reason=response.finish_reason,
        content_characters=len(response.content),
        adapter_error=bool(response.metadata.get("adapter_error", False)),
        serialized_response=serialized,
    )
