from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nvidia_startup_intel.ai_native_assessment import AINativeAssessment, DiagnosticQuality, TechnicalGap
from nvidia_startup_intel.collection_quality import CollectionQualitySummary
from nvidia_startup_intel.downstream_metrics import (
    RetrievalMetricExpectation,
    build_downstream_quality_report,
)
from nvidia_startup_intel.evidence import FieldEvidenceGroup
from nvidia_startup_intel.llm_adapters import LLMGenerationRequest, LLMGenerationResponse
from nvidia_startup_intel.nvidia_knowledge import NVIDIAKnowledgeRetrieval, load_nvidia_knowledge_corpus
from nvidia_startup_intel.persistence import JsonDownstreamArtifactStore, create_pipeline_run, load_json
from nvidia_startup_intel.search_params import UNKNOWN
from nvidia_startup_intel.sql_repository import sqlite_repository
from nvidia_startup_intel.startup_profile import ClaimSource, FieldEvidence, ProfileField, StartupProfile
from nvidia_startup_intel.workflow_graph import DownstreamWorkflowRuntime, build_local_downstream_workflow


class DownstreamPersistenceTests(unittest.TestCase):
    def test_workflow_persists_downstream_json_snapshots_for_reprocessing(self) -> None:
        with TemporaryDirectory() as base_dir:
            run = create_pipeline_run(base_dir, run_id="run-issue-11")
            startup_evidence = _startup_evidence(
                snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
            )
            workflow = build_local_downstream_workflow(
                DownstreamWorkflowRuntime(
                    corpus=load_nvidia_knowledge_corpus(_fixture_path()),
                    artifact_store=JsonDownstreamArtifactStore(run),
                )
            )

            state = workflow.invoke(
                {
                    "run_id": run.run_id,
                    "profile": _profile(startup_evidence),
                    "evidence_groups": (_evidence_group(startup_evidence),),
                    "collection_quality": _collection_quality(),
                    "assessment": _assessment(_model_serving_gap(startup_evidence), run_id=run.run_id),
                }
            )

            startup_dir = run.processed_dir / "downstream" / "VetAI"
            retrievals = load_json(startup_dir / "retrievals.json")
            recommendation_set = load_json(startup_dir / "recommendation_set.json")
            briefing = load_json(startup_dir / "briefing.json")

            self.assertEqual(state["errors"], ())
            self.assertEqual(retrievals["run_id"], "run-issue-11")
            self.assertEqual(retrievals["startup_identifier"], "VetAI")
            self.assertEqual(retrievals["corpus_version"], "official-nvidia-fixture.v1")
            self.assertEqual(retrievals["items"][0]["schema_version"], "nvidia_knowledge.v1")
            self.assertIn(
                "nvidia.com",
                retrievals["items"][0]["results"][0]["citation"]["source_url"],
            )
            self.assertEqual(recommendation_set["schema_version"], "nvidia_recommendation.v1")
            self.assertEqual(recommendation_set["startup_identifier"], "VetAI")
            self.assertEqual(recommendation_set["corpus_version"], "official-nvidia-fixture.v1")
            self.assertEqual(
                recommendation_set["technical_recommendations"][0]["nvidia_citations"][0]["chunk_id"],
                retrievals["items"][0]["results"][0]["citation"]["chunk_id"],
            )
            self.assertEqual(briefing["schema_version"], "executive_briefing.v1")
            self.assertEqual(briefing["run_id"], "run-issue-11")
            self.assertEqual(briefing["startup_identifier"], "VetAI")
            self.assertEqual(
                briefing["citation_references"][0]["chunk_id"],
                recommendation_set["technical_recommendations"][0]["nvidia_citations"][0]["chunk_id"],
            )
            self.assertFalse((run.processed_dir / "downstream_retrievals.json").exists())
            self.assertFalse((run.processed_dir / "downstream_recommendation_set.json").exists())
            self.assertFalse((run.processed_dir / "downstream_briefing.json").exists())

    def test_workflow_persists_groq_briefing_narrative_json_with_llm_metadata(self) -> None:
        with TemporaryDirectory() as base_dir:
            run = create_pipeline_run(base_dir, run_id="run-issue-62-json")
            startup_evidence = _startup_evidence(
                snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
            )
            workflow = build_local_downstream_workflow(
                DownstreamWorkflowRuntime(
                    corpus=load_nvidia_knowledge_corpus(_fixture_path()),
                    llm_client=GroqNarrativeLLM(),
                    artifact_store=JsonDownstreamArtifactStore(run),
                )
            )

            state = workflow.invoke(
                {
                    "run_id": run.run_id,
                    "user_query": "priorizar healthtech AI-native no Brasil",
                    "profile": _profile(startup_evidence),
                    "evidence_groups": (_evidence_group(startup_evidence),),
                    "collection_quality": _collection_quality(),
                    "assessment": _assessment(_model_serving_gap(startup_evidence), run_id=run.run_id),
                }
            )

            startup_dir = run.processed_dir / "downstream" / "VetAI"
            narrative = load_json(startup_dir / "briefing_narrative.json")
            serialized = str(narrative).lower()

            self.assertEqual(state["errors"], ())
            self.assertEqual(narrative["schema_version"], "briefing_narrative.v1")
            self.assertEqual(narrative["run_id"], "run-issue-62-json")
            self.assertEqual(narrative["startup_identifier"], "VetAI")
            self.assertEqual(narrative["source_briefing_schema_version"], "executive_briefing.v1")
            self.assertIn("NVIDIA NIM Microservices", narrative["technical_gap_narrative"])
            self.assertIn("prepare_technical_outreach", narrative["commercial_approach_narrative"])
            self.assertEqual(narrative["llm_request"]["metadata"]["run_id"], "run-issue-62-json")
            self.assertEqual(
                narrative["llm_request"]["metadata"]["source_briefing_schema_version"],
                "executive_briefing.v1",
            )
            self.assertEqual(narrative["llm_response"]["provider"], "litellm")
            self.assertEqual(narrative["llm_response"]["model"], "groq/llama-3.1-8b-instant")
            self.assertEqual(narrative["llm_response"]["metadata"]["adapter"], "litellm")
            self.assertEqual(
                narrative["llm_response"]["metadata"]["configured_api_key_env_var"],
                "GROQ_API_KEY",
            )
            self.assertNotIn("secret", serialized)

    def test_json_downstream_snapshots_are_namespaced_by_startup(self) -> None:
        with TemporaryDirectory() as base_dir:
            run = create_pipeline_run(base_dir, run_id="run-json-multi-startup")
            workflow = build_local_downstream_workflow(
                DownstreamWorkflowRuntime(
                    corpus=load_nvidia_knowledge_corpus(_fixture_path()),
                    artifact_store=JsonDownstreamArtifactStore(run),
                )
            )

            vetai_evidence = _startup_evidence(
                snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem.",
                company_name="VetAI",
            )
            medai_evidence = _startup_evidence(
                snippet="A MedAI precisa reduzir latencia de inferencia em producao para modelos de imagens medicas.",
                company_name="MedAI",
            )

            workflow.invoke(
                {
                    "run_id": run.run_id,
                    "profile": _profile(vetai_evidence, company_name="VetAI"),
                    "evidence_groups": (_evidence_group(vetai_evidence),),
                    "collection_quality": _collection_quality(),
                    "assessment": _assessment(
                        _model_serving_gap(vetai_evidence),
                        run_id=run.run_id,
                        company_name="VetAI",
                    ),
                }
            )
            workflow.invoke(
                {
                    "run_id": run.run_id,
                    "profile": _profile(medai_evidence, company_name="MedAI"),
                    "evidence_groups": (_evidence_group(medai_evidence),),
                    "collection_quality": _collection_quality(),
                    "assessment": _assessment(
                        _model_serving_gap(medai_evidence),
                        run_id=run.run_id,
                        company_name="MedAI",
                    ),
                }
            )

            vetai_recommendation_set = load_json(
                run.processed_dir / "downstream" / "VetAI" / "recommendation_set.json"
            )
            medai_recommendation_set = load_json(
                run.processed_dir / "downstream" / "MedAI" / "recommendation_set.json"
            )
            vetai_briefing = load_json(run.processed_dir / "downstream" / "VetAI" / "briefing.json")
            medai_briefing = load_json(run.processed_dir / "downstream" / "MedAI" / "briefing.json")

            self.assertEqual(vetai_recommendation_set["startup_identifier"], "VetAI")
            self.assertEqual(medai_recommendation_set["startup_identifier"], "MedAI")
            self.assertEqual(vetai_briefing["startup_identifier"], "VetAI")
            self.assertEqual(medai_briefing["startup_identifier"], "MedAI")
            self.assertNotEqual(
                vetai_recommendation_set["technical_recommendations"][0]["recommendation_id"],
                medai_recommendation_set["technical_recommendations"][0]["recommendation_id"],
            )

    def test_json_downstream_snapshots_include_metrics_when_supplied(self) -> None:
        with TemporaryDirectory() as base_dir:
            run = create_pipeline_run(base_dir, run_id="run-json-metrics")
            startup_evidence = _startup_evidence(
                snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
            )
            workflow = build_local_downstream_workflow(
                DownstreamWorkflowRuntime(corpus=load_nvidia_knowledge_corpus(_fixture_path()))
            )
            state = workflow.invoke(
                {
                    "run_id": run.run_id,
                    "profile": _profile(startup_evidence),
                    "evidence_groups": (_evidence_group(startup_evidence),),
                    "collection_quality": _collection_quality(),
                    "assessment": _assessment(_model_serving_gap(startup_evidence), run_id=run.run_id),
                }
            )
            metrics = build_downstream_quality_report(
                run_id=run.run_id,
                startup_identifier="VetAI",
                retrievals=state["retrievals"],
                retrieval_expectations=(
                    RetrievalMetricExpectation(
                        expectation_id="model-serving-nim",
                        target_type="technical_gap",
                        target="model_serving",
                        expected_chunk_ids=("nvidia-nim-developers:0",),
                    ),
                ),
                recommendation_set=state["recommendation_set"],
            )

            JsonDownstreamArtifactStore(run).save_downstream_state(
                {**state, "downstream_quality_report": metrics}
            )

            metrics_payload = load_json(run.processed_dir / "downstream" / "VetAI" / "metrics.json")
            self.assertEqual(metrics_payload["schema_version"], "downstream_metrics.v1")
            self.assertEqual(metrics_payload["run_id"], "run-json-metrics")
            self.assertEqual(metrics_payload["startup_identifier"], "VetAI")
            self.assertEqual(metrics_payload["retrieval_metrics"]["f1"], 1.0)

    def test_sql_repository_persists_downstream_payloads_by_run_and_startup(self) -> None:
        repository = sqlite_repository()
        run_id = repository.create_run(run_id="run-sql-downstream")
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        workflow = build_local_downstream_workflow(
            DownstreamWorkflowRuntime(
                corpus=load_nvidia_knowledge_corpus(_fixture_path()),
                artifact_store=repository,
            )
        )

        state = workflow.invoke(
            {
                "run_id": run_id,
                "profile": _profile(startup_evidence),
                "evidence_groups": (_evidence_group(startup_evidence),),
                "collection_quality": _collection_quality(),
                "assessment": _assessment(_model_serving_gap(startup_evidence), run_id=run_id),
            }
        )
        stored = repository.load_downstream_artifacts(run_id, startup_identifier="VetAI")

        self.assertEqual(state["errors"], ())
        self.assertEqual(repository.load_run(run_id).raw_discovery_results, ())
        self.assertEqual(stored.run_id, "run-sql-downstream")
        self.assertEqual(stored.startup_identifier, "VetAI")
        self.assertEqual(stored.retrievals[0]["schema_version"], "nvidia_knowledge.v1")
        self.assertEqual(stored.retrievals[0]["corpus_version"], "official-nvidia-fixture.v1")
        self.assertEqual(stored.recommendation_sets[0]["schema_version"], "nvidia_recommendation.v1")
        self.assertEqual(stored.recommendation_sets[0]["startup_identifier"], "VetAI")
        self.assertEqual(stored.briefings[0]["schema_version"], "executive_briefing.v1")
        self.assertEqual(stored.briefings[0]["startup_identifier"], "VetAI")
        self.assertEqual(
            stored.briefings[0]["citation_references"][0]["chunk_id"],
            stored.recommendation_sets[0]["technical_recommendations"][0]["nvidia_citations"][0]["chunk_id"],
        )

    def test_sql_repository_persists_human_review_narrative_with_llm_metadata(self) -> None:
        repository = sqlite_repository()
        run_id = repository.create_run(run_id="run-sql-human-review-narrative")
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        retrieval_without_citation = NVIDIAKnowledgeRetrieval(
            schema_version="nvidia_knowledge.v1",
            run_id=run_id,
            corpus_version="official-nvidia-fixture.v1",
            query="unrelated commercial billing workflow",
            results=(),
            documents=(),
        )
        workflow = build_local_downstream_workflow(
            DownstreamWorkflowRuntime(
                retrievals=(retrieval_without_citation,),
                llm_client=GroqNarrativeLLM(),
                artifact_store=repository,
            )
        )

        state = workflow.invoke(
            {
                "run_id": run_id,
                "user_query": "priorizar healthtech AI-native no Brasil",
                "profile": _profile(startup_evidence),
                "evidence_groups": (_evidence_group(startup_evidence),),
                "collection_quality": _collection_quality(),
                "assessment": _assessment(_model_serving_gap(startup_evidence), run_id=run_id),
            }
        )
        stored = repository.load_downstream_artifacts(run_id, startup_identifier="VetAI")
        briefings_by_schema = {briefing["schema_version"]: briefing for briefing in stored.briefings}
        narrative = briefings_by_schema["briefing_narrative.v1"]

        self.assertEqual(state["workflow_outcome"], "human_review_requested")
        self.assertEqual(len(stored.briefings), 2)
        self.assertIn("human_review_briefing.v1", briefings_by_schema)
        self.assertEqual(narrative["run_id"], run_id)
        self.assertEqual(narrative["startup_identifier"], "VetAI")
        self.assertEqual(narrative["source_briefing_schema_version"], "human_review_briefing.v1")
        self.assertEqual(narrative["llm_request"]["metadata"]["run_id"], run_id)
        self.assertEqual(
            narrative["llm_request"]["metadata"]["source_briefing_schema_version"],
            "human_review_briefing.v1",
        )
        self.assertEqual(narrative["llm_response"]["provider"], "litellm")
        self.assertEqual(narrative["llm_response"]["metadata"]["configured_api_key_env_var"], "GROQ_API_KEY")

    def test_sql_repository_reprocesses_briefing_without_repeating_scraping_or_retrieval(self) -> None:
        repository = sqlite_repository()
        run_id = repository.create_run(run_id="run-sql-reprocess")
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        workflow = build_local_downstream_workflow(
            DownstreamWorkflowRuntime(
                corpus=load_nvidia_knowledge_corpus(_fixture_path()),
                artifact_store=repository,
            )
        )
        state = workflow.invoke(
            {
                "run_id": run_id,
                "profile": _profile(startup_evidence),
                "evidence_groups": (_evidence_group(startup_evidence),),
                "collection_quality": _collection_quality(),
                "assessment": _assessment(_model_serving_gap(startup_evidence), run_id=run_id),
            }
        )
        stored_before = repository.load_downstream_artifacts(run_id, startup_identifier="VetAI")

        repository.save_downstream_state(
            {
                "run_id": run_id,
                "recommendation_set": state["recommendation_set"],
                "executive_briefing": state["executive_briefing"],
            }
        )
        stored_after = repository.load_downstream_artifacts(run_id, startup_identifier="VetAI")

        self.assertEqual(repository.load_run(run_id).collected_pages, ())
        self.assertEqual(stored_after.retrievals, stored_before.retrievals)
        self.assertEqual(len(stored_after.recommendation_sets), 1)
        self.assertEqual(len(stored_after.briefings), 1)

    def test_sql_repository_reprocessing_snapshot_requires_matching_corpus_version(self) -> None:
        repository = sqlite_repository()
        run_id = repository.create_run(run_id="run-sql-reprocess-match")
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        workflow = build_local_downstream_workflow(
            DownstreamWorkflowRuntime(
                corpus=load_nvidia_knowledge_corpus(_fixture_path()),
                artifact_store=repository,
            )
        )
        workflow.invoke(
            {
                "run_id": run_id,
                "profile": _profile(startup_evidence),
                "evidence_groups": (_evidence_group(startup_evidence),),
                "collection_quality": _collection_quality(),
                "assessment": _assessment(_model_serving_gap(startup_evidence), run_id=run_id),
            }
        )

        input_fingerprint = repository.build_operational_input_fingerprint(
            run_id,
            startup_identifier="VetAI",
        )
        matching = repository.load_downstream_artifacts_for_reprocessing(
            run_id,
            startup_identifier="VetAI",
            corpus_version="official-nvidia-fixture.v1",
            input_fingerprint=input_fingerprint,
        )
        stale = repository.load_downstream_artifacts_for_reprocessing(
            run_id,
            startup_identifier="VetAI",
            corpus_version="official-nvidia-fixture.v2",
            input_fingerprint=input_fingerprint,
        )
        changed_inputs = repository.load_downstream_artifacts_for_reprocessing(
            run_id,
            startup_identifier="VetAI",
            corpus_version="official-nvidia-fixture.v1",
            input_fingerprint="sha256:changed-inputs",
        )

        self.assertEqual(repository.load_run(run_id).collected_pages, ())
        self.assertEqual(matching.retrievals[0]["corpus_version"], "official-nvidia-fixture.v1")
        self.assertTrue(matching.retrievals[0]["created_at"])
        self.assertEqual(matching.recommendation_sets[0]["corpus_version"], "official-nvidia-fixture.v1")
        self.assertTrue(matching.recommendation_sets[0]["created_at"])
        self.assertEqual(matching.briefings[0]["schema_version"], "executive_briefing.v1")
        self.assertTrue(matching.briefings[0]["created_at"])
        self.assertEqual(stale.retrievals, ())
        self.assertEqual(stale.recommendation_sets, ())
        self.assertEqual(stale.briefings, ())
        self.assertEqual(stale.metrics, ())
        self.assertEqual(changed_inputs.retrievals, ())
        self.assertEqual(changed_inputs.recommendation_sets, ())
        self.assertEqual(changed_inputs.briefings, ())
        self.assertEqual(changed_inputs.metrics, ())

    def test_sql_repository_loads_complete_operational_run_with_downstream_metrics(self) -> None:
        repository = sqlite_repository()
        run_id = repository.create_run(run_id="run-sql-complete")
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        assessment = _assessment(_model_serving_gap(startup_evidence), run_id=run_id)
        repository.save_startup_profiles(run_id, (_profile(startup_evidence),))
        repository.save_field_evidences(run_id, {"VetAI": (_evidence_group(startup_evidence),)})
        repository.save_collection_quality(run_id, _collection_quality())
        repository.save_ai_native_assessments(run_id, {"VetAI": assessment})
        workflow = build_local_downstream_workflow(
            DownstreamWorkflowRuntime(
                corpus=load_nvidia_knowledge_corpus(_fixture_path()),
                artifact_store=repository,
            )
        )

        state = workflow.invoke(
            {
                "run_id": run_id,
                "profile": _profile(startup_evidence),
                "evidence_groups": (_evidence_group(startup_evidence),),
                "collection_quality": _collection_quality(),
                "assessment": assessment,
            }
        )
        metrics = build_downstream_quality_report(
            run_id=run_id,
            startup_identifier="VetAI",
            retrievals=state["retrievals"],
            retrieval_expectations=(
                RetrievalMetricExpectation(
                    expectation_id="model-serving-nim",
                    target_type="technical_gap",
                    target="model_serving",
                    expected_chunk_ids=("nvidia-nim-developers:0",),
                ),
            ),
            recommendation_set=state["recommendation_set"],
        )
        repository.save_downstream_quality_report(run_id, metrics)

        stored = repository.load_operational_run(run_id, startup_identifier="VetAI")

        self.assertEqual(stored.run_id, run_id)
        self.assertEqual(stored.startup_identifier, "VetAI")
        self.assertEqual(stored.upstream.startup_profiles[0]["schema_version"], "startup_profile.v1")
        self.assertEqual(stored.upstream.ai_native_assessments[0]["schema_version"], "ai_native_assessment.v1")
        self.assertEqual(stored.downstream.retrievals[0]["schema_version"], "nvidia_knowledge.v1")
        self.assertEqual(stored.downstream.recommendation_sets[0]["schema_version"], "nvidia_recommendation.v1")
        self.assertEqual(stored.downstream.briefings[0]["schema_version"], "executive_briefing.v1")
        self.assertEqual(stored.downstream.metrics[0]["schema_version"], "downstream_metrics.v1")
        self.assertEqual(stored.downstream.metrics[0]["startup_identifier"], "VetAI")
        self.assertEqual(stored.downstream.metrics[0]["retrieval_metrics"]["f1"], 1.0)


