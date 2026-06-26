from __future__ import annotations

import os

import pytest

from nvidia_startup_intel.pgvector_smoke import PgvectorSmokeError, run_pgvector_smoke


pytestmark = pytest.mark.pgvector_integration


def test_pgvector_smoke_round_trips_fixture_against_real_postgres() -> None:
    if os.environ.get("NVIDIA_STARTUP_INTEL_RUN_PGVECTOR_SMOKE") != "1":
        pytest.skip(
            "optional pgvector smoke is disabled; set "
            "NVIDIA_STARTUP_INTEL_RUN_PGVECTOR_SMOKE=1 after starting Docker Compose"
        )

    try:
        result = run_pgvector_smoke()
    except PgvectorSmokeError as exc:
        pytest.fail(f"OPTIONAL PGVECTOR SMOKE FAILED: {exc}", pytrace=False)

    assert result.vector_extension_available is True
    assert result.corpus_version == "official-nvidia-fixture.v1"
    assert result.persisted_embeddings == result.persisted_chunks
    assert result.retrieval_strategy == "vector_semantic"
    assert result.retrieved_chunk_id == "nvidia-nim-developers:0"
