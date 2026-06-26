from __future__ import annotations

from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

from nvidia_startup_intel.ai_native_assessment import AINativeAssessment, DiagnosticQuality, TechnicalGap
from nvidia_startup_intel.collection_quality import CollectionQualitySummary
from nvidia_startup_intel.evidence import FieldEvidenceGroup
from nvidia_startup_intel.nvidia_embeddings import DeterministicFakeEmbeddingClient, EmbeddingClient
from nvidia_startup_intel.nvidia_knowledge import (
    NVIDIAKnowledgeCorpus,
    NVIDIAKnowledgeRetrieval,
    RetrievedNVIDIAKnowledge,
    load_nvidia_knowledge_corpus,
    nvidia_citation_from_chunk,
    retrieve_nvidia_knowledge_by_gap,
)
from nvidia_startup_intel.search_params import UNKNOWN
from nvidia_startup_intel.startup_profile import ClaimSource, FieldEvidence, ProfileField, StartupProfile
from nvidia_startup_intel.workflow_graph import (
    DownstreamWorkflowRuntime,
    build_downstream_langgraph,
    build_local_downstream_workflow,
)


class DownstreamWorkflowTests(unittest.TestCase):
    def test_optional_langgraph_builder_matches_local_successful_downstream_path(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        profile = _profile(startup_evidence)
        runtime = DownstreamWorkflowRuntime(corpus=load_nvidia_knowledge_corpus(_fixture_path()))

        with fake_langgraph_modules():
            graph = build_downstream_langgraph(runtime)

        state = graph.invoke(
            {
                "run_id": "run-issue-47",
                "profile": profile,
                "evidence_groups": (),
                "collection_quality": _collection_quality(),
                "assessment": _assessment(_model_serving_gap(startup_evidence)),
            }
        )

        self.assertEqual(state["workflow_outcome"], "briefing_generated")
        self.assertEqual(state["next_action"], "prepare_technical_outreach")
        self.assertEqual(state["executive_briefing"].schema_version, "executive_briefing.v1")
        self.assertEqual(
            tuple(branch.branch_name for branch in state["branch_decisions"]),
            ("ready_for_recommendation", "ready_for_briefing", "briefing_generated"),
        )
        self.assertTrue(all(branch.audit_reason for branch in state["branch_decisions"]))

    def test_optional_langgraph_builder_routes_missing_citation_to_human_review(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        retrieval_without_citation = NVIDIAKnowledgeRetrieval(
            schema_version="nvidia_knowledge.v1",
            run_id="run-issue-47",
            corpus_version="official-nvidia-fixture.v1",
            query="unrelated commercial billing workflow",
            results=(),
            documents=(),
        )
        runtime = DownstreamWorkflowRuntime(retrievals=(retrieval_without_citation,))

        with fake_langgraph_modules():
            graph = build_downstream_langgraph(runtime)

        state = graph.invoke(
            {
                "run_id": "run-issue-47",
                "profile": _profile(startup_evidence),
                "evidence_groups": (),
                "collection_quality": _collection_quality(),
                "assessment": _assessment(_model_serving_gap(startup_evidence)),
            }
        )

        self.assertEqual(state["workflow_outcome"], "human_review_requested")
        self.assertEqual(state["next_action"], "validate_nvidia_fit_with_human")
        self.assertNotIn("executive_briefing", state)
        self.assertEqual(state["human_review_briefing"].schema_version, "human_review_briefing.v1")
        self.assertEqual(
            tuple(branch.branch_name for branch in state["branch_decisions"]),
            ("ready_for_recommendation", "human_review_requested"),
        )
        self.assertTrue(all(branch.audit_reason for branch in state["branch_decisions"]))

    def test_optional_langgraph_builder_exposes_needs_more_collection_branch(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        runtime = DownstreamWorkflowRuntime()

        with fake_langgraph_modules():
            graph = build_downstream_langgraph(runtime)

        state = graph.invoke(
            {
                "run_id": "run-issue-47",
                "profile": _profile(startup_evidence),
                "evidence_groups": (),
                "collection_quality": _low_collection_quality(),
                "assessment": _assessment(_model_serving_gap(startup_evidence)),
            }
        )

        self.assertEqual(state["workflow_outcome"], "needs_more_collection_or_human_review")
        self.assertEqual(state["next_action"], "resolve_blocking_evidence")
        self.assertEqual(state["retrievals"], ())
        self.assertEqual(state["errors"], ())
        self.assertEqual(state["human_review_briefing"].schema_version, "human_review_briefing.v1")
        self.assertEqual(state["branch_decisions"][0].branch_name, "needs_more_collection_or_human_review")
        self.assertIn("insufficient_public_evidence", state["branch_decisions"][0].audit_reason)
        self.assertTrue(all(branch.audit_reason for branch in state["branch_decisions"]))

    def test_downstream_langgraph_builder_reports_missing_optional_dependency(self) -> None:
        with patch.dict(sys.modules, {"langgraph.graph": None}):
            with self.assertRaisesRegex(RuntimeError, "Install langgraph"):
                build_downstream_langgraph(DownstreamWorkflowRuntime())

    def test_injected_retriever_adapter_keeps_framework_objects_out_of_workflow_state(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        profile = _profile(startup_evidence)
        gap = _model_serving_gap(startup_evidence)
        retrieval = retrieve_nvidia_knowledge_by_gap(
            load_nvidia_knowledge_corpus(_fixture_path()),
            run_id="run-issue-10",
            gap_type=gap.gap_type,
            description=gap.description,
            startup_signals=("inferencia em producao",),
            top_k=1,
        )
        retriever = FakeFrameworkRetriever(retrieval)
        workflow = build_local_downstream_workflow(DownstreamWorkflowRuntime(knowledge_retriever=retriever))

        state = workflow.invoke(
            {
                "run_id": "run-issue-10",
                "profile": profile,
                "evidence_groups": (),
                "collection_quality": _collection_quality(),
                "assessment": _assessment(gap),
            }
        )

        self.assertEqual(state["workflow_outcome"], "briefing_generated")
        self.assertEqual(state["retrievals"], (retrieval,))
        self.assertEqual(state["recommendation_set"].schema_version, "nvidia_recommendation.v1")
        self.assertEqual(state["executive_briefing"].schema_version, "executive_briefing.v1")
        self.assertEqual(
            retriever.requests,
            (("run-issue-10", "model_serving", "Needs lower latency inference and production model serving.", 1),),
        )
        self.assertNotIn("raw_framework_node", state)
        self.assertFalse(hasattr(state["retrievals"][0].results[0], "raw_framework_node"))

    def test_supported_gap_generates_executive_briefing_without_langgraph(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        profile = _profile(startup_evidence)
        evidence_groups = (
            FieldEvidenceGroup(
                field_name="ai_signals",
                value="inferencia em producao",
                evidences=(startup_evidence,),
                has_conflict=False,
                conflicting_values=(),
            ),
        )
        gap = _model_serving_gap(startup_evidence)
        assessment = _assessment(gap)
        runtime = DownstreamWorkflowRuntime(corpus=load_nvidia_knowledge_corpus(_fixture_path()))
        workflow = build_local_downstream_workflow(runtime)

        state = workflow.invoke(
            {
                "run_id": "run-issue-10",
                "profile": profile,
                "evidence_groups": evidence_groups,
                "collection_quality": _collection_quality(),
                "assessment": assessment,
            }
        )

        self.assertEqual(state["workflow_outcome"], "briefing_generated")
        self.assertEqual(state["next_action"], "prepare_technical_outreach")
        self.assertEqual(state["errors"], ())
        self.assertEqual(state["retrievals"][0].schema_version, "nvidia_knowledge.v1")
        self.assertEqual(state["recommendation_set"].schema_version, "nvidia_recommendation.v1")
        self.assertEqual(state["executive_briefing"].schema_version, "executive_briefing.v1")
        self.assertEqual(state["executive_briefing"].status, "ready_for_use")
        self.assertEqual(state["executive_briefing"].next_action, "prepare_technical_outreach")
        self.assertNotIn("human_review_briefing", state)

        branches = state["branch_decisions"]
        self.assertEqual(
            tuple(branch.branch_name for branch in branches),
            ("ready_for_recommendation", "ready_for_briefing", "briefing_generated"),
        )
        self.assertTrue(all(branch.audit_reason for branch in branches))

    def test_downstream_retrieval_uses_hybrid_pgvector_path_by_default_when_available(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        corpus = load_nvidia_knowledge_corpus(_fixture_path())
        vector_store = FakePgvectorStore(corpus, chunk_ids=("nvidia-api-catalog:0",))
        runtime = DownstreamWorkflowRuntime(
            corpus=corpus,
            embedding_client=DeterministicFakeEmbeddingClient(dimension=6),
            vector_store=vector_store,
            retrieval_top_k=2,
            lexical_top_k=1,
            vector_top_k=1,
        )
        workflow = build_local_downstream_workflow(runtime)

        state = workflow.invoke(
            {
                "run_id": "run-issue-59",
                "profile": _profile(startup_evidence),
                "evidence_groups": (),
                "collection_quality": _collection_quality(),
                "assessment": _assessment(_model_serving_gap(startup_evidence)),
            }
        )

        self.assertEqual(state["workflow_outcome"], "briefing_generated")
        self.assertEqual(vector_store.requests, (("run-issue-59", "official-nvidia-fixture.v1", "model_serving", 1),))

        retrieval = state["retrievals"][0]
        self.assertEqual(retrieval.results[0].retrieval_strategy, "hybrid_bm25_vector")
        self.assertEqual(retrieval.results[0].ranking_strategy, "reciprocal_rank_fusion")
        self.assertTrue(any(result.bm25_score > 0.0 for result in retrieval.results))
        self.assertTrue(any(result.vector_score > 0.0 for result in retrieval.results))
        self.assertTrue(all(result.hybrid_score == result.score for result in retrieval.results))
        self.assertEqual(retrieval.results[0].index_parameters["storage"], "postgres_pgvector")
        self.assertEqual(retrieval.results[0].index_parameters["lexical_top_k"], 1)
        self.assertEqual(retrieval.results[0].index_parameters["vector_top_k"], 1)
        self.assertEqual(retrieval.results[0].index_parameters["top_k"], 2)

    def test_missing_citation_fixture_requests_human_review(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        profile = _profile(startup_evidence)
        assessment = _assessment(_model_serving_gap(startup_evidence))
        retrieval_without_citation = NVIDIAKnowledgeRetrieval(
            schema_version="nvidia_knowledge.v1",
            run_id="run-issue-10",
            corpus_version="official-nvidia-fixture.v1",
            query="unrelated commercial billing workflow",
            results=(),
            documents=(),
        )
        workflow = build_local_downstream_workflow(
            DownstreamWorkflowRuntime(retrievals=(retrieval_without_citation,))
        )

        state = workflow.invoke(
            {
                "run_id": "run-issue-10",
                "profile": profile,
                "evidence_groups": (),
                "collection_quality": _collection_quality(),
                "assessment": assessment,
            }
        )

        self.assertEqual(state["workflow_outcome"], "human_review_requested")
        self.assertEqual(state["next_action"], "validate_nvidia_fit_with_human")
        self.assertNotIn("executive_briefing", state)
        self.assertEqual(state["human_review_briefing"].schema_version, "human_review_briefing.v1")
        self.assertEqual(
            state["human_review_briefing"].hypothesis_recommendations,
            state["recommendation_set"].hypotheses,
        )
        self.assertIn(
            "recommendation_hypothesis_requires_human_review",
            state["human_review_briefing"].review_reasons,
        )
        self.assertEqual(
            tuple(branch.branch_name for branch in state["branch_decisions"]),
            ("ready_for_recommendation", "human_review_requested"),
        )

    def test_missing_retrieval_input_preserves_upstream_evidence(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        profile = _profile(startup_evidence)
        assessment = _assessment(_model_serving_gap(startup_evidence))
        workflow = build_local_downstream_workflow(DownstreamWorkflowRuntime())

        state = workflow.invoke(
            {
                "run_id": "run-issue-10",
                "profile": profile,
                "evidence_groups": (),
                "collection_quality": _collection_quality(),
                "assessment": assessment,
            }
        )

        self.assertEqual(state["workflow_outcome"], "human_review_requested")
        self.assertEqual(state["next_action"], "validate_nvidia_fit_with_human")
        self.assertEqual(state["profile"], profile)
        self.assertEqual(state["assessment"].evidences, (startup_evidence,))
        self.assertEqual(state["human_review_briefing"].main_evidence, (startup_evidence,))

        error = state["errors"][0]
        self.assertEqual(error.step, "retrieve_nvidia_knowledge")
        self.assertEqual(error.error_type, "missing_nvidia_knowledge_input")
        self.assertTrue(error.audit_reason)
        self.assertIn(
            "human_review_requested",
            tuple(branch.branch_name for branch in state["branch_decisions"]),
        )

    def test_low_collection_quality_exposes_needs_more_collection_branch(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        profile = _profile(startup_evidence)
        workflow = build_local_downstream_workflow(DownstreamWorkflowRuntime())

        state = workflow.invoke(
            {
                "run_id": "run-issue-10",
                "profile": profile,
                "evidence_groups": (),
                "collection_quality": _low_collection_quality(),
                "assessment": _assessment(_model_serving_gap(startup_evidence)),
            }
        )

        self.assertEqual(state["workflow_outcome"], "needs_more_collection_or_human_review")
        self.assertEqual(state["next_action"], "resolve_blocking_evidence")
        self.assertEqual(state["retrievals"], ())
        self.assertEqual(state["errors"], ())
        self.assertEqual(state["human_review_briefing"].status, "ready_for_human_review")
        needs_more_branch = state["branch_decisions"][0]
        self.assertEqual(needs_more_branch.branch_name, "needs_more_collection_or_human_review")
        self.assertIn("insufficient_public_evidence", needs_more_branch.audit_reason)
        self.assertTrue(all(branch.audit_reason for branch in state["branch_decisions"]))

    def test_storage_error_is_structured_without_discarding_generated_briefing(self) -> None:
        startup_evidence = _startup_evidence(
            snippet="A VetAI precisa reduzir latencia de inferencia em producao para modelos de triagem."
        )
        profile = _profile(startup_evidence)
        workflow = build_local_downstream_workflow(
            DownstreamWorkflowRuntime(
                corpus=load_nvidia_knowledge_corpus(_fixture_path()),
                artifact_store=FailingArtifactStore(),
            )
        )

        state = workflow.invoke(
            {
                "run_id": "run-issue-10",
                "profile": profile,
                "evidence_groups": (),
                "collection_quality": _collection_quality(),
                "assessment": _assessment(_model_serving_gap(startup_evidence)),
            }
        )

        self.assertEqual(state["workflow_outcome"], "briefing_generated")
        self.assertEqual(state["next_action"], "prepare_technical_outreach")
        self.assertEqual(state["executive_briefing"].schema_version, "executive_briefing.v1")
        self.assertEqual(state["profile"], profile)
        error = state["errors"][0]
        self.assertEqual(error.step, "persist_downstream_artifacts")
        self.assertEqual(error.error_type, "RuntimeError")
        self.assertEqual(error.audit_reason, "storage_failed_structured_error")


class FailingArtifactStore:
    def save_downstream_state(self, state: dict[str, object]) -> None:
        raise RuntimeError("fixture storage failure")


class FakeFrameworkRetriever:
    def __init__(self, retrieval: NVIDIAKnowledgeRetrieval) -> None:
        self.retrieval = retrieval
        self.raw_framework_node = object()
        self.requests: tuple[tuple[str, str, str, int], ...] = ()

    def retrieve_for_gap(
        self,
        *,
        run_id: str,
        gap: TechnicalGap,
        startup_signals: tuple[str, ...],
        top_k: int,
    ) -> NVIDIAKnowledgeRetrieval:
        self.requests = (*self.requests, (run_id, gap.gap_type, gap.description, top_k))
        return self.retrieval


class FakePgvectorStore:
    def __init__(self, corpus: NVIDIAKnowledgeCorpus, *, chunk_ids: tuple[str, ...]) -> None:
        self.corpus = corpus
        self.chunk_ids = chunk_ids
        self.requests: tuple[tuple[str, str, str, int], ...] = ()

    def retrieve_by_vector(
        self,
        embedding_client: EmbeddingClient,
        *,
        run_id: str,
        corpus_version: str,
        gap_type: str = "",
        opportunity_type: str = "",
        description: str = "",
        startup_signals: tuple[str, ...] = (),
        query_terms: tuple[str, ...] = (),
        normalized_query: str = "",
        top_k: int = 3,
        min_vector_score: float = 0.0,
    ) -> NVIDIAKnowledgeRetrieval:
        self.requests = (*self.requests, (run_id, corpus_version, gap_type, top_k))
        chunks_by_id = {chunk.chunk_id: chunk for chunk in self.corpus.chunks}
        documents_by_id = {document.document_id: document for document in self.corpus.documents}
        result_documents = {}
        results = []
        for rank, chunk_id in enumerate(self.chunk_ids[:top_k], start=1):
            chunk = chunks_by_id[chunk_id]
            document = documents_by_id[chunk.document_id]
            vector_score = round(0.93 - rank / 100, 6)
            result_documents[document.document_id] = document
            results.append(
                RetrievedNVIDIAKnowledge(
                    chunk=chunk,
                    citation=nvidia_citation_from_chunk(document, chunk),
                    score=vector_score,
                    retrieval_strategy="vector_semantic",
                    rationale="Fixture pgvector nearest-neighbor result.",
                    rank=rank,
                    vector_score=vector_score,
                    embedding_metadata={
                        "schema_version": embedding_client.metadata.schema_version,
                        "corpus_version": corpus_version,
                        "embedding_provider": embedding_client.metadata.embedding_provider,
                        "embedding_model": embedding_client.metadata.embedding_model,
                        "embedding_version": embedding_client.metadata.embedding_version,
                        "dimension": embedding_client.metadata.dimension,
                        "expected_language_behavior": embedding_client.metadata.expected_language_behavior,
                    },
                    index_parameters={
                        "distance_metric": "cosine",
                        "index_type": "exact_pgvector_sql",
                        "storage": "postgres_pgvector",
                        "approximate_index": "none",
                    },
                    ranking_strategy="cosine_similarity_desc",
                    tie_breakers=("document_id", "chunk_index", "chunk_id"),
                )
            )
        return NVIDIAKnowledgeRetrieval(
            schema_version="nvidia_knowledge.v1",
            run_id=run_id,
            corpus_version=corpus_version,
            query=" ".join(
                (
                    gap_type.replace("_", " "),
                    opportunity_type.replace("_", " "),
                    description,
                    *startup_signals,
                    *query_terms,
                    normalized_query,
                )
            ).strip(),
            results=tuple(results),
            documents=tuple(result_documents.values()),
        )


class FakeCompiledStateGraph:
    def __init__(self, graph: "FakeStateGraph") -> None:
        self.graph = graph

    def invoke(self, state: dict[str, object]) -> dict[str, object]:
        current = dict(state)
        node_name = self.graph.entry_point
        while node_name != self.graph.end_marker:
            current = self.graph.nodes[node_name](current)
            if node_name in self.graph.conditional_edges:
                route_function, branch_targets = self.graph.conditional_edges[node_name]
                branch_name = route_function(current)
                node_name = branch_targets[branch_name]
            else:
                node_name = self.graph.edges[node_name]
        return current


class FakeStateGraph:
    def __init__(self, state_type: object) -> None:
        self.state_type = state_type
        self.end_marker = "__end__"
        self.nodes: dict[str, object] = {}
        self.edges: dict[str, str] = {}
        self.conditional_edges: dict[str, tuple[object, dict[str, str]]] = {}
        self.entry_point = ""

    def add_node(self, name: str, node: object) -> None:
        self.nodes[name] = node

    def set_entry_point(self, name: str) -> None:
        self.entry_point = name

    def add_edge(self, source: str, target: str) -> None:
        self.edges[source] = target

    def add_conditional_edges(
        self,
        source: str,
        route_function: object,
        branch_targets: dict[str, str],
    ) -> None:
        self.conditional_edges[source] = (route_function, branch_targets)

    def compile(self) -> FakeCompiledStateGraph:
        return FakeCompiledStateGraph(self)


def fake_langgraph_modules() -> object:
    langgraph_module = ModuleType("langgraph")
    graph_module = ModuleType("langgraph.graph")
    graph_module.END = "__end__"
    graph_module.StateGraph = FakeStateGraph
    langgraph_module.graph = graph_module
    return patch.dict(sys.modules, {"langgraph": langgraph_module, "langgraph.graph": graph_module})


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


def _model_serving_gap(evidence: FieldEvidence) -> TechnicalGap:
    return TechnicalGap(
        gap_type="model_serving",
        description="Needs lower latency inference and production model serving.",
        severity="high",
        confidence=0.86,
        evidences=(evidence,),
    )


def _assessment(gap: TechnicalGap) -> AINativeAssessment:
    return AINativeAssessment(
        schema_version="ai_native_assessment.v1",
        run_id="run-issue-10",
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


def _low_collection_quality() -> CollectionQualitySummary:
    return CollectionQualitySummary(
        candidate_count=1,
        official_site_found_count=0,
        official_site_found_rate=0.0,
        minimum_profile_complete_count=0,
        minimum_profile_complete_rate=0.0,
        average_evidences_per_startup=1.0,
        unknown_fields=(("technologies_used", 1),),
        source_success_rates=(),
        ready_for_evaluation=False,
        readiness_reasons=("insufficient_public_evidence",),
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