class GroqNarrativeLLM:
    def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        next_action = (
            "validate_nvidia_fit_with_human"
            if "validate_nvidia_fit_with_human" in request.user_prompt
            else "prepare_technical_outreach"
        )
        return LLMGenerationResponse(
            schema_version="llm_generation_response.v1",
            request_purpose=request.purpose,
            provider="litellm",
            model="groq/llama-3.1-8b-instant",
            model_version="2026-06-26",
            content=(
                "technical_gap_narrative: Recommend NVIDIA NIM Microservices for model_serving.\n"
                f"commercial_approach_narrative: next_action {next_action}."
            ),
            structured_output_schema=request.structured_output_schema,
            finish_reason="stop",
            usage={"total_tokens": 34},
            metadata={"adapter": "litellm", "configured_api_key_env_var": "GROQ_API_KEY"},
        )


def _fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "nvidia_knowledge_official_fixture.json"


def _startup_evidence(*, snippet: str, company_name: str = "VetAI") -> FieldEvidence:
    hostname = company_name.lower()
    return FieldEvidence(
        url=f"https://{hostname}.example/product",
        title=f"{company_name} Product",
        snippet=snippet,
        collected_at="2026-06-23T00:00:00Z",
        source_type="official_site",
    )


def _evidence_group(evidence: FieldEvidence) -> FieldEvidenceGroup:
    return FieldEvidenceGroup(
        field_name="ai_signals",
        value="inferencia em producao",
        evidences=(evidence,),
        has_conflict=False,
        conflicting_values=(),
    )


