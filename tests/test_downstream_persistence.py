from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nvidia_startup_intel.ai_native_assessment import AINativeAssessment, DiagnosticQuality, TechnicalGap
from nvidia_startup_intel.collection_quality import CollectionQualitySummary
from nvidia_startup_intel.evidence import FieldEvidenceGroup
from nvidia_startup_intel.nvidia_knowledge import load_nvidia_knowledge_corpus
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

            retrievals = load_json(run.processed_dir / "downstream_retrievals.json")
            recommendation_set = load_json(run.processed_dir / "downstream_recommendation_set.json")
            briefing = load_json(run.processed_dir / "downstream_briefing.json")

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


def _assessment(gap: TechnicalGap, *, run_id: str) -> AINativeAssessment:
    return AINativeAssessment(
        schema_version="ai_native_assessment.v1",
        run_id=run_id,
        company_name="VetAI",
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


def _profile(evidence: FieldEvidence) -> StartupProfile:
    unknown = ProfileField(value=UNKNOWN, claim_source=ClaimSource.UNKNOWN, evidences=())
    return StartupProfile(
        schema_version="startup_profile.v1",
        company_name=ProfileField(value="VetAI", claim_source=ClaimSource.OBSERVED, evidences=(evidence,)),
        official_site=ProfileField(
            value="https://vetai.example",
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
