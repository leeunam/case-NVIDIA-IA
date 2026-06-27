"""Project-owned LLM adapter contracts and provider integrations."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, fields, is_dataclass
import os
from typing import Protocol


LLM_REQUEST_SCHEMA_VERSION = "llm_generation_request.v1"
LLM_RESPONSE_SCHEMA_VERSION = "llm_generation_response.v1"
LLM_ENV_PREFIX = "NVIDIA_STARTUP_INTEL_LLM_"


@dataclass(frozen=True)
class LLMGenerationRequest:
    schema_version: str
    purpose: str
    system_prompt: str
    user_prompt: str
    structured_output_schema: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMGenerationResponse:
    schema_version: str
    request_purpose: str
    provider: str
    model: str
    model_version: str
    content: str
    structured_output_schema: str
    finish_reason: str
    usage: dict[str, object] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)


class LLMClient(Protocol):
    """Project-owned seam for LangChain, LiteLLM, local, or provider LLM clients."""

    def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse: ...


@dataclass(frozen=True)
class LLMProviderConfig:
    """Explicit external LLM adapter configuration without storing credentials."""

    provider: str
    model: str
    model_version: str = "unknown"
    api_key_env_var: str = ""
    api_base: str = ""
    timeout_seconds: float | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    extra_parameters: dict[str, object] = field(default_factory=dict)


def llm_provider_config_from_env(env: Mapping[str, str] | None = None) -> LLMProviderConfig:
    """Build explicit LLM provider config from environment-style inputs.

    The config records the name of the credential environment variable, not the
    credential value itself. The adapter reads the value only when invoking the
    provider.
    """

    source = os.environ if env is None else env
    provider = source.get(f"{LLM_ENV_PREFIX}PROVIDER", "").strip().lower()
    model = source.get(f"{LLM_ENV_PREFIX}MODEL", "").strip()
    if not provider:
        raise ValueError("NVIDIA_STARTUP_INTEL_LLM_PROVIDER is required")
    if provider not in {"litellm", "langchain"}:
        raise ValueError(f"Unsupported LLM provider: {provider}")
    if not model:
        raise ValueError("NVIDIA_STARTUP_INTEL_LLM_MODEL is required")

    return LLMProviderConfig(
        provider=provider,
        model=model,
        model_version=source.get(f"{LLM_ENV_PREFIX}MODEL_VERSION", "unknown").strip() or "unknown",
        api_key_env_var=source.get(f"{LLM_ENV_PREFIX}API_KEY_ENV", "").strip(),
        api_base=source.get(f"{LLM_ENV_PREFIX}API_BASE", "").strip(),
        timeout_seconds=_optional_float(source.get(f"{LLM_ENV_PREFIX}TIMEOUT_SECONDS")),
        temperature=_optional_float(source.get(f"{LLM_ENV_PREFIX}TEMPERATURE")),
        max_tokens=_optional_int(source.get(f"{LLM_ENV_PREFIX}MAX_TOKENS")),
    )


@dataclass(frozen=True)
class LiteLLMClient:
    """Optional LiteLLM-backed adapter behind the project-owned LLMClient seam."""

    config: LLMProviderConfig
    completion: Callable[..., object] | None = None
    env: Mapping[str, str] | None = None

    def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        try:
            completion = self.completion or _load_litellm_completion()
            raw_response = completion(**self._completion_kwargs(request))
        except Exception as exc:
            return _adapter_error_response(
                request=request,
                provider="litellm",
                model=self.config.model,
                model_version=self.config.model_version,
                adapter="litellm",
                error=exc,
                metadata=self._response_metadata(request),
            )

        return LLMGenerationResponse(
            schema_version=LLM_RESPONSE_SCHEMA_VERSION,
            request_purpose=request.purpose,
            provider="litellm",
            model=self.config.model,
            model_version=self.config.model_version,
            content=_extract_litellm_content(raw_response),
            structured_output_schema=request.structured_output_schema,
            finish_reason=_extract_litellm_finish_reason(raw_response),
            usage=_extract_usage(raw_response),
            metadata=self._response_metadata(request),
        )

    def _completion_kwargs(self, request: LLMGenerationRequest) -> dict[str, object]:
        kwargs: dict[str, object] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
        }
        if self.config.api_key_env_var:
            api_key = (self.env or os.environ).get(self.config.api_key_env_var)
            if api_key:
                kwargs["api_key"] = api_key
        if self.config.api_base:
            kwargs["api_base"] = self.config.api_base
        if self.config.timeout_seconds is not None:
            kwargs["timeout"] = self.config.timeout_seconds
        if self.config.temperature is not None:
            kwargs["temperature"] = self.config.temperature
        if self.config.max_tokens is not None:
            kwargs["max_tokens"] = self.config.max_tokens
        kwargs.update(self.config.extra_parameters)
        return kwargs

    def _response_metadata(self, request: LLMGenerationRequest) -> dict[str, object]:
        metadata = dict(request.metadata)
        metadata.update(
            {
                "adapter": "litellm",
                "configured_api_key_env_var": self.config.api_key_env_var,
                "api_base_configured": bool(self.config.api_base),
            }
        )
        return metadata


@dataclass(frozen=True)
class LangChainLLMClient:
    """Optional LangChain chat-model adapter behind the project-owned LLMClient seam."""

    config: LLMProviderConfig
    chat_model: object

    def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        try:
            raw_response = self.chat_model.invoke(
                [
                    ("system", request.system_prompt),
                    ("human", request.user_prompt),
                ]
            )
        except Exception as exc:
            return _adapter_error_response(
                request=request,
                provider="langchain",
                model=self.config.model,
                model_version=self.config.model_version,
                adapter="langchain",
                error=exc,
                metadata=self._response_metadata(request),
            )

        return LLMGenerationResponse(
            schema_version=LLM_RESPONSE_SCHEMA_VERSION,
            request_purpose=request.purpose,
            provider="langchain",
            model=self.config.model,
            model_version=self.config.model_version,
            content=str(_lookup(raw_response, "content") or raw_response or ""),
            structured_output_schema=request.structured_output_schema,
            finish_reason=_extract_langchain_finish_reason(raw_response),
            usage=_extract_langchain_usage(raw_response),
            metadata=self._response_metadata(request),
        )

    def _response_metadata(self, request: LLMGenerationRequest) -> dict[str, object]:
        metadata = dict(request.metadata)
        metadata.update({"adapter": "langchain"})
        return metadata


@dataclass(frozen=True)
class DeterministicFakeLLMClient:
    """Local fake for contract tests; it does not call LangChain, LiteLLM, or a model."""

    provider: str = "local_fake"
    model: str = "deterministic-fake-llm"
    model_version: str = "v1"

    def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        return LLMGenerationResponse(
            schema_version=LLM_RESPONSE_SCHEMA_VERSION,
            request_purpose=request.purpose,
            provider=self.provider,
            model=self.model,
            model_version=self.model_version,
            content=(f"deterministic_response:{request.purpose}:{request.structured_output_schema}"),
            structured_output_schema=request.structured_output_schema,
            finish_reason="stop",
            usage={
                "system_prompt_characters": len(request.system_prompt),
                "user_prompt_characters": len(request.user_prompt),
            },
            metadata=dict(request.metadata),
        )


def llm_generation_response_to_dict(response: LLMGenerationResponse) -> dict[str, object]:
    """Convert an LLM adapter response to JSON-serializable data."""

    return _to_plain_data(response)


def _load_litellm_completion() -> Callable[..., object]:
    from litellm import completion

    return completion


def _optional_float(raw_value: str | None) -> float | None:
    if raw_value is None or not raw_value.strip():
        return None
    return float(raw_value)


def _optional_int(raw_value: str | None) -> int | None:
    if raw_value is None or not raw_value.strip():
        return None
    return int(raw_value)


def _adapter_error_response(
    *,
    request: LLMGenerationRequest,
    provider: str,
    model: str,
    model_version: str,
    adapter: str,
    error: Exception,
    metadata: Mapping[str, object],
) -> LLMGenerationResponse:
    response_metadata = dict(metadata)
    response_metadata.update(
        {
            "adapter": adapter,
            "adapter_error": True,
            "error_type": type(error).__name__,
            "error_message": str(error),
        }
    )
    return LLMGenerationResponse(
        schema_version=LLM_RESPONSE_SCHEMA_VERSION,
        request_purpose=request.purpose,
        provider=provider,
        model=model,
        model_version=model_version,
        content="",
        structured_output_schema=request.structured_output_schema,
        finish_reason="adapter_error",
        usage={},
        metadata=response_metadata,
    )


def _extract_litellm_content(raw_response: object) -> str:
    first_choice = _first_choice(raw_response)
    message = _lookup(first_choice, "message")
    content = _lookup(message, "content")
    if content is None:
        content = _lookup(first_choice, "text")
    return str(content or "")


def _extract_litellm_finish_reason(raw_response: object) -> str:
    finish_reason = _lookup(_first_choice(raw_response), "finish_reason")
    return str(finish_reason or "unknown")


def _first_choice(raw_response: object) -> object:
    choices = _lookup(raw_response, "choices")
    if isinstance(choices, (list, tuple)) and choices:
        return choices[0]
    return {}


def _extract_usage(raw_response: object) -> dict[str, object]:
    usage = _lookup(raw_response, "usage")
    if isinstance(usage, Mapping):
        return dict(usage)
    if hasattr(usage, "model_dump"):
        dumped = usage.model_dump()
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    if hasattr(usage, "dict"):
        dumped = usage.dict()
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    return {}


def _extract_langchain_finish_reason(raw_response: object) -> str:
    response_metadata = _lookup(raw_response, "response_metadata")
    if isinstance(response_metadata, Mapping):
        finish_reason = response_metadata.get("finish_reason")
        if finish_reason:
            return str(finish_reason)
    additional_kwargs = _lookup(raw_response, "additional_kwargs")
    if isinstance(additional_kwargs, Mapping):
        finish_reason = additional_kwargs.get("finish_reason")
        if finish_reason:
            return str(finish_reason)
    return "unknown"


def _extract_langchain_usage(raw_response: object) -> dict[str, object]:
    usage_metadata = _lookup(raw_response, "usage_metadata")
    if isinstance(usage_metadata, Mapping):
        return dict(usage_metadata)
    response_metadata = _lookup(raw_response, "response_metadata")
    if isinstance(response_metadata, Mapping):
        token_usage = response_metadata.get("token_usage")
        if isinstance(token_usage, Mapping):
            return dict(token_usage)
    return {}


def _lookup(value: object, key: str) -> object | None:
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)


def _to_plain_data(value: object) -> dict[str, object]:
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: _to_plain_value(getattr(value, item.name)) for item in fields(value)}
    raise TypeError(f"unsupported_llm_serialization_type:{type(value).__name__}")


def _to_plain_value(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: _to_plain_value(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, dict):
        return {key: _to_plain_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain_value(item) for item in value]
    return value
