from __future__ import annotations

import json
import os

import pytest

from nvidia_startup_intel.production_smoke_matrix import run_production_smoke_matrix


pytestmark = pytest.mark.production_smoke_matrix_integration

_RUN_ENV = "NVIDIA_STARTUP_INTEL_RUN_PRODUCTION_SMOKE_MATRIX"


def test_production_smoke_matrix_reports_clear_status_for_opt_in_integrations() -> None:
    if os.environ.get(_RUN_ENV) != "1":
        pytest.skip(
            "optional production smoke matrix is disabled; set "
            f"{_RUN_ENV}=1 and enable one or more integration-specific smoke flags"
        )

    only = tuple(
        item.strip()
        for item in os.environ.get("NVIDIA_STARTUP_INTEL_PRODUCTION_SMOKE_MATRIX_ONLY", "").split(",")
        if item.strip()
    )
    result = run_production_smoke_matrix(only=only)
    payload = result.to_dict()

    assert payload["schema_version"] == "production_smoke_matrix.v1"
    assert payload["overall_status"] in {"passed", "skipped", "failed"}
    assert payload["steps"]
    assert all(step["status"] in {"passed", "skipped", "failed"} for step in payload["steps"])
    assert all(step["bottleneck"] for step in payload["steps"])

    serialized = json.dumps(payload)
    for env_name, env_value in os.environ.items():
        if _is_sensitive_env_name(env_name) and len(env_value.strip()) >= 4:
            assert env_value not in serialized

    if result.overall_status == "failed":
        failed = [step for step in payload["steps"] if step["status"] == "failed"]
        pytest.fail(f"OPTIONAL PRODUCTION SMOKE MATRIX FAILED: {failed}", pytrace=False)


def _is_sensitive_env_name(name: str) -> bool:
    upper_name = name.upper()
    return any(marker in upper_name for marker in ("API_KEY", "TOKEN", "SECRET", "PASSWORD"))
