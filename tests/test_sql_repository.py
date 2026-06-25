from datetime import UTC, datetime
from pathlib import Path
import re
import sqlite3

import pytest

from nvidia_startup_intel.discovery import RawDiscoveryResult
from nvidia_startup_intel.page_collection import FetchResponse, PageCollectionError, PageCollectionResult
from nvidia_startup_intel.pipeline import fixture_fetcher, run_scraping_pipeline
from nvidia_startup_intel.robots import RobotsCache
from nvidia_startup_intel.sql_repository import POSTGRES_SCHEMA_STATEMENTS, sqlite_repository


def allow_robots() -> RobotsCache:
    return RobotsCache(fetcher=lambda url: "User-agent: *\nAllow: /\n")


def test_sql_repository_saves_and_loads_complete_pipeline_run() -> None:
    repository = sqlite_repository()
    run_id = repository.create_run(
        run_id="run-sql",
        created_at=datetime(2026, 6, 14, 12, 0, tzinfo=UTC),
    )
    raw_results = (
        RawDiscoveryResult(
            title="NeuralMind",
            url="https://neuralmind.ai/",
            snippet="NeuralMind desenvolve IA para documentos.",
            source_name="web",
            discovered_name="NeuralMind",
        ),
    )
    result = run_scraping_pipeline(
        "startups AI-native do Brasil",
        raw_results,
        fetcher=fixture_fetcher(
            {
                "https://neuralmind.ai": FetchResponse(
                    url="https://neuralmind.ai/",
                    status_code=200,
                    body=(
                        "<html><head><title>NeuralMind</title></head><body>"
                        "Resumo: IA para documentos. Setor: dados. "
                        "Produto: Plataforma de IA documental. "
                        "Sinais de IA: modelos de IA proprietarios. "
                        "Tecnologias: machine learning."
                        "</body></html>"
                    ),
                )
            }
        ),
        robots_cache=allow_robots(),
        limit=1,
        max_pages_per_candidate=1,
    )

    repository.save_pipeline_result(run_id, result)
    loaded = repository.load_run(run_id)

    assert loaded.run_id == "run-sql"
    assert loaded.search_params["raw_query"] == "startups AI-native do Brasil"
    assert loaded.search_plan_items[0]["term"]
    assert loaded.search_plan_items[0]["priority"] == 1
    assert loaded.raw_discovery_results[0]["title"] == "NeuralMind"
    assert loaded.raw_discovery_results[0]["position"] == 1
    assert loaded.candidate_startups[0]["name"] == "NeuralMind"
    assert loaded.candidate_startups[0]["candidate_key"] == "url:https://neuralmind.ai"
    assert loaded.collected_pages[0]["url"] == "https://neuralmind.ai"
    assert loaded.collected_pages[0]["candidate_key"] == "url:https://neuralmind.ai"
    assert loaded.collected_pages[0]["candidate_name"] == "NeuralMind"
    assert loaded.collected_pages[0]["is_error"] is False
    assert loaded.startup_profiles[0]["schema_version"] == "startup_profile.v1"
    assert loaded.startup_profiles[0]["profile_key"] == "url:https://neuralmind.ai"
    assert loaded.startup_profiles[0]["company_name"] == "NeuralMind"
    assert loaded.field_evidences
    assert loaded.field_evidences[0]["profile_key"] == "url:https://neuralmind.ai"
    assert loaded.field_evidences[0]["company_name"] == "NeuralMind"
    assert loaded.field_evidences[0]["field_name"]
    assert loaded.field_evidences[0]["evidence_url"] == loaded.field_evidences[0]["evidence"]["url"]
    assert loaded.collection_quality_summaries[0]["candidate_count"] == 1
    assert loaded.collection_quality_summaries[0]["ready_for_evaluation"] is True


def test_sql_repository_loads_collected_page_error_metadata() -> None:
    repository = sqlite_repository()
    run_id = repository.create_run(run_id="run-sql-error")

    repository.save_collected_pages(
        run_id,
        {
            "Startup Falha": PageCollectionResult(
                pages=(),
                errors=(
                    PageCollectionError(
                        url="https://falha.ai/sobre",
                        error_type="TimeoutError",
                        message="timeout",
                        collected_at="2026-06-14T12:00:00+00:00",
                        error_category="timeout",
                    ),
                ),
            )
        },
    )

    loaded = repository.load_run(run_id)

    assert loaded.collected_pages[0]["candidate_name"] == "Startup Falha"
    assert loaded.collected_pages[0]["candidate_key"] == "Startup Falha"
    assert loaded.collected_pages[0]["is_error"] is True
    assert loaded.collected_pages[0]["url"] == "https://falha.ai/sobre"
    assert loaded.collected_pages[0]["error_type"] == "TimeoutError"


def test_sql_repository_rejects_child_rows_for_missing_run() -> None:
    repository = sqlite_repository()

    with pytest.raises(sqlite3.IntegrityError):
        repository.save_raw_discovery_results(
            "missing-run",
            (
                RawDiscoveryResult(
                    title="NeuralMind",
                    url="https://neuralmind.ai",
                    snippet="IA para documentos.",
                    source_name="web",
                ),
            ),
        )


def test_save_pipeline_result_rolls_back_partial_writes_on_failure() -> None:
    repository = sqlite_repository()
    run_id = repository.create_run(run_id="run-rollback")
    raw_results = (
        RawDiscoveryResult(
            title="NeuralMind",
            url="https://neuralmind.ai/",
            snippet="NeuralMind desenvolve IA para documentos.",
            source_name="web",
            discovered_name="NeuralMind",
        ),
    )
    result = run_scraping_pipeline(
        "startups AI-native do Brasil",
        raw_results,
        fetcher=fixture_fetcher(
            {
                "https://neuralmind.ai": FetchResponse(
                    url="https://neuralmind.ai/",
                    status_code=200,
                    body="<html><head><title>NeuralMind</title></head><body>Resumo: IA.</body></html>",
                )
            }
        ),
        robots_cache=allow_robots(),
        limit=1,
        max_pages_per_candidate=1,
    )

    def fail_save_startup_profiles(*args, **kwargs):
        raise RuntimeError("profile write failed")

    repository.save_startup_profiles = fail_save_startup_profiles

    with pytest.raises(RuntimeError, match="profile write failed"):
        repository.save_pipeline_result(run_id, result)

    loaded = repository.load_run(run_id)
    assert loaded.search_params is None
    assert loaded.search_plan_items == ()
    assert loaded.raw_discovery_results == ()
    assert loaded.candidate_startups == ()
    assert loaded.collected_pages == ()


def test_postgres_schema_file_matches_repository_schema() -> None:
    schema_file = Path("db/schema.sql").read_text(encoding="utf-8")
    expected = "\n\n".join(f"{statement.strip()};" for statement in POSTGRES_SCHEMA_STATEMENTS)

    assert _normalize_sql(schema_file) == _normalize_sql(expected)


def test_docker_compose_mounts_schema_for_postgres_init() -> None:
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "./db/schema.sql:/docker-entrypoint-initdb.d/001-schema.sql:ro" in compose


def _normalize_sql(sql: str) -> list[str]:
    return [
        re.sub(r"\s+", " ", statement.strip()).rstrip(";")
        for statement in sql.split(";")
        if statement.strip()
    ]
