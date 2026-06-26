"""Persist intermediate pipeline results by execution.

Raw and processed artifacts are stored separately so collection can be reused
while later extraction, assessment, recommendation, or briefing steps are
reprocessed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from enum import Enum
import json
from pathlib import Path
import re
import shutil
from typing import Any
from uuid import uuid4

from nvidia_startup_intel.briefing import executive_briefing_to_dict, human_review_briefing_to_dict
from nvidia_startup_intel.nvidia_knowledge import nvidia_knowledge_retrieval_to_dict
from nvidia_startup_intel.nvidia_recommendation import nvidia_recommendation_set_to_dict


@dataclass(frozen=True)
class PipelineRun:
    run_id: str
    root_dir: Path
    raw_dir: Path
    processed_dir: Path
    created_at: str


class JsonDownstreamArtifactStore:
    """Persist downstream workflow artifacts in a run's processed directory."""

    def __init__(self, run: PipelineRun) -> None:
        self.run = run

    def save_downstream_state(self, state: dict[str, Any]) -> None:
        retrievals = tuple(state.get("retrievals", ()))
        recommendation_set = state.get("recommendation_set")
        executive_briefing = state.get("executive_briefing")
        human_review_briefing = state.get("human_review_briefing")
        startup_identifier = _downstream_startup_identifier(
            recommendation_set=recommendation_set,
            executive_briefing=executive_briefing,
            human_review_briefing=human_review_briefing,
            profile=state.get("profile"),
            assessment=state.get("assessment"),
        )

        if retrievals:
            save_downstream_retrievals(
                self.run,
                retrievals,
                startup_identifier=startup_identifier,
            )
        if recommendation_set is not None:
            save_downstream_recommendation_set(self.run, recommendation_set)
        if executive_briefing is not None:
            save_downstream_briefing(self.run, executive_briefing)
        if human_review_briefing is not None:
            save_downstream_briefing(self.run, human_review_briefing)


def create_pipeline_run(
    base_dir: str | Path,
    *,
    run_id: str | None = None,
    created_at: datetime | None = None,
) -> PipelineRun:
    """Create a run directory with raw and processed artifact folders."""

    resolved_run_id = run_id or _new_run_id()
    created = created_at or datetime.now(UTC)
    root_dir = Path(base_dir) / resolved_run_id
    raw_dir = root_dir / "raw"
    processed_dir = root_dir / "processed"

    root_dir.mkdir(parents=True, exist_ok=False)
    try:
        raw_dir.mkdir()
        processed_dir.mkdir()

        run = PipelineRun(
            run_id=resolved_run_id,
            root_dir=root_dir,
            raw_dir=raw_dir,
            processed_dir=processed_dir,
            created_at=_format_time(created),
        )
        _write_json(root_dir / "manifest.json", {"run_id": run.run_id, "created_at": run.created_at})
        return run
    except Exception:
        shutil.rmtree(root_dir, ignore_errors=True)
        raise


def save_search_params(run: PipelineRun, params: Any) -> Path:
    return _write_json(run.processed_dir / "search_params.json", params)


def save_search_plan(run: PipelineRun, plan: Any) -> Path:
    return _write_json(run.processed_dir / "search_plan.json", plan)


def save_raw_discovery_results(run: PipelineRun, results: Any) -> Path:
    return _write_json(run.raw_dir / "discovery_results.json", results)


def save_candidate_startups(run: PipelineRun, candidates: Any) -> Path:
    return _write_json(run.processed_dir / "candidate_startups.json", candidates)


def save_collected_pages(run: PipelineRun, pages: Any) -> Path:
    return _write_json(run.raw_dir / "collected_pages.json", pages)


def save_startup_profiles(run: PipelineRun, profiles: Any) -> Path:
    return _write_json(run.processed_dir / "startup_profiles.json", profiles)


def save_field_evidences(run: PipelineRun, evidences_by_profile: Any) -> Path:
    return _write_json(run.processed_dir / "field_evidences.json", evidences_by_profile)


def save_collection_quality(run: PipelineRun, quality_summary: Any) -> Path:
    return _write_json(run.processed_dir / "collection_quality.json", quality_summary)


def save_ai_native_assessments(run: PipelineRun, assessments: Any) -> Path:
    return _write_json(run.processed_dir / "ai_native_assessments.json", assessments)


def save_downstream_retrievals(
    run: PipelineRun,
    retrievals: Any,
    *,
    startup_identifier: str,
) -> Path:
    retrieval_items = tuple(retrievals)
    corpus_version = _downstream_corpus_version(retrieval_items)
    return _write_json(
        _downstream_artifact_path(run, startup_identifier, "retrievals.json"),
        {
            "run_id": run.run_id,
            "startup_identifier": startup_identifier,
            "corpus_version": corpus_version,
            "items": tuple(nvidia_knowledge_retrieval_to_dict(retrieval) for retrieval in retrieval_items),
        },
    )


def save_downstream_recommendation_set(run: PipelineRun, recommendation_set: Any) -> Path:
    return _write_json(
        _downstream_artifact_path(run, recommendation_set.startup_identifier, "recommendation_set.json"),
        nvidia_recommendation_set_to_dict(recommendation_set),
    )


def save_downstream_briefing(run: PipelineRun, briefing: Any) -> Path:
    if getattr(briefing, "schema_version", "") == "human_review_briefing.v1":
        payload = human_review_briefing_to_dict(briefing)
    else:
        payload = executive_briefing_to_dict(briefing)
    return _write_json(_downstream_artifact_path(run, briefing.startup_identifier, "briefing.json"), payload)


def load_collected_pages(run: PipelineRun) -> dict[str, Any]:
    """Load raw collected pages for extraction reprocessing."""

    return load_json(run.raw_dir / "collected_pages.json")


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as file:
        return json.load(file)


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_to_jsonable(payload), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _downstream_startup_identifier(
    *,
    recommendation_set: Any,
    executive_briefing: Any,
    human_review_briefing: Any,
    profile: Any = None,
    assessment: Any = None,
) -> str:
    for artifact in (recommendation_set, executive_briefing, human_review_briefing):
        startup_identifier = getattr(artifact, "startup_identifier", None)
        if startup_identifier:
            return startup_identifier
    profile_company_name = getattr(getattr(profile, "company_name", None), "value", None)
    if profile_company_name:
        return str(profile_company_name)
    assessment_company_name = getattr(assessment, "company_name", None)
    if assessment_company_name:
        return str(assessment_company_name)
    return "unknown"


def _downstream_artifact_path(run: PipelineRun, startup_identifier: str, filename: str) -> Path:
    return run.processed_dir / "downstream" / _safe_path_segment(startup_identifier) / filename


def _safe_path_segment(value: str) -> str:
    segment = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip(".-")
    return segment or "unknown"


def _downstream_corpus_version(retrievals: tuple[Any, ...]) -> str:
    if not retrievals:
        return "unknown"
    return str(getattr(retrievals[0], "corpus_version", "unknown"))


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _to_jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item) for item in value]
    return value


def _new_run_id() -> str:
    now = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"run-{now}-{uuid4().hex[:8]}"


def _format_time(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()
