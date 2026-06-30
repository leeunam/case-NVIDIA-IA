from __future__ import annotations

import os

import pytest

from nvidia_startup_intel.postgres_persistence_smoke import (
    PostgresPersistenceSmokeError,
    run_postgres_persistence_smoke,
)


pytestmark = pytest.mark.postgres_persistence_integration

_RUN_ENV = "NVIDIA_STARTUP_INTEL_RUN_POSTGRES_PERSISTENCE_SMOKE"


def test_postgres_persistence_smoke_validates_complete_run_against_real_postgres() -> None:
    if os.environ.get(_RUN_ENV) != "1":
        pytest.skip(
            "optional Postgres persistence smoke is disabled; set "
            f"{_RUN_ENV}=1 after starting Docker Compose"
        )

    try:
        result = run_postgres_persistence_smoke()
    except PostgresPersistenceSmokeError as exc:
        pytest.fail(f"OPTIONAL POSTGRES PERSISTENCE SMOKE FAILED: {exc}", pytrace=False)

    assert result.schema_version == "postgres_persistence_smoke.v1"
    assert result.persisted_collected_pages >= 1
    assert result.persisted_ai_native_assessments >= 1
    assert result.persisted_retrievals >= 1
    assert result.persisted_recommendation_sets >= 1
    assert result.persisted_briefings >= 1
    assert result.persisted_metrics >= 1
    assert result.ready_for_reprocessing is True
