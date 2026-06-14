from datetime import UTC, datetime

from nvidia_startup_intel.discovery import RawDiscoveryResult
from nvidia_startup_intel.page_collection import FetchResponse
from nvidia_startup_intel.pipeline import fixture_fetcher, run_scraping_pipeline
from nvidia_startup_intel.sql_repository import sqlite_repository


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
        limit=1,
        max_pages_per_candidate=1,
    )

    repository.save_pipeline_result(run_id, result, raw_discovery_results=raw_results)
    loaded = repository.load_run(run_id)

    assert loaded.run_id == "run-sql"
    assert loaded.search_params["raw_query"] == "startups AI-native do Brasil"
    assert loaded.search_plan_items[0]["term"]
    assert loaded.raw_discovery_results[0]["title"] == "NeuralMind"
    assert loaded.candidate_startups[0]["name"] == "NeuralMind"
    assert loaded.collected_pages[0]["url"] == "https://neuralmind.ai/"
    assert loaded.startup_profiles[0]["schema_version"] == "startup_profile.v1"
    assert loaded.field_evidences
    assert loaded.collection_quality_summaries[0]["candidate_count"] == 1
