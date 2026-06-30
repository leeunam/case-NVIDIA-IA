from __future__ import annotations

import json
from pathlib import Path

from nvidia_startup_intel.postgres_persistence_smoke import run_postgres_persistence_smoke
from nvidia_startup_intel.sql_repository import sqlite_repository


def test_postgres_persistence_smoke_validates_complete_run_path_with_sqlite_repository() -> None:
    repository = sqlite_repository()

    result = run_postgres_persistence_smoke(
        repository_factory=lambda: repository,
        run_id="run-postgres-persistence-smoke-test",
    )

    payload = result.to_dict()
    loaded = repository.load_operational_run(
        "run-postgres-persistence-smoke-test",
        startup_identifier=result.startup_identifier,
    )

    json.dumps(payload)
    assert result.schema_version == "postgres_persistence_smoke.v1"
    assert result.startup_identifier == "VetAI"
    assert result.corpus_version == "official-nvidia-fixture.v1"
    assert result.persisted_collected_pages == 1
    assert result.persisted_ai_native_assessments == 1
    assert result.persisted_retrievals >= 1
    assert result.persisted_recommendation_sets == 1
    assert result.persisted_briefings == 1
    assert result.persisted_metrics == 1
    assert loaded.downstream.metrics[0]["schema_version"] == "downstream_metrics.v1"
    assert "secret" not in json.dumps(payload).lower()


def test_postgres_persistence_smoke_command_is_documented() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "PYTHONPATH=src python -m nvidia_startup_intel.postgres_persistence_smoke" in readme
    assert "NVIDIA_STARTUP_INTEL_RUN_POSTGRES_PERSISTENCE_SMOKE=1" in readme
