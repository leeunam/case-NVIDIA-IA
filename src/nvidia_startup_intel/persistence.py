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

from nvidia_startup_intel.downstream_artifacts import (
    build_downstream_artifact_snapshot,
    build_downstream_briefing_artifact,
    build_downstream_recommendation_artifact,
    build_downstream_retrieval_artifact,
    downstream_corpus_version,
    downstream_startup_identifier,
)


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
        snapshot = build_downstream_artifact_snapshot(state)

        if snapshot.retrievals:
            save_downstream_retrievals(
                self.run,
                tuple(item.retrieval for item in snapshot.retrievals),
                startup_identifier=snapshot.startup_identifier,
            )
        if snapshot.recommendation is not None:
            save_downstream_recommendation_set(self.run, snapshot.recommendation.recommendation_set)
        for briefing in snapshot.briefings:
            _write_json(
                _downstream_artifact_path(self.run, briefing.startup_identifier, briefing.filename),
                briefing.payload,
            )
        for metrics in snapshot.metrics:
            _write_json(
                _downstream_artifact_path(self.run, metrics.startup_identifier, metrics.filename),
                metrics.payload,
            )


class JsonIntelligenceArtifactStore:
    """Persist complete intelligence workflow artifacts in a JSON run directory."""

    def __init__(
        self,
        base_dir: str | Path,
        *,
        created_at: datetime | None = None,
    ) -> None:
        self.base_dir = Path(base_dir)
        self.created_at = created_at
        self.run: PipelineRun | None = None

    def create_run(self, *, run_id: str) -> str:
        if self.run is not None:
            if self.run.run_id != run_id:
                raise ValueError(f"json_store_run_id_mismatch:{self.run.run_id}:{run_id}")
            return self.run.run_id

        self.run = create_pipeline_run(
            self.base_dir,
            run_id=run_id,
            created_at=self.created_at,
        )
        return self.run.run_id

    def save_pipeline_result(self, run_id: str, result: Any) -> None:
        run = self._ensure_run(run_id)
        save_search_params(run, result.search_params)
        save_search_plan(run, result.search_plan)
        save_raw_discovery_results(run, result.raw_results)
        save_candidate_startups(run, result.candidates)
        save_collected_pages(run, result.collected_pages_by_candidate)
        save_startup_profiles(run, result.profiles)
        save_field_evidences(run, result.evidence_groups_by_profile)
        save_collection_quality(run, result.quality_summary)

    def save_ai_native_assessments(self, run_id: str, assessments_by_profile: Any) -> None:
        save_ai_native_assessments(self._ensure_run(run_id), assessments_by_profile)

    def save_downstream_state(self, state: dict[str, Any]) -> None:
        run = self._ensure_run(str(state.get("run_id", "unknown")))
        JsonDownstreamArtifactStore(run).save_downstream_state(state)

    def _ensure_run(self, run_id: str) -> PipelineRun:
        if self.run is None:
            self.create_run(run_id=run_id)
        assert self.run is not None
        return self.run


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
    retrieval_items = tuple(build_downstream_retrieval_artifact(retrieval) for retrieval in retrievals)
    corpus_version = downstream_corpus_version(retrieval_items)
    return _write_json(
        _downstream_artifact_path(run, startup_identifier, "retrievals.json"),
        {
            "run_id": run.run_id,
            "startup_identifier": startup_identifier,
            "corpus_version": corpus_version,
            "items": tuple(item.payload for item in retrieval_items),
        },
    )


def save_downstream_recommendation_set(run: PipelineRun, recommendation_set: Any) -> Path:
    artifact = build_downstream_recommendation_artifact(recommendation_set)
    return _write_json(
        _downstream_artifact_path(run, artifact.startup_identifier, "recommendation_set.json"),
        artifact.payload,
    )


def save_downstream_briefing(run: PipelineRun, briefing: Any) -> Path:
    artifact = build_downstream_briefing_artifact(briefing)
    return _write_json(_downstream_artifact_path(run, artifact.startup_identifier, artifact.filename), artifact.payload)


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
    briefing_narrative: Any = None,
    profile: Any = None,
    assessment: Any = None,
) -> str:
    return downstream_startup_identifier(
        recommendation_set=recommendation_set,
        executive_briefing=executive_briefing,
        human_review_briefing=human_review_briefing,
        briefing_narrative=briefing_narrative,
        profile=profile,
        assessment=assessment,
    )


def _downstream_artifact_path(run: PipelineRun, startup_identifier: str, filename: str) -> Path:
    return run.processed_dir / "downstream" / _safe_path_segment(startup_identifier) / filename


def _safe_path_segment(value: str) -> str:
    segment = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip(".-")
    return segment or "unknown"


def _downstream_corpus_version(retrievals: tuple[Any, ...]) -> str:
    return downstream_corpus_version(retrievals)


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
