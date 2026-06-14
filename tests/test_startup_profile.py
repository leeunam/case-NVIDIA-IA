import json

from nvidia_startup_intel.page_collection import CollectedPage
from nvidia_startup_intel.startup_profile import (
    ClaimSource,
    SCHEMA_VERSION,
    extract_startup_profile,
    startup_profile_to_dict,
)


COLLECTED_AT = "2026-06-14T12:00:00+00:00"


def test_extract_profile_from_structured_collected_pages() -> None:
    pages = (
        CollectedPage(
            url="https://neuralmind.ai/",
            title="NeuralMind | Inteligencia Artificial",
            main_text=(
                "Resumo: A NeuralMind desenvolve soluções de inteligência artificial para documentos. "
                "Setor: dados. Produto: Plataforma de IA para leitura de documentos. "
                "Clientes: bancos e seguradoras. Funding: unknown. "
                "Founders: Roberto Lotufo, Rodrigo Nogueira. "
                "Tecnologias: machine learning, NLP, modelos de IA. "
                "Sinais de IA: modelos de IA proprietarios para processamento de linguagem. "
                "Localizacao: Campinas, SP."
            ),
            collected_at=COLLECTED_AT,
            status_code=200,
        ),
        CollectedPage(
            url="https://neuralmind.ai/produtos",
            title="Produtos | NeuralMind",
            main_text="Produto: APIs de IA para automacao documental.",
            collected_at=COLLECTED_AT,
            status_code=200,
        ),
    )

    profile = extract_startup_profile(pages)

    assert profile.schema_version == SCHEMA_VERSION
    assert profile.company_name.value == "NeuralMind"
    assert profile.official_site.value == "https://neuralmind.ai"
    assert profile.company_summary.value.startswith("A NeuralMind desenvolve")
    assert profile.sector.value == "dados"
    assert profile.product.value == "Plataforma de IA para leitura de documentos"
    assert profile.customers.value == "bancos e seguradoras"
    assert profile.funding.value == "unknown"
    assert profile.founders.value == "Roberto Lotufo, Rodrigo Nogueira"
    assert profile.technologies_used.value == "machine learning, NLP, modelos de IA"
    assert profile.ai_signals.value == "modelos de IA proprietarios para processamento de linguagem"
    assert profile.location.value == "Campinas, SP"
    assert profile.product.claim_source is ClaimSource.OBSERVED
    assert profile.product.evidences[0].url == "https://neuralmind.ai/"
    assert "Plataforma de IA" in profile.product.evidences[0].snippet


def test_extract_profile_infers_sector_and_ai_signals_when_labels_are_absent() -> None:
    pages = (
        CollectedPage(
            url="https://visionhealth.ai/",
            title="VisionHealth AI",
            main_text=(
                "A VisionHealth AI e uma healthtech brasileira que usa computer vision "
                "e machine learning para apoiar triagem clinica."
            ),
            collected_at=COLLECTED_AT,
            status_code=200,
        ),
    )

    profile = extract_startup_profile(pages)

    assert profile.company_name.value == "VisionHealth AI"
    assert profile.sector.value == "healthtech"
    assert profile.sector.claim_source is ClaimSource.INFERRED
    assert profile.ai_signals.value == "computer vision, machine learning"
    assert profile.ai_signals.claim_source is ClaimSource.INFERRED
    assert len(profile.ai_signals.evidences) == 2


def test_missing_fields_return_unknown_without_evidence() -> None:
    pages = (
        CollectedPage(
            url="https://minimal.ai/",
            title="Minimal AI",
            main_text="Empresa brasileira de software.",
            collected_at=COLLECTED_AT,
            status_code=200,
        ),
    )

    profile = extract_startup_profile(pages)

    assert profile.product.value == "unknown"
    assert profile.product.claim_source is ClaimSource.UNKNOWN
    assert profile.product.evidences == ()
    assert profile.funding.value == "unknown"
    assert profile.funding.evidences == ()


def test_profile_can_be_serialized_as_json_schema_dict() -> None:
    pages = (
        CollectedPage(
            url="https://profile.ai/",
            title="Profile AI",
            main_text="Resumo: Plataforma de IA. Setor: fintech.",
            collected_at=COLLECTED_AT,
            status_code=200,
        ),
    )

    profile_dict = startup_profile_to_dict(extract_startup_profile(pages))

    assert profile_dict["schema_version"] == SCHEMA_VERSION
    assert profile_dict["sector"]["claim_source"] == "observed"
    assert profile_dict["product"]["value"] == "unknown"
    json.dumps(profile_dict)
