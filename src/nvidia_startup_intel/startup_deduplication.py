"""Startup normalization and conservative deduplication.

Story 7 consolidates candidate startups while preserving every discovery
evidence that led to them. The matching rules are intentionally conservative:
domain matches and known aliases are strong signals; similar names alone are
not enough unless the similarity is an obvious legal/name variant.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from nvidia_startup_intel.normalization import normalize_domain, normalize_startup_name, normalize_url
from nvidia_startup_intel.search_params import UNKNOWN

if TYPE_CHECKING:
    from nvidia_startup_intel.discovery import CandidateStartup, DiscoveryEvidence


def deduplicate_startups(
    candidates: list["CandidateStartup"] | tuple["CandidateStartup", ...],
    *,
    aliases: dict[str, tuple[str, ...]] | None = None,
) -> tuple["CandidateStartup", ...]:
    """Consolidate duplicate startups and preserve all discovery evidences."""

    alias_groups = _normalize_alias_groups(aliases or {})
    consolidated: list[CandidateStartup] = []

    for candidate in candidates:
        normalized_candidate = _normalize_candidate(candidate)
        match_index = _find_duplicate_index(normalized_candidate, consolidated, alias_groups)
        if match_index is None:
            consolidated.append(normalized_candidate)
            continue

        consolidated[match_index] = _merge_candidates(consolidated[match_index], normalized_candidate)

    return tuple(sorted(consolidated, key=lambda candidate: (-candidate.confidence_score, candidate.name)))


def _find_duplicate_index(
    candidate: "CandidateStartup",
    existing_candidates: list["CandidateStartup"],
    alias_groups: dict[str, str],
) -> int | None:
    candidate_domain = normalize_domain(candidate.primary_url)
    candidate_alias_key = alias_groups.get(candidate.normalized_name, candidate.normalized_name)

    for index, existing in enumerate(existing_candidates):
        existing_domain = normalize_domain(existing.primary_url)
        if (
            _has_company_source(candidate)
            and _has_company_source(existing)
            and candidate_domain != UNKNOWN
            and existing_domain != UNKNOWN
            and candidate_domain == existing_domain
        ):
            return index

        existing_alias_key = alias_groups.get(existing.normalized_name, existing.normalized_name)
        if candidate_alias_key == existing_alias_key:
            if _has_conflicting_company_domains(candidate, existing):
                continue
            return index

        if candidate_domain == UNKNOWN and existing_domain == UNKNOWN and _is_obvious_name_variant(
            candidate.normalized_name,
            existing.normalized_name,
        ):
            return index

    return None


def _is_obvious_name_variant(left: str, right: str) -> bool:
    if left == UNKNOWN or right == UNKNOWN:
        return False
    if left == right:
        return True
    left_tokens = left.split()
    right_tokens = right.split()
    if min(len(left_tokens), len(right_tokens)) < 2:
        return False
    shorter, longer = sorted((left_tokens, right_tokens), key=len)
    return longer[: len(shorter)] == shorter


def _merge_candidates(existing: "CandidateStartup", new: "CandidateStartup") -> "CandidateStartup":
    evidences = _dedupe_evidences(existing.evidences + new.evidences)
    source_types = tuple(dict.fromkeys(existing.source_types + new.source_types))
    name = _preferred_name(existing.name, new.name)
    primary_url = _preferred_url(existing, new)
    confidence_score = round(
        max(existing.confidence_score, new.confidence_score)
        + _additional_evidence_bonus(existing.evidences, evidences),
        2,
    )

    return replace(
        existing,
        name=name,
        normalized_name=normalize_startup_name(name),
        primary_url=primary_url,
        discovery_source=existing.discovery_source,
        evidence_snippet=existing.evidence_snippet,
        confidence_score=min(confidence_score, 0.99),
        source_types=source_types,
        evidences=evidences,
    )


def _normalize_candidate(candidate: "CandidateStartup") -> "CandidateStartup":
    primary_url = normalize_url(candidate.primary_url)
    name = candidate.name.strip()
    return replace(
        candidate,
        name=name,
        normalized_name=normalize_startup_name(name),
        primary_url=primary_url,
    )


def _dedupe_evidences(evidences: tuple["DiscoveryEvidence", ...]) -> tuple["DiscoveryEvidence", ...]:
    unique: dict[tuple[str, str], DiscoveryEvidence] = {}
    for evidence in evidences:
        unique[(normalize_url(evidence.url), evidence.snippet)] = evidence
    return tuple(unique.values())


def _preferred_name(existing_name: str, new_name: str) -> str:
    if len(new_name) < len(existing_name):
        return new_name
    return existing_name


def _preferred_url(existing: "CandidateStartup", new: "CandidateStartup") -> str:
    if _has_company_source(new) and not _has_company_source(existing) and new.primary_url != UNKNOWN:
        return new.primary_url
    if existing.primary_url != UNKNOWN:
        return existing.primary_url
    return new.primary_url


def _has_company_source(candidate: "CandidateStartup") -> bool:
    return any(getattr(source_type, "value", source_type) == "company" for source_type in candidate.source_types)


def _has_conflicting_company_domains(left: "CandidateStartup", right: "CandidateStartup") -> bool:
    if not (_has_company_source(left) and _has_company_source(right)):
        return False
    left_domain = normalize_domain(left.primary_url)
    right_domain = normalize_domain(right.primary_url)
    return left_domain != UNKNOWN and right_domain != UNKNOWN and left_domain != right_domain


def _additional_evidence_bonus(
    existing_evidences: tuple["DiscoveryEvidence", ...],
    merged_evidences: tuple["DiscoveryEvidence", ...],
) -> float:
    existing_bonus = min(len(existing_evidences) - 1, 2) * 0.05
    merged_bonus = min(len(merged_evidences) - 1, 2) * 0.05
    return max(merged_bonus - existing_bonus, 0.0)


def _normalize_alias_groups(aliases: dict[str, tuple[str, ...]]) -> dict[str, str]:
    groups: dict[str, str] = {}
    for canonical_name, alias_names in aliases.items():
        canonical_key = normalize_startup_name(canonical_name)
        groups[canonical_key] = canonical_key
        for alias_name in alias_names:
            groups[normalize_startup_name(alias_name)] = canonical_key
    return groups
