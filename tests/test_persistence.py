from datetime import UTC, datetime

from nvidia_startup_intel.discovery import (
    RawDiscoveryResult,
    discover_candidate_startups,
)
from nvidia_startup_intel.ai_native_assessment import assess_ai_native_maturity
from nvidia_startup_intel.collection_quality import CollectionQualitySummary
from nvidia_startup_intel.evidence import claims_from_profile, structure_evidence_by_field
from nvidia_startup_intel.page_collection import CollectedPage
from nvidia_startup_intel.persistence import (
    create_pipeline_run,
    load_collected_pages,
    load_json,
    save_ai_native_assessments,
    save_candidate_startups,
    save_collected_pages,
    save_raw_discovery_results,
    save_search_params,
    save_search_plan,
    save_startup_profiles,
)
from nvidia_startup_intel.search_params import parse_search_params
from nvidia_startup_intel.search_plan import build_search_plan
from nvidia_startup_intel.startup_profile import extract_startup_profile


CREATED_AT = datetime(2026, 6, 14, 12, 0, tzinfo=UTC)
COLLECTED_AT = "2026-06-14T12:00:00+00:00"


def test_persists_pipeline_intermediate_results_with_run_id(tmp_path) -> None:
    run = create_pipeline_run(tmp_path, run_id="run-story-8", created_at=CREATED_AT)
    params = parse_search_params("startups AI-native de Minas Gerais", limit=2)
    plan = build_search_plan(params)
    raw_results = (
        RawDiscoveryResult(
            title="NeuralMind",
            url="https://www.neuralmind.ai/",
            snippet="NeuralMind desenvolve IA para documentos.",
            source_name="web",
            discovered_name="NeuralMind",
        ),
    )
    candidates = discover_candidate_startups(raw_results)
    pages = (
        CollectedPage(
            url="https://neuralmind.ai/",
            title="NeuralMind | Inteligencia Artificial",
            main_text="Resumo: IA para documentos. Setor: dados.",
            collected_at=COLLECTED_AT,
            status_code=200,
        ),
    )
    profiles = (extract_startup_profile(pages),)

    save_search_params(run, params)
    save_search_plan(run, plan)
    save_raw_discovery_results(run, raw_results)
    save_candidate_startups(run, candidates)
    save_collected_pages(run, pages)
    save_startup_profiles(run, profiles)

    manifest = load_json(run.root_dir / "manifest.json")
    search_params = load_json(run.processed_dir / "search_params.json")
    search_plan = load_json(run.processed_dir / "search_plan.json")
    discovery_results = load_json(run.raw_dir / "discovery_results.json")
    candidate_startups = load_json(run.processed_dir / "candidate_startups.json")
    collected_pages = load_json(run.raw_dir / "collected_pages.json")
    startup_profiles = load_json(run.processed_dir / "startup_profiles.json")

    assert manifest == {"created_at": "2026-06-14T12:00:00+00:00", "run_id": "run-story-8"}
    assert search_params["raw_query"] == "startups AI-native de Minas Gerais"
    assert search_plan["items"][0]["scope"] == "broad_web"
    assert discovery_results[0]["source_name"] == "web"
    assert candidate_startups[0]["name"] == "NeuralMind"
    assert collected_pages[0]["title"] == "NeuralMind | Inteligencia Artificial"
    assert startup_profiles[0]["schema_version"] == "startup_profile.v1"


def test_loads_raw_collected_pages_for_reprocessing_without_new_collection(tmp_path) -> None:
    run = create_pipeline_run(tmp_path, run_id="run-reprocess", created_at=CREATED_AT)
    pages = (
        CollectedPage(
            url="https://startup.ai/",
            title="Startup AI",
            main_text="Resumo: Plataforma de IA. Setor: fintech.",
            collected_at=COLLECTED_AT,
            status_code=200,
        ),
    )
    save_collected_pages(run, pages)

    loaded_pages = load_collected_pages(run)

    assert loaded_pages[0]["url"] == "https://startup.ai/"
    assert loaded_pages[0]["main_text"] == "Resumo: Plataforma de IA. Setor: fintech."
    assert not (run.raw_dir / "search_params.json").exists()
    assert not (run.processed_dir / "collected_pages.json").exists()


def test_persists_ai_native_assessments_as_processed_artifact(tmp_path) -> None:
    run = create_pipeline_run(tmp_path, run_id="run-assessment", created_at=CREATED_AT)
    profile = extract_startup_profile(
        (
            CollectedPage(
                url="https://deepdocs.ai/",
                title="DeepDocs",
                main_text=(
                    "Resumo: Plataforma AI-native. Setor: dados. Produto: IA para documentos. "
                    "Sinais de IA: modelos proprietarios e fine-tuning. "
                    "Tecnologias: inferencia em producao, MLOps, dados proprietarios e feedback loop."
                ),
                collected_at=COLLECTED_AT,
                status_code=200,
            ),
        )
    )
    groups = structure_evidence_by_field(claims_from_profile(profile))
    assessment = assess_ai_native_maturity(profile, groups, _ready_quality(), run_id=run.run_id)

    save_ai_native_assessments(run, {profile.company_name.value: assessment})

    loaded = load_json(run.processed_dir / "ai_native_assessments.json")
    assert loaded["DeepDocs"]["schema_version"] == "ai_native_assessment.v1"
    assert loaded["DeepDocs"]["classification"] == "ai_native"


def _ready_quality() -> CollectionQualitySummary:
    return CollectionQualitySummary(
        candidate_count=1,
        official_site_found_count=1,
        official_site_found_rate=1.0,
        minimum_profile_complete_count=1,
        minimum_profile_complete_rate=1.0,
        average_evidences_per_startup=6.0,
        unknown_fields=(),
        source_success_rates=(),
        ready_for_evaluation=True,
        readiness_reasons=("ready_for_ai_native_evaluation",),
    )
