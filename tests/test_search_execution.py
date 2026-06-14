import json

import pytest

from nvidia_startup_intel.search_execution import (
    BraveSearchClient,
    SearchProviderResult,
    execute_search_plan,
    normalize_brave_response,
    search_client_from_env,
)
from nvidia_startup_intel.search_params import parse_search_params
from nvidia_startup_intel.search_plan import build_search_plan


class FakeSearchClient:
    provider_name = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, *, limit: int) -> tuple[SearchProviderResult, ...]:
        self.calls.append((query, limit))
        if "site:startse.com" in query:
            raise TimeoutError("provider timeout")
        return (
            SearchProviderResult(
                title=f"{query} Startup",
                url="https://startup.ai/",
                snippet="Startup brasileira com IA.",
                position=1,
            ),
        )


def test_executes_search_plan_with_limits_and_preserves_traceability() -> None:
    params = parse_search_params("startups AI-native de Sao Paulo", limit=2)
    plan = build_search_plan(params)
    client = FakeSearchClient()

    result = execute_search_plan(plan, client, per_term_limit=1, total_limit=2)

    assert len(result.raw_results) == 2
    assert result.errors == ()
    assert client.calls == [(plan.items[0].term, 1), (plan.items[1].term, 1)]
    assert result.raw_results[0].source_name == "web"
    assert "search_term=" in result.raw_results[0].snippet
    assert "position=1" in result.raw_results[0].snippet


def test_records_search_errors_without_stopping_execution() -> None:
    params = parse_search_params("startups AI-native", limit=4)
    plan = build_search_plan(params)
    client = FakeSearchClient()

    result = execute_search_plan(plan, client, per_term_limit=1, total_limit=4)

    assert len(result.raw_results) == 4
    assert len(result.errors) == 1
    assert result.errors[0].target_source == "StartSe"
    assert result.errors[0].error_type == "TimeoutError"


def test_normalizes_brave_response_contract() -> None:
    payload = {
        "web": {
            "results": [
                {
                    "title": "NeuralMind",
                    "url": "https://neuralmind.ai/",
                    "description": "IA para documentos.",
                },
                {
                    "title": "VisionHealth",
                    "url": "https://visionhealth.ai/",
                    "description": "Computer vision em saude.",
                },
            ]
        }
    }

    results = normalize_brave_response(payload, limit=1)

    assert results == (
        SearchProviderResult(
            title="NeuralMind",
            url="https://neuralmind.ai/",
            snippet="IA para documentos.",
            position=1,
        ),
    )


def test_brave_client_uses_configured_transport_without_exposing_key() -> None:
    seen_headers = {}

    def transport(request, timeout: int) -> bytes:
        seen_headers["token"] = request.headers["X-subscription-token"]
        seen_headers["timeout"] = timeout
        return json.dumps(
            {"web": {"results": [{"title": "A", "url": "https://a.ai/", "description": "Snippet"}]}}
        ).encode("utf-8")

    client = BraveSearchClient(api_key="secret", endpoint="https://search.example", timeout=7, transport=transport)

    assert client.search("startups IA", limit=1)[0].url == "https://a.ai/"
    assert seen_headers == {"token": "secret", "timeout": 7}


def test_search_client_from_env_requires_api_key_for_real_provider() -> None:
    with pytest.raises(ValueError, match="api_key is required"):
        search_client_from_env({"NVIDIA_STARTUP_INTEL_SEARCH_PROVIDER": "brave"})