def _model_serving_gap(evidence: FieldEvidence) -> TechnicalGap:
    return TechnicalGap(
        gap_type="model_serving",
        description="Needs lower latency inference and production model serving.",
        severity="high",
        confidence=0.86,
        evidences=(evidence,),
    )


def _assessment(gap: TechnicalGap, *, run_id: str, company_name: str = "VetAI") -> AINativeAssessment:
    return AINativeAssessment(
        schema_version="ai_native_assessment.v1",
        run_id=run_id,
        company_name=company_name,
        classification="ai_native",
        confidence=0.82,
        nvidia_opportunity_urgency="urgent",
        criteria_results=(),
        positive_signals=(),
        technical_gaps=(gap,),
        wrapper_dependency_risks=(),
        insufficient_evidence_fields=(),
        evidences=gap.evidences,
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


def _profile(evidence: FieldEvidence, *, company_name: str = "VetAI") -> StartupProfile:
    unknown = ProfileField(value=UNKNOWN, claim_source=ClaimSource.UNKNOWN, evidences=())
    hostname = company_name.lower()
    return StartupProfile(
        schema_version="startup_profile.v1",
        company_name=ProfileField(value=company_name, claim_source=ClaimSource.OBSERVED, evidences=(evidence,)),
        official_site=ProfileField(
            value=f"https://{hostname}.example",
            claim_source=ClaimSource.OBSERVED,
            evidences=(evidence,),
        ),
        company_summary=ProfileField(
            value="AI-native veterinary triage platform.",
            claim_source=ClaimSource.OBSERVED,
            evidences=(evidence,),
        ),
        sector=ProfileField(value="healthtech", claim_source=ClaimSource.INFERRED, evidences=(evidence,)),
        product=ProfileField(value="AI triage product", claim_source=ClaimSource.OBSERVED, evidences=(evidence,)),
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


if __name__ == "__main__":
    unittest.main()
