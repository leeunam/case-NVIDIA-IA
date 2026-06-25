"""Persist intermediate pipeline results by execution.

Story 8 stores raw and processed artifacts separately so collection can be
reused while later extraction/profile steps are reprocessed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from enum import Enum
import json
from pathlib import Path
import shutil
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class PipelineRun:
    run_id: str
    root_dir: Path
    raw_dir: Path
    processed_dir: Path
    created_at: str


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


def save_collection_quality(run: PipelineRun, quality_summary: Any) -> Path:
    return _write_json(run.processed_dir / "collection_quality.json", quality_summary)


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
