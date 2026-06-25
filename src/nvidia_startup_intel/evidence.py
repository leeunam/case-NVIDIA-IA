"""Evidence structuring and conflict detection by profile field.

Story 6 makes field-level claims auditable. It preserves all sourced claims,
supports multiple evidences per field, and marks fields with conflicting values.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from nvidia_startup_intel.normalization import normalize_text, normalize_whitespace
from nvidia_startup_intel.search_params import UNKNOWN
from nvidia_startup_intel.startup_profile import FieldEvidence, ProfileField, StartupProfile


@dataclass(frozen=True)
class FieldClaim:
    field_name: str
    value: str
    evidences: tuple[FieldEvidence, ...]


@dataclass(frozen=True)
class FieldEvidenceGroup:
    field_name: str
    value: str
    evidences: tuple[FieldEvidence, ...]
    has_conflict: bool
    conflicting_values: tuple[str, ...]


def structure_evidence_by_field(
    claims: list[FieldClaim] | tuple[FieldClaim, ...],
) -> tuple[FieldEvidenceGroup, ...]:
    """Group sourced field claims and mark conflicting values."""

    sourced_claims = [claim for claim in claims if claim.value != UNKNOWN and claim.evidences]
    claims_by_field: dict[str, list[FieldClaim]] = {}
    for claim in sourced_claims:
        claims_by_field.setdefault(claim.field_name, []).append(claim)

    groups: list[FieldEvidenceGroup] = []
    for field_name, field_claims in claims_by_field.items():
        values_by_key: dict[str, str] = {}
        evidences: list[FieldEvidence] = []

        for claim in field_claims:
            values_by_key.setdefault(_normalize_value(claim.value), claim.value)
            evidences.extend(claim.evidences)

        unique_values = tuple(values_by_key.values())
        has_conflict = len(unique_values) > 1
        groups.append(
            FieldEvidenceGroup(
                field_name=field_name,
                value=unique_values[0],
                evidences=_dedupe_evidences(tuple(evidences)),
                has_conflict=has_conflict,
                conflicting_values=unique_values if has_conflict else (),
            )
        )

    return tuple(sorted(groups, key=lambda group: group.field_name))


def claims_from_profile(profile: StartupProfile) -> tuple[FieldClaim, ...]:
    """Convert a StartupProfile into field claims for evidence auditing."""

    claims: list[FieldClaim] = []
    for field_name, field_value in profile.__dict__.items():
        if field_name == "schema_version" or not isinstance(field_value, ProfileField):
            continue
        claims.append(
            FieldClaim(
                field_name=field_name,
                value=field_value.value,
                evidences=field_value.evidences,
            )
        )
    return tuple(claims)


def evidence_groups_to_dict(groups: tuple[FieldEvidenceGroup, ...]) -> list[dict[str, object]]:
    """Convert evidence groups to JSON-serializable dictionaries."""

    return [asdict(group) for group in groups]


def _dedupe_evidences(evidences: tuple[FieldEvidence, ...]) -> tuple[FieldEvidence, ...]:
    unique: dict[tuple[str, str, str], FieldEvidence] = {}
    for evidence in evidences:
        unique[(evidence.url, evidence.snippet, evidence.source_type)] = evidence
    return tuple(unique.values())


def _normalize_value(value: str) -> str:
    return normalize_whitespace(normalize_text(value))
