from __future__ import annotations

from pathlib import Path
import unittest

from nvidia_startup_intel.ai_native_assessment import (
    AINativeAssessment,
    DiagnosticQuality,
    TechnicalGap,
)
from nvidia_startup_intel.collection_quality import CollectionQualitySummary
from nvidia_startup_intel.evidence import FieldEvidenceGroup
from nvidia_startup_intel.nvidia_knowledge import (
    NVIDIAKnowledgeChunk,
    NVIDIAKnowledgeDocument,
    NVIDIAKnowledgeRetrieval,
    RetrievedNVIDIAKnowledge,
    load_nvidia_knowledge_corpus,
    nvidia_citation_from_chunk,
    retrieve_nvidia_knowledge_by_gap,
)
from nvidia_startup_intel.nvidia_recommendation import build_nvidia_recommendations
from nvidia_startup_intel.search_params import UNKNOWN
from nvidia_startup_intel.startup_profile import ClaimSource, FieldEvidence, ProfileField, StartupProfile


class NVIDIARecommendationTests(unittest.TestCase):
    def test_supported_recommendations_cover_four_controlled_gap_types_and_rank_by_need(self) -> None:
        evidence_by_gap = {
            "model_serving": _startup_evidence(
                snippet="A VetAI precisa reduzir latencia de inferencia em producao."
            ),
            "data_acceleration": _startup_evidence(
                snippet="A VetAI processa grandes volumes de dados para treinamento e analise."
            ),
            "computer_vision": _startup_evidence(
                snippet="A VetAI analisa video e imagens em tempo real para triagem."
            ),
            "llm_customization": _startup_evidence(
                snippet="A VetAI customiza modelos generativos com dados proprietarios."
            ),
        }
        gaps = (
            TechnicalGap(
                gap_type="model_serving",
                description="Needs lower latency inference and production model serving.",
                severity="low",
                confidence=0.92,
                evidences=(evidence_by_gap["model_serving"],),
            ),
            TechnicalGap(
                gap_type="data_acceleration",
                description="Needs GPU acceleration for dataframe and training data workflows.",
                severity="medium",
                confidence=0.72,
                evidences=(evidence_by_gap["data_acceleration"],),
            ),
            TechnicalGap(
                gap_type="computer_vision",
                description="Needs video analytics and sensor data processing for AI applications.",
                severity="high",
                confidence=0.88,
                evidences=(evidence_by_gap["computer_vision"],),
            ),
            TechnicalGap(
                gap_type="llm_customization",
                description="Needs customization and deployment of generative AI models.",
                severity="high",
                confidence=0.95,
                evidences=(evidence_by_gap["llm_customization"],),
            ),
        )
        corpus = load_nvidia_knowledge_corpus(_fixture_path())
        retrievals = tuple(
            retrieve_nvidia_knowledge_by_gap(
                corpus,
                run_id="run-issue-12",
                gap_type=gap.gap_type,
                description=gap.description,
                startup_signals=(gap.gap_type.replace("_", " "),),
                top_k=1,
            )
            for gap in gaps
        )

        recommendation_set = build_nvidia_recommendations(
            profile=_profile(evidence_by_gap["model_serving"]),
            evidence_groups=(),
            collection_quality=_collection_quality(),
            assessment=_assessment(*gaps),
            retrievals=retrievals,
        )

        self.assertEqual(recommendation_set.hypotheses, ())
        self.assertEqual(recommendation_set.blocked_recommendations, ())
        self.assertTrue(recommendation_set.quality.ready_for_briefing)
        self.assertEqual(
            tuple(recommendation.gap.gap_type for recommendation in recommendation_set.technical_recommendations),
            ("llm_customization", "computer_vision", "data_acceleration", "model_serving"),
        )
        self.assertEqual(
            {
                recommendation.gap.gap_type: recommendation.nvidia_citations[0].document_id
                for recommendation in recommendation_set.top_recommendations_by_gap
            },
            {
                "model_serving": "nvidia-nim-developers",
                "llm_customization": "nvidia-nemo-framework",
                "data_acceleration": "nvidia-cuda-x-data-science",
                "computer_vision": "nvidia-deepstream-sdk",
            },
        )
        self.assertTrue(
            all(recommendation.rank == 1 for recommendation in recommendation_set.top_recommendations_by_gap)
        )

    def test_supported_technical_recommendation_links_gap_evidence_and_official_citation(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        gap = TechnicalGap(
            gap_type="model_serving",
            description="Needs lower latency inference and production model serving.",
            severity="high",
            confidence=0.86,
            evidences=(startup_evidence,),
        )
        assessment = _assessment(gap)
        corpus = load_nvidia_knowledge_corpus(_fixture_path())
        retrieval = retrieve_nvidia_knowledge_by_gap(
            corpus,
            run_id="run-issue-7",
            gap_type=gap.gap_type,
            description=gap.description,
            startup_signals=("inference", "latency"),
            top_k=1,
        )

        recommendation_set = build_nvidia_recommendations(
            profile=_profile(startup_evidence),
            evidence_groups=(
                FieldEvidenceGroup(
                    field_name="ai_signals",
                    value="inferencia em producao",
                    evidences=(startup_evidence,),
                    has_conflict=False,
                    conflicting_values=(),
                ),
            ),
            collection_quality=_collection_quality(),
            assessment=assessment,
            retrievals=(retrieval,),
        )

        self.assertEqual(recommendation_set.schema_version, "nvidia_recommendation.v1")
        self.assertEqual(recommendation_set.run_id, "run-issue-7")
        self.assertEqual(recommendation_set.startup_identifier, "VetAI")
        self.assertEqual(recommendation_set.final_nvidia_opportunity_priority, "urgent")
        self.assertEqual(recommendation_set.next_action, "prepare_technical_outreach")
        self.assertTrue(recommendation_set.quality.ready_for_briefing)
        self.assertEqual(recommendation_set.hypotheses, ())
        self.assertEqual(recommendation_set.blocked_recommendations, ())

        recommendation = recommendation_set.technical_recommendations[0]
        self.assertEqual(recommendation.recommendation_type, "technical")
        self.assertEqual(recommendation.state, "supported")
        self.assertEqual(recommendation.rank, 1)
        self.assertEqual(recommendation.gap.gap_type, "model_serving")
        self.assertEqual(recommendation.nvidia_technology, "NVIDIA NIM for Developers")
        self.assertEqual(recommendation.complexity, "medium")
        self.assertEqual(recommendation.startup_evidences, (startup_evidence,))
        self.assertEqual(recommendation.nvidia_citations[0].document_id, "nvidia-nim-developers")
        self.assertEqual(recommendation.nvidia_citations[0].chunk_id, "nvidia-nim-developers:0")
        self.assertEqual(
            recommendation.selection_reasons,
            (
                "matched_gap_type:model_serving",
                "has_startup_gap_evidence",
                "has_official_nvidia_citation",
                "ranked_by_recommendation_score",
                "top_recommendation_for_gap",
            ),
        )
        self.assertEqual(recommendation_set.top_recommendations_by_gap, (recommendation,))

    def test_missing_nvidia_citation_creates_hypothesis_not_supported_recommendation(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        gap = TechnicalGap(
            gap_type="model_serving",
            description="Needs lower latency inference and production model serving.",
            severity="high",
            confidence=0.86,
            evidences=(startup_evidence,),
        )
        corpus = load_nvidia_knowledge_corpus(_fixture_path())
        retrieval = retrieve_nvidia_knowledge_by_gap(
            corpus,
            run_id="run-issue-7",
            gap_type="quantum_billing",
            description="Need tax invoicing workflow support.",
            startup_signals=("accounts payable",),
            top_k=1,
        )

        recommendation_set = build_nvidia_recommendations(
            profile=_profile(startup_evidence),
            evidence_groups=(),
            collection_quality=_collection_quality(),
            assessment=_assessment(gap),
            retrievals=(retrieval,),
        )

        self.assertEqual(recommendation_set.technical_recommendations, ())
        self.assertEqual(recommendation_set.top_recommendations_by_gap, ())
        self.assertEqual(recommendation_set.final_nvidia_opportunity_priority, "human_review")
        self.assertEqual(recommendation_set.next_action, "validate_nvidia_fit_with_human")
        self.assertFalse(recommendation_set.quality.ready_for_briefing)
        self.assertTrue(recommendation_set.quality.human_review_requested)
        self.assertEqual(
            recommendation_set.quality.reasons,
            ("recommendation_hypothesis_requires_human_review",),
        )

        hypothesis = recommendation_set.hypotheses[0]
        self.assertEqual(hypothesis.state, "hypothesis")
        self.assertEqual(hypothesis.recommendation_type, "technical")
        self.assertEqual(hypothesis.gap.gap_type, "model_serving")
        self.assertEqual(hypothesis.nvidia_technology, UNKNOWN)
        self.assertEqual(hypothesis.startup_evidences, (startup_evidence,))
        self.assertEqual(hypothesis.nvidia_citations, ())
        self.assertIn("missing_official_nvidia_citation", hypothesis.selection_reasons)

    def test_low_confidence_gap_stays_hypothesis_even_with_official_citation(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI talvez precise reduzir latencia de inferencia em producao."
        )
        gap = TechnicalGap(
            gap_type="model_serving",
            description="May need lower latency inference and production model serving.",
            severity="high",
            confidence=0.42,
            evidences=(startup_evidence,),
        )
        corpus = load_nvidia_knowledge_corpus(_fixture_path())
        retrieval = retrieve_nvidia_knowledge_by_gap(
            corpus,
            run_id="run-issue-12",
            gap_type=gap.gap_type,
            description=gap.description,
            startup_signals=("inference", "latency"),
            top_k=1,
        )

        recommendation_set = build_nvidia_recommendations(
            profile=_profile(startup_evidence),
            evidence_groups=(),
            collection_quality=_collection_quality(),
            assessment=_assessment(gap),
            retrievals=(retrieval,),
        )

        self.assertEqual(recommendation_set.technical_recommendations, ())
        self.assertEqual(recommendation_set.blocked_recommendations, ())
        self.assertEqual(recommendation_set.final_nvidia_opportunity_priority, "human_review")
        self.assertFalse(recommendation_set.quality.ready_for_briefing)

        hypothesis = recommendation_set.hypotheses[0]
        self.assertEqual(hypothesis.state, "hypothesis")
        self.assertEqual(hypothesis.gap.gap_type, "model_serving")
        self.assertEqual(hypothesis.nvidia_citations[0].document_id, "nvidia-nim-developers")
        self.assertIn("confidence is below", hypothesis.technical_rationale)
        self.assertNotIn("citation support is insufficient", hypothesis.technical_rationale)
        self.assertIn("low_gap_confidence", hypothesis.selection_reasons)

    def test_close_alternative_is_preserved_without_displacing_top_recommendation(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao."
        )
        gap = TechnicalGap(
            gap_type="model_serving",
            description="Needs lower latency inference and production model serving.",
            severity="high",
            confidence=0.9,
            evidences=(startup_evidence,),
        )
        retrieval = _retrieval_with_results(
            gap_type=gap.gap_type,
            query=gap.description,
            entries=(
                ("nvidia-nim-developers", "NVIDIA NIM for Developers", 0.91),
                ("nvidia-triton-inference", "NVIDIA Triton Inference Server", 0.87),
            ),
        )

        recommendation_set = build_nvidia_recommendations(
            profile=_profile(startup_evidence),
            evidence_groups=(),
            collection_quality=_collection_quality(),
            assessment=_assessment(gap),
            retrievals=(retrieval,),
        )

        recommendation = recommendation_set.technical_recommendations[0]
        self.assertEqual(recommendation.nvidia_citations[0].document_id, "nvidia-nim-developers")
        self.assertEqual(recommendation.rank, 1)
        self.assertEqual(recommendation_set.top_recommendations_by_gap, (recommendation,))

        alternative = recommendation_set.alternatives[0]
        self.assertEqual(alternative.nvidia_citations[0].document_id, "nvidia-triton-inference")
        self.assertEqual(alternative.gap.gap_type, "model_serving")
        self.assertEqual(alternative.rank, 2)
        self.assertIn("ranked_by_recommendation_score", alternative.selection_reasons)
        self.assertNotIn("highest_retrieval_score_for_gap", alternative.selection_reasons)
        self.assertIn("close_alternative_for_gap", alternative.selection_reasons)

    def test_uncovered_gap_type_becomes_hypothesis_even_with_official_citation(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI menciona avaliacao de voz com modelos de IA em pesquisa."
        )
        gap = TechnicalGap(
            gap_type="voice_ai",
            description="May need speech AI support for voice interactions.",
            severity="medium",
            confidence=0.82,
            evidences=(startup_evidence,),
        )
        retrieval = _retrieval_with_results(
            gap_type=gap.gap_type,
            query=gap.description,
            entries=(("nvidia-riva", "NVIDIA Riva", 0.93),),
        )

        recommendation_set = build_nvidia_recommendations(
            profile=_profile(startup_evidence),
            evidence_groups=(),
            collection_quality=_collection_quality(),
            assessment=_assessment(gap),
            retrievals=(retrieval,),
        )

        self.assertEqual(recommendation_set.technical_recommendations, ())
        self.assertEqual(recommendation_set.blocked_recommendations, ())
        hypothesis = recommendation_set.hypotheses[0]
        self.assertEqual(hypothesis.gap.gap_type, "voice_ai")
        self.assertEqual(hypothesis.nvidia_citations[0].document_id, "nvidia-riva")
        self.assertIn("not covered by deterministic recommendation rules", hypothesis.technical_rationale)
        self.assertNotIn("citation support is insufficient", hypothesis.technical_rationale)
        self.assertIn("gap_type_not_covered_by_recommendation_rules", hypothesis.selection_reasons)

    def test_unknown_gap_produces_no_recommendation_candidate(self) -> None:
        startup_evidence = _startup_evidence(snippet="A VetAI usa inteligencia artificial no produto.")
        gap = TechnicalGap(
            gap_type=UNKNOWN,
            description=UNKNOWN,
            severity=UNKNOWN,
            confidence=0.0,
            evidences=(startup_evidence,),
        )

        recommendation_set = build_nvidia_recommendations(
            profile=_profile(startup_evidence),
            evidence_groups=(),
            collection_quality=_collection_quality(),
            assessment=_assessment(gap),
            retrievals=(),
        )

        self.assertEqual(recommendation_set.technical_recommendations, ())
        self.assertEqual(recommendation_set.hypotheses, ())
        self.assertEqual(recommendation_set.blocked_recommendations, ())
        self.assertEqual(recommendation_set.final_nvidia_opportunity_priority, "low")
        self.assertEqual(recommendation_set.next_action, "deprioritize_for_now")
        self.assertEqual(recommendation_set.quality.reasons, ("no_recommendation_candidate",))

    def test_equal_retrieval_scores_use_stable_document_tie_breaker(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao."
        )
        gap = TechnicalGap(
            gap_type="model_serving",
            description="Needs lower latency inference and production model serving.",
            severity="high",
            confidence=0.9,
            evidences=(startup_evidence,),
        )
        retrieval = _retrieval_with_results(
            gap_type=gap.gap_type,
            query=gap.description,
            entries=(
                ("z-nvidia-serving", "Z NVIDIA Serving", 0.9),
                ("a-nvidia-serving", "A NVIDIA Serving", 0.9),
            ),
        )

        recommendation_set = build_nvidia_recommendations(
            profile=_profile(startup_evidence),
            evidence_groups=(),
            collection_quality=_collection_quality(),
            assessment=_assessment(gap),
            retrievals=(retrieval,),
        )

        self.assertEqual(
            recommendation_set.technical_recommendations[0].nvidia_citations[0].document_id,
            "a-nvidia-serving",
        )
        self.assertEqual(
            recommendation_set.alternatives[0].nvidia_citations[0].document_id,
            "z-nvidia-serving",
        )

    def test_missing_startup_gap_evidence_blocks_recommendation_even_with_nvidia_citation(self) -> None:
        profile_evidence = _startup_evidence(snippet="A VetAI usa inteligencia artificial no produto.")
        gap = TechnicalGap(
            gap_type="model_serving",
            description="Needs lower latency inference and production model serving.",
            severity="high",
            confidence=0.86,
            evidences=(),
        )
        corpus = load_nvidia_knowledge_corpus(_fixture_path())
        retrieval = retrieve_nvidia_knowledge_by_gap(
            corpus,
            run_id="run-issue-7",
            gap_type=gap.gap_type,
            description=gap.description,
            startup_signals=("inference", "latency"),
            top_k=1,
        )

        recommendation_set = build_nvidia_recommendations(
            profile=_profile(profile_evidence),
            evidence_groups=(),
            collection_quality=_collection_quality(),
            assessment=_assessment(gap),
            retrievals=(retrieval,),
        )

        self.assertEqual(recommendation_set.technical_recommendations, ())
        self.assertEqual(recommendation_set.hypotheses, ())
        self.assertEqual(recommendation_set.final_nvidia_opportunity_priority, "human_review")
        self.assertEqual(recommendation_set.next_action, "resolve_blocking_evidence")
        self.assertFalse(recommendation_set.quality.ready_for_briefing)
        self.assertEqual(
            recommendation_set.quality.reasons,
            ("blocked_recommendation_requires_human_review",),
        )

        blocked = recommendation_set.blocked_recommendations[0]
        self.assertEqual(blocked.state, "blocked")
        self.assertEqual(blocked.recommendation_type, "technical")
        self.assertEqual(blocked.gap.gap_type, "model_serving")
        self.assertEqual(blocked.startup_evidences, ())
        self.assertEqual(blocked.nvidia_citations[0].document_id, "nvidia-nim-developers")
        self.assertIn("missing_startup_gap_evidence", blocked.selection_reasons)


def _fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "nvidia_knowledge_official_fixture.json"


def _startup_evidence(*, snippet: str) -> FieldEvidence:
    return FieldEvidence(
        url="https://vetai.example/product",
        title="VetAI Product",
        snippet=snippet,
        collected_at="2026-06-23T00:00:00Z",
        source_type="official_site",
    )


def _assessment(*gaps: TechnicalGap) -> AINativeAssessment:
    evidences = tuple(evidence for gap in gaps for evidence in gap.evidences)
    return AINativeAssessment(
        schema_version="ai_native_assessment.v1",
        run_id="run-issue-12" if len(gaps) > 1 else "run-issue-7",
        company_name="VetAI",
        classification="ai_native",
        confidence=0.82,
        nvidia_opportunity_urgency="urgent",
        criteria_results=(),
        positive_signals=(),
        technical_gaps=gaps,
        wrapper_dependency_risks=(),
        insufficient_evidence_fields=(),
        evidences=evidences,
        diagnostic_quality=DiagnosticQuality(
            ready_for_recommendation=True,
            requires_human_review=False,
            reasons=("ready_for_recommendation",),
        ),
        ready_for_recommendation=True,
    )


def _collection_quality() -> CollectionQualitySummary:
    return CollectionQualitySummary(
        candidate_count=1,
        official_site_found_count=1,
        official_site_found_rate=1.0,
        minimum_profile_complete_count=1,
        minimum_profile_complete_rate=1.0,
        average_evidences_per_startup=4.0,
        unknown_fields=(),
        source_success_rates=(),
        ready_for_evaluation=True,
        readiness_reasons=("ready_for_ai_native_evaluation",),
    )


def _profile(evidence: FieldEvidence) -> StartupProfile:
    observed_company = ProfileField(
        value="VetAI",
        claim_source=ClaimSource.OBSERVED,
        evidences=(evidence,),
    )
    unknown = ProfileField(value=UNKNOWN, claim_source=ClaimSource.UNKNOWN, evidences=())
    return StartupProfile(
        schema_version="startup_profile.v1",
        company_name=observed_company,
        official_site=ProfileField(
            value="https://vetai.example",
            claim_source=ClaimSource.OBSERVED,
            evidences=(evidence,),
        ),
        company_summary=unknown,
        sector=unknown,
        product=unknown,
        customers=unknown,
        funding=unknown,
        founders=unknown,
        technologies_used=unknown,
        ai_signals=ProfileField(
            value="inferencia em producao",
            claim_source=ClaimSource.OBSERVED,
            evidences=(evidence,),
        ),
        location=unknown,
    )


def _retrieval_with_results(
    *,
    gap_type: str,
    query: str,
    entries: tuple[tuple[str, str, float], ...],
) -> NVIDIAKnowledgeRetrieval:
    documents: list[NVIDIAKnowledgeDocument] = []
    results: list[RetrievedNVIDIAKnowledge] = []
    for rank, (document_id, title, score) in enumerate(entries, start=1):
        document = NVIDIAKnowledgeDocument(
            schema_version="nvidia_knowledge.v1",
            corpus_version="official-nvidia-fixture.v1",
            document_id=document_id,
            title=title,
            source_url=f"https://developer.nvidia.com/{document_id}",
            source_type="official_nvidia_developer_page",
            ingested_at="2026-06-23T00:00:00Z",
        )
        chunk = NVIDIAKnowledgeChunk(
            schema_version="nvidia_knowledge.v1",
            corpus_version=document.corpus_version,
            chunk_id=f"{document_id}:0",
            document_id=document_id,
            chunk_index=0,
            topic=gap_type,
            text=f"{title} supports {gap_type.replace('_', ' ')} workloads.",
        )
        documents.append(document)
        results.append(
            RetrievedNVIDIAKnowledge(
                chunk=chunk,
                citation=nvidia_citation_from_chunk(document, chunk),
                score=score,
                retrieval_strategy="bm25_lexical",
                rationale="Fixture retrieval result.",
                rank=rank,
                bm25_score=score,
            )
        )
    return NVIDIAKnowledgeRetrieval(
        schema_version="nvidia_knowledge.v1",
        run_id="run-issue-12",
        corpus_version="official-nvidia-fixture.v1",
        query=query,
        results=tuple(results),
        documents=tuple(documents),
    )


if __name__ == "__main__":
    unittest.main()
