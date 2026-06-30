from __future__ import annotations

import json
from pathlib import Path
from io import StringIO

from nvidia_startup_intel.production_smoke_matrix import (
    ProductionSmokeMatrixContext,
    main,
    run_production_smoke_matrix,
)


def test_production_smoke_matrix_reports_skipped_passed_and_failed_integrations() -> None:
    def passing_runner(context: ProductionSmokeMatrixContext) -> dict[str, object]:
        assert context.integration_id == "playwright_collection"
        return {"collected_pages": 1}

    def failing_runner(context: ProductionSmokeMatrixContext) -> dict[str, object]:
        assert context.integration_id == "pgvector_retrieval"
        raise RuntimeError("pgvector extension is unavailable")

    result = run_production_smoke_matrix(
        env={
            "NVIDIA_STARTUP_INTEL_RUN_PLAYWRIGHT_COLLECTION_SMOKE": "1",
            "NVIDIA_STARTUP_INTEL_RUN_PGVECTOR_SMOKE": "1",
        },
        step_runners={
            "playwright_collection": passing_runner,
            "pgvector_retrieval": failing_runner,
        },
    )

    payload = result.to_dict()
    steps_by_id = {step["integration_id"]: step for step in payload["steps"]}

    assert payload["schema_version"] == "production_smoke_matrix.v1"
    assert payload["overall_status"] == "failed"
    assert steps_by_id["playwright_collection"]["status"] == "passed"
    assert steps_by_id["playwright_collection"]["bottleneck"] == "collection"
    assert steps_by_id["playwright_collection"]["payload"] == {"collected_pages": 1}
    assert steps_by_id["pgvector_retrieval"]["status"] == "failed"
    assert steps_by_id["pgvector_retrieval"]["bottleneck"] == "pgvector"
    assert "pgvector extension is unavailable" in steps_by_id["pgvector_retrieval"]["message"]
    assert steps_by_id["postgres_persistence"]["status"] == "skipped"
    assert "NVIDIA_STARTUP_INTEL_RUN_POSTGRES_PERSISTENCE_SMOKE=1" in (
        steps_by_id["postgres_persistence"]["message"]
    )
    json.dumps(payload)


def test_production_smoke_matrix_fails_step_without_serializing_leaked_credentials() -> None:
    secret = "secret-token-from-env"

    def leaking_runner(context: ProductionSmokeMatrixContext) -> dict[str, object]:
        assert context.integration_id == "groq_litellm_narrative"
        return {
            "provider": "litellm",
            "metadata": {"api_key": secret, "configured_api_key_env_var": "GROQ_API_KEY"},
        }

    result = run_production_smoke_matrix(
        env={
            "NVIDIA_STARTUP_INTEL_RUN_LLM_ADAPTER_SMOKE": "1",
            "NVIDIA_STARTUP_INTEL_LLM_PROVIDER": "litellm",
            "NVIDIA_STARTUP_INTEL_LLM_MODEL": "groq/smoke-model",
            "NVIDIA_STARTUP_INTEL_LLM_API_KEY_ENV": "GROQ_API_KEY",
            "GROQ_API_KEY": secret,
        },
        step_runners={"groq_litellm_narrative": leaking_runner},
        only=("groq_litellm_narrative",),
    )

    payload = result.to_dict()
    step = payload["steps"][0]
    serialized = json.dumps(payload)

    assert result.overall_status == "failed"
    assert step["status"] == "failed"
    assert step["bottleneck"] == "credential_hygiene"
    assert "credential leak detected" in step["message"]
    assert step["payload"]["metadata"]["api_key"] == "[REDACTED]"
    assert secret not in serialized


def test_production_smoke_matrix_scans_generated_artifacts_for_credential_leaks(
    tmp_path: Path,
) -> None:
    secret = "credential-in-generated-briefing"
    briefing_path = tmp_path / "processed" / "downstream" / "VetAI" / "briefing.json"
    briefing_path.parent.mkdir(parents=True)
    briefing_path.write_text(json.dumps({"llm_response": secret}), encoding="utf-8")

    def artifact_runner(context: ProductionSmokeMatrixContext) -> dict[str, object]:
        assert context.integration_id == "full_operational_smoke"
        return {
            "workflow_outcome": "briefing_generated",
            "briefing_reference": {
                "storage": "json",
                "path": str(briefing_path),
                "briefing_type": "executive",
            },
            "artifact_locations": {"json_run_dir": str(tmp_path)},
        }

    result = run_production_smoke_matrix(
        env={
            "NVIDIA_STARTUP_INTEL_RUN_FULL_PRODUCTION_SMOKE": "1",
            "GROQ_API_KEY": secret,
        },
        step_runners={"full_operational_smoke": artifact_runner},
        only=("full_operational_smoke",),
    )

    payload = result.to_dict()
    step = payload["steps"][0]
    serialized = json.dumps(payload)

    assert result.overall_status == "failed"
    assert step["status"] == "failed"
    assert step["bottleneck"] == "credential_hygiene"
    assert str(briefing_path) in step["payload"]["credential_scan"]["leaked_artifacts"]
    assert secret not in serialized


def test_production_smoke_matrix_main_outputs_selected_skipped_status() -> None:
    stdout = StringIO()

    exit_code = main(("--only", "postgres_persistence"), stdout=stdout)
    payload = json.loads(stdout.getvalue())

    assert exit_code == 0
    assert payload["schema_version"] == "production_smoke_matrix.v1"
    assert payload["overall_status"] == "skipped"
    assert [step["integration_id"] for step in payload["steps"]] == ["postgres_persistence"]
    assert payload["steps"][0]["status"] == "skipped"


def test_production_smoke_matrix_is_documented_with_operational_guidance() -> None:
    doc = Path("context/production-smoke-matrix.md").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    for required_text in (
        "Production Smoke Matrix",
        "NVIDIA_STARTUP_INTEL_RUN_PLAYWRIGHT_COLLECTION_SMOKE",
        "NVIDIA_STARTUP_INTEL_RUN_POSTGRES_PERSISTENCE_SMOKE",
        "NVIDIA_STARTUP_INTEL_RUN_PGVECTOR_SMOKE",
        "NVIDIA_STARTUP_INTEL_RUN_REAL_EMBEDDING_SMOKE",
        "NVIDIA_STARTUP_INTEL_RUN_HYBRID_RETRIEVAL_SMOKE",
        "NVIDIA_STARTUP_INTEL_RUN_REAL_RERANKING_SMOKE",
        "NVIDIA_STARTUP_INTEL_RUN_LANGGRAPH_CHECKPOINT_SMOKE",
        "NVIDIA_STARTUP_INTEL_RUN_LLM_ADAPTER_SMOKE",
        "NVIDIA_STARTUP_INTEL_RUN_FULL_PRODUCTION_SMOKE",
        "python -m nvidia_startup_intel.production_smoke_matrix",
        "Expected artifacts",
        "Cleanup",
        "Credential hygiene",
    ):
        assert required_text in doc

    assert "context/production-smoke-matrix.md" in readme
