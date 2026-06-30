"""Shared downstream artifact projection for persistence adapters."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from nvidia_startup_intel.briefing import (
    briefing_narrative_to_dict,
    executive_briefing_to_dict,
    human_review_briefing_to_dict,
)
from nvidia_startup_intel.downstream_metrics import downstream_quality_report_to_dict
from nvidia_startup_intel.nvidia_knowledge import nvidia_knowledge_retrieval_to_dict
from nvidia_startup_intel.nvidia_recommendation import nvidia_recommendation_set_to_dict


@dataclass(frozen=True)
class DownstreamRetrievalArtifact:
    retrieval: Any
    corpus_version: str
    retrieval_strategy: str
    payload: dict[str, object]


@dataclass(frozen=True)
class DownstreamRecommendationArtifact:
    recommendation_set: Any
    startup_identifier: str
    corpus_version: str
    final_nvidia_opportunity_priority: str
    ready_for_briefing: bool
    payload: dict[str, object]


@dataclass(frozen=True)
class DownstreamBriefingArtifact:
    briefing: Any
    startup_identifier: str
    briefing_type: str
    status: str
    filename: str
    payload: dict[str, object]


@dataclass(frozen=True)
class DownstreamMetricsArtifact:
    report: Any
    startup_identifier: str
    schema_version: str
    corpus_version: str
    filename: str
    payload: dict[str, object]


@dataclass(frozen=True)
class DownstreamArtifactSnapshot:
    run_id: str
    startup_identifier: str
    retrievals: tuple[DownstreamRetrievalArtifact, ...]
    recommendation: DownstreamRecommendationArtifact | None
    briefings: tuple[DownstreamBriefingArtifact, ...]
    metrics: tuple[DownstreamMetricsArtifact, ...]


def build_downstream_artifact_snapshot(state: Mapping[str, Any]) -> DownstreamArtifactSnapshot:
    """Project runner state into storage-neutral downstream artifacts."""

    retrievals = tuple(state.get("retrievals", ()))
    recommendation_set = state.get("recommendation_set")
    executive_briefing = state.get("executive_briefing")
    human_review_briefing = state.get("human_review_briefing")
    briefing_narrative = state.get("briefing_narrative")
    startup_identifier = downstream_startup_identifier(
        recommendation_set=recommendation_set,
        executive_briefing=executive_briefing,
        human_review_briefing=human_review_briefing,
        briefing_narrative=briefing_narrative,
        profile=state.get("profile"),
        assessment=state.get("assessment"),
    )
    return DownstreamArtifactSnapshot(
        run_id=str(state.get("run_id", "unknown")),
        startup_identifier=startup_identifier,
        retrievals=tuple(build_downstream_retrieval_artifact(retrieval) for retrieval in retrievals),
        recommendation=(
            build_downstream_recommendation_artifact(recommendation_set)
            if recommendation_set is not None
            else None
        ),
        briefings=tuple(
            build_downstream_briefing_artifact(briefing)
            for briefing in (executive_briefing, human_review_briefing, briefing_narrative)
            if briefing is not None
        ),
        metrics=tuple(build_downstream_metrics_artifact(report) for report in _downstream_metric_reports(state)),
    )


def build_downstream_retrieval_artifact(retrieval: Any) -> DownstreamRetrievalArtifact:
    return DownstreamRetrievalArtifact(
        retrieval=retrieval,
        corpus_version=str(getattr(retrieval, "corpus_version", "unknown")),
        retrieval_strategy=downstream_retrieval_strategy(retrieval),
        payload=nvidia_knowledge_retrieval_to_dict(retrieval),
    )


def build_downstream_recommendation_artifact(recommendation_set: Any) -> DownstreamRecommendationArtifact:
    return DownstreamRecommendationArtifact(
        recommendation_set=recommendation_set,
        startup_identifier=str(getattr(recommendation_set, "startup_identifier", "unknown")),
        corpus_version=str(getattr(recommendation_set, "corpus_version", "unknown")),
        final_nvidia_opportunity_priority=str(
            getattr(recommendation_set, "final_nvidia_opportunity_priority", "unknown")
        ),
        ready_for_briefing=bool(getattr(getattr(recommendation_set, "quality", None), "ready_for_briefing", False)),
        payload=nvidia_recommendation_set_to_dict(recommendation_set),
    )


def build_downstream_briefing_artifact(briefing: Any) -> DownstreamBriefingArtifact:
    briefing_type = downstream_briefing_type(briefing)
    return DownstreamBriefingArtifact(
        briefing=briefing,
        startup_identifier=str(getattr(briefing, "startup_identifier", "unknown")),
        briefing_type=briefing_type,
        status=downstream_briefing_status(briefing),
        filename=downstream_briefing_filename(briefing_type),
        payload=downstream_briefing_payload(briefing, briefing_type=briefing_type),
    )


def build_downstream_metrics_artifact(report: Any) -> DownstreamMetricsArtifact:
    payload = downstream_quality_report_to_dict(report)
    return DownstreamMetricsArtifact(
        report=report,
        startup_identifier=str(payload.get("startup_identifier", "unknown")),
        schema_version=str(payload.get("schema_version", "unknown")),
        corpus_version=str(payload.get("corpus_version", "unknown")),
        filename="metrics.json",
        payload=payload,
    )


def _downstream_metric_reports(state: Mapping[str, Any]) -> tuple[Any, ...]:
    report = state.get("downstream_quality_report")
    if report is None:
        return ()
    if isinstance(report, Sequence) and not isinstance(report, (str, bytes, bytearray, Mapping)):
        return tuple(report)
    return (report,)


def downstream_startup_identifier(
    *,
    recommendation_set: Any = None,
    executive_briefing: Any = None,
    human_review_briefing: Any = None,
    briefing_narrative: Any = None,
    profile: Any = None,
    assessment: Any = None,
) -> str:
    for artifact in (recommendation_set, executive_briefing, human_review_briefing, briefing_narrative):
        startup_identifier = getattr(artifact, "startup_identifier", None)
        if startup_identifier:
            return str(startup_identifier)
    profile_company_name = getattr(getattr(profile, "company_name", None), "value", None)
    if profile_company_name:
        return str(profile_company_name)
    assessment_company_name = getattr(assessment, "company_name", None)
    if assessment_company_name:
        return str(assessment_company_name)
    return "unknown"


def downstream_corpus_version(retrievals: Sequence[Any] | Sequence[DownstreamRetrievalArtifact]) -> str:
    if not retrievals:
        return "unknown"
    first = retrievals[0]
    return str(getattr(first, "corpus_version", "unknown"))


def downstream_retrieval_strategy(retrieval: Any) -> str:
    if getattr(retrieval, "results", ()):
        return str(retrieval.results[0].retrieval_strategy)
    return "none"


def downstream_briefing_type(briefing: Any) -> str:
    schema_version = getattr(briefing, "schema_version", "")
    if schema_version == "human_review_briefing.v1":
        return "human_review"
    if schema_version == "briefing_narrative.v1":
        return "briefing_narrative"
    return "executive"


def downstream_briefing_status(briefing: Any) -> str:
    status = getattr(briefing, "status", None)
    if status:
        return str(status)
    return str(getattr(briefing, "source_briefing_status", "unknown"))


def downstream_briefing_payload(briefing: Any, *, briefing_type: str | None = None) -> dict[str, object]:
    resolved_type = briefing_type or downstream_briefing_type(briefing)
    if resolved_type == "human_review":
        return human_review_briefing_to_dict(briefing)
    if resolved_type == "briefing_narrative":
        return briefing_narrative_to_dict(briefing)
    return executive_briefing_to_dict(briefing)


def downstream_briefing_filename(briefing_type: str) -> str:
    if briefing_type == "briefing_narrative":
        return "briefing_narrative.json"
    return "briefing.json"
