import json

from nvidia_startup_intel.evidence import (
    FieldClaim,
    claims_from_profile,
    evidence_groups_to_dict,
    structure_evidence_by_field,
)
from nvidia_startup_intel.page_collection import CollectedPage
from nvidia_startup_intel.startup_profile import (
    FieldEvidence,
    extract_startup_profile,
)


COLLECTED_AT = "2026-06-14T12:00:00+00:00"


def evidence(url: str, snippet: str, title: str = "Fonte") -> FieldEvidence:
    return FieldEvidence(
        url=url,
        title=title,
        snippet=snippet,
        collected_at=COLLECTED_AT,
        source_type="collected_page",
    )


def test_groups_field_with_two_concordant_sources() -> None:
    groups = structure_evidence_by_field(
        (
            FieldClaim(
                field_name="sector",
                value="healthtech",
                evidences=(evidence("https://startup.ai/", "Setor: healthtech."),),
            ),
            FieldClaim(
                field_name="sector",
                value="healthtech",
                evidences=(evidence("https://startup.ai/sobre", "Healthtech brasileira."),),
            ),
        )
    )

    assert len(groups) == 1
    assert groups[0].field_name == "sector"
    assert groups[0].value == "healthtech"
    assert groups[0].has_conflict is False
    assert groups[0].conflicting_values == ()
    assert len(groups[0].evidences) == 2


def test_preserves_conflicting_field_values_and_marks_conflict() -> None:
    groups = structure_evidence_by_field(
        (
            FieldClaim(
                field_name="funding",
                value="seed",
                evidences=(evidence("https://startup.ai/news", "Rodada seed anunciada."),),
            ),
            FieldClaim(
                field_name="funding",
                value="series a",
                evidences=(evidence("https://startup.ai/about", "Empresa em Series A."),),
            ),
        )
    )

    assert len(groups) == 1
    assert groups[0].field_name == "funding"
    assert groups[0].has_conflict is True
    assert groups[0].conflicting_values == ("seed", "series a")
    assert len(groups[0].evidences) == 2


def test_claims_without_evidence_do_not_enter_as_facts() -> None:
    groups = structure_evidence_by_field(
        (
            FieldClaim(field_name="customers", value="Banco X", evidences=()),
            FieldClaim(
                field_name="product",
                value="Plataforma de IA",
                evidences=(evidence("https://startup.ai/", "Produto: Plataforma de IA."),),
            ),
        )
    )

    assert [group.field_name for group in groups] == ["product"]


def test_build_claims_from_startup_profile_for_audit() -> None:
    profile = extract_startup_profile(
        (
            CollectedPage(
                url="https://startup.ai/",
                title="Startup AI",
                main_text="Resumo: Plataforma de IA. Setor: fintech.",
                collected_at=COLLECTED_AT,
                status_code=200,
            ),
        )
    )

    groups = structure_evidence_by_field(claims_from_profile(profile))
    group_names = {group.field_name for group in groups}

    assert "company_summary" in group_names
    assert "sector" in group_names
    assert "product" not in group_names
    json.dumps(evidence_groups_to_dict(groups))
