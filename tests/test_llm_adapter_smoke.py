from __future__ import annotations

import json
import unittest

from nvidia_startup_intel.llm_adapter_smoke import (
    LLMAdapterSmokeError,
    run_langchain_adapter_smoke,
    run_litellm_adapter_smoke,
)


class LLMAdapterSmokeTests(unittest.TestCase):
    def test_litellm_smoke_converts_provider_response_to_project_schema(self) -> None:
        env = {
            "NVIDIA_STARTUP_INTEL_LLM_PROVIDER": "litellm",
            "NVIDIA_STARTUP_INTEL_LLM_MODEL": "openrouter/nvidia-smoke-fixture",
            "NVIDIA_STARTUP_INTEL_LLM_MODEL_VERSION": "2026-06-26",
            "NVIDIA_STARTUP_INTEL_LLM_API_KEY_ENV": "OPENROUTER_API_KEY",
            "OPENROUTER_API_KEY": "secret-token-from-env",
        }

        def fake_completion(**kwargs: object) -> dict[str, object]:
            self.assertEqual(kwargs["model"], "openrouter/nvidia-smoke-fixture")
            self.assertEqual(kwargs["api_key"], "secret-token-from-env")
            return {
                "choices": [
                    {
                        "message": {"content": "Smoke response from validated claims."},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"total_tokens": 9},
            }

        result = run_litellm_adapter_smoke(env=env, completion=fake_completion)

        self.assertEqual(result.provider, "litellm")
        self.assertEqual(result.model, "openrouter/nvidia-smoke-fixture")
        self.assertEqual(result.schema_version, "llm_generation_response.v1")
        self.assertEqual(result.finish_reason, "stop")
        self.assertEqual(result.content_characters, len("Smoke response from validated claims."))
        self.assertFalse(result.adapter_error)
        self.assertEqual(result.serialized_response["provider"], "litellm")
        self.assertEqual(result.serialized_response["metadata"]["adapter"], "litellm")

        serialized_json = json.dumps(result.to_dict())
        self.assertNotIn("secret-token-from-env", serialized_json)
        self.assertNotIn("choices", serialized_json)

    def test_langchain_smoke_converts_local_chat_model_to_project_schema(self) -> None:
        env = {
            "NVIDIA_STARTUP_INTEL_LLM_PROVIDER": "langchain",
            "NVIDIA_STARTUP_INTEL_LLM_MODEL": "local-langchain-smoke",
            "NVIDIA_STARTUP_INTEL_LLM_MODEL_VERSION": "local-v1",
        }
        chat_model = _SmokeChatModel(
            _SmokeChatMessage(
                content="Smoke response from local chat model.",
                response_metadata={"finish_reason": "stop", "token_usage": {"total_tokens": 7}},
            )
        )

        result = run_langchain_adapter_smoke(env=env, chat_model=chat_model)

        self.assertEqual(result.provider, "langchain")
        self.assertEqual(result.model, "local-langchain-smoke")
        self.assertEqual(result.model_version, "local-v1")
        self.assertEqual(result.schema_version, "llm_generation_response.v1")
        self.assertEqual(result.finish_reason, "stop")
        self.assertFalse(result.adapter_error)
        self.assertEqual(result.serialized_response["metadata"]["adapter"], "langchain")
        self.assertEqual(
            chat_model.messages,
            (
                ("system", "Return a short response using only the smoke-test request."),
                ("human", "Confirm the adapter boundary without adding external facts."),
            ),
        )

        serialized_json = json.dumps(result.to_dict())
        self.assertNotIn("_SmokeChatMessage", serialized_json)
        self.assertNotIn("chat_model", serialized_json)

    def test_litellm_smoke_reports_adapter_failure_as_structured_response(self) -> None:
        env = {
            "NVIDIA_STARTUP_INTEL_LLM_PROVIDER": "litellm",
            "NVIDIA_STARTUP_INTEL_LLM_MODEL": "openrouter/error-smoke-fixture",
        }

        def failing_completion(**kwargs: object) -> object:
            raise RuntimeError("provider temporarily unavailable")

        with self.assertRaises(LLMAdapterSmokeError) as raised:
            run_litellm_adapter_smoke(env=env, completion=failing_completion)

        response = raised.exception.adapter_response
        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(response.schema_version, "llm_generation_response.v1")
        self.assertEqual(response.provider, "litellm")
        self.assertEqual(response.finish_reason, "adapter_error")
        self.assertEqual(response.metadata["adapter_error"], True)
        self.assertEqual(response.metadata["error_type"], "RuntimeError")
        self.assertEqual(
            raised.exception.serialized_response["metadata"]["error_message"],
            "provider temporarily unavailable",
        )

        serialized_json = json.dumps(raised.exception.serialized_response)
        self.assertNotIn("traceback", serialized_json)
        self.assertNotIn("choices", serialized_json)


class _SmokeChatMessage:
    def __init__(self, *, content: str, response_metadata: dict[str, object]) -> None:
        self.content = content
        self.response_metadata = response_metadata


class _SmokeChatModel:
    def __init__(self, response: _SmokeChatMessage) -> None:
        self.response = response
        self.messages: tuple[tuple[str, str], ...] = ()

    def invoke(self, messages: list[tuple[str, str]]) -> _SmokeChatMessage:
        self.messages = tuple(messages)
        return self.response


if __name__ == "__main__":
    unittest.main()
