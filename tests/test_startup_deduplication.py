from nvidia_startup_intel.discovery import (
    CandidateStartup,
    DiscoveryEvidence,
    DiscoverySourceType,
)
from nvidia_startup_intel.startup_deduplication import (
    deduplicate_startups,
    normalize_domain,
    normalize_startup_name,
    normalize_url,
)


def evidence(url: str, snippet: str, source_name: str = "web") -> DiscoveryEvidence:
    return DiscoveryEvidence(
        url=url,
        title="Fonte",
        snippet=snippet,
        source_name=source_name,
        source_type=DiscoverySourceType.COMPANY,
    )


def candidate(
    name: str,
    url: str,
    snippet: str,
    *,
    score: float = 0.9,
    source_name: str = "web",
) -> CandidateStartup:
    return CandidateStartup(
        name=name,
        normalized_name=normalize_startup_name(name),
        primary_url=url,
        discovery_source=source_name,
        evidence_snippet=snippet,
        confidence_score=score,
        source_types=(DiscoverySourceType.COMPANY,),
        evidences=(evidence(url, snippet, source_name),),
    )


def test_normalizes_name_domain_and_url() -> None:
    assert normalize_startup_name("Exemplo AI Ltda.") == "exemplo ai"
    assert normalize_url("https://www.Exemplo.com.br/produto/?utm=x#top") == "https://exemplo.com.br/produto"
    assert normalize_domain("https://www.Exemplo.com.br/produto/?utm=x#top") == "exemplo.com.br"


def test_deduplicates_by_same_domain_and_preserves_all_sources() -> None:
    candidates = deduplicate_startups(
        (
            candidate("Aquarela", "https://www.aquare.la/", "Home oficial."),
            candidate("Aquarela Analytics", "https://aquare.la/blog/ia", "Blog oficial.", source_name="blog"),
        )
    )

    assert len(candidates) == 1
    assert candidates[0].name == "Aquarela"
    assert candidates[0].primary_url == "https://aquare.la/"
    assert candidates[0].normalized_name == "aquarela"
    assert len(candidates[0].evidences) == 2
    assert {evidence.source_name for evidence in candidates[0].evidences} == {"web", "blog"}


def test_deduplicates_by_known_aliases_without_domain() -> None:
    candidates = deduplicate_startups(
        (
            candidate("NeuralMind", "unknown", "Fonte de diretorio.", score=0.75, source_name="Distrito"),
            candidate("Neural Mind AI", "unknown", "Fonte de noticia.", score=0.65, source_name="NeoFeed"),
        ),
        aliases={"NeuralMind": ("Neural Mind AI",)},
    )

    assert len(candidates) == 1
    assert candidates[0].name == "NeuralMind"
    assert candidates[0].primary_url == "unknown"
    assert len(candidates[0].evidences) == 2


def test_deduplicates_obvious_name_variant_without_domain() -> None:
    candidates = deduplicate_startups(
        (
            candidate("Exemplo AI", "unknown", "Fonte de diretorio.", score=0.75, source_name="Distrito"),
            candidate("Exemplo AI Brasil", "unknown", "Fonte de evento.", score=0.7, source_name="Evento"),
        )
    )

    assert len(candidates) == 1
    assert candidates[0].name == "Exemplo AI"
    assert len(candidates[0].evidences) == 2


def test_does_not_merge_false_positive_similar_names_with_different_domains() -> None:
    candidates = deduplicate_startups(
        (
            candidate("DataMind", "https://datamind.ai", "IA para dados."),
            candidate("DataMind Health", "https://datamindhealth.com.br", "IA para saude."),
        )
    )

    assert len(candidates) == 2
    assert {item.normalized_name for item in candidates} == {"datamind", "datamind health"}
    assert {item.primary_url for item in candidates} == {
        "https://datamind.ai",
        "https://datamindhealth.com.br",
    }
