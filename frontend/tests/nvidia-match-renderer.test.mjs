import assert from "node:assert/strict";
import test from "node:test";

import { buildMockRunRecord } from "../src/mock-data.js";
import { createInitialState, renderApp } from "../src/renderer.js";

test("renders supported NVIDIA recommendation with citations, evidence refs, and metrics", () => {
  const recommendation = supportedRecommendation();
  const currentRun = runWithNvidiaPayload({
    nvidia_match: recommendationSet({
      technical_recommendations: [recommendation],
      top_recommendations_by_gap: [recommendation]
    }),
    downstream_quality_report: downstreamQualityReport()
  });

  const html = renderApp(createInitialState({ activeSection: "nvidia-match", currentRun }));

  assert.match(html, /Top recommendations per gap/);
  assert.match(html, /Top recommendation/);
  assert.match(html, /Supported recommendations/);
  assert.match(html, /NVIDIA NIM Microservices/);
  assert.match(html, /supported/);
  assert.match(html, /urgent/);
  assert.match(html, /medium/);
  assert.match(html, /prepare_technical_outreach/);
  assert.match(html, /Startup evidence refs: 1/);
  assert.match(html, /https:\/\/vetai.example\/product/);
  assert.match(html, /NVIDIA citation refs: 1/);
  assert.match(html, /Official NVIDIA citation/);
  assert.match(html, /nvidia-nim-developers:0/);
  assert.match(html, /Recall/);
  assert.match(html, /Precision/);
  assert.match(html, /F1/);
  assert.match(html, /Coverage/);
  assert.match(html, /100%/);
  assert.match(html, /Human review reason counts/);
  assert.match(html, /none/);
});

test("renders missing or non-official citation as hypothesis instead of supported fact", () => {
  const hypothesis = supportedRecommendation({
    state: "hypothesis",
    nvidia_technology: "Unknown NVIDIA fit",
    nvidia_citations: [nonOfficialCitation()],
    next_action: "validate_nvidia_fit_with_human",
    selection_reasons: ["matched_gap_type:model_serving", "missing_official_nvidia_citation"]
  });
  const currentRun = runWithNvidiaPayload(
    {
      nvidia_match: recommendationSet({
        final_nvidia_opportunity_priority: "human_review",
        next_action: "validate_nvidia_fit_with_human",
        technical_recommendations: [],
        top_recommendations_by_gap: [],
        hypotheses: [hypothesis],
        quality: recommendationQuality({
          ready_for_briefing: false,
          human_review_requested: true,
          metrics: recommendationMetrics({
            supported_recommendation_count: 0,
            hypothesis_recommendation_count: 1,
            recommendations_with_official_nvidia_citation_count: 0,
            human_review_reason_counts: [["missing_official_nvidia_citation", 1]]
          }),
          reasons: ["recommendation_hypothesis_requires_human_review", "missing_official_nvidia_citation"]
        })
      })
    },
    {
      workflow_outcome: "human_review_requested",
      next_action: "validate_nvidia_fit_with_human",
      human_review_reasons: ["missing_official_nvidia_citation"]
    }
  );

  const html = renderApp(createInitialState({ activeSection: "nvidia-match", currentRun }));

  assert.match(html, /Hypotheses/);
  assert.match(html, /hypothesis/);
  assert.match(html, /validate_nvidia_fit_with_human/);
  assert.match(html, /missing_official_nvidia_citation/);
  assert.match(html, /Non-official or insufficient NVIDIA citation/);
  assert.match(html, /treat as hypothesis until validated/);
  assert.match(html, /missing_official_nvidia_citation \(1\)/);
});

test("renders hybrid retrieval results with chunk, source, rank, and scores", () => {
  const currentRun = runWithNvidiaPayload({
    nvidia_match: recommendationSet(),
    retrievals: [hybridRetrieval()]
  });

  const html = renderApp(createInitialState({ activeSection: "nvidia-match", currentRun }));

  assert.match(html, /Retrieved NVIDIA Knowledge/);
  assert.match(html, /official-nvidia-fixture.v1/);
  assert.match(html, /hybrid_bm25_vector/);
  assert.match(html, /NVIDIA NIM Microservices/);
  assert.match(html, /nvidia-nim-developers:0/);
  assert.match(html, /https:\/\/developer.nvidia.com\/nim/);
  assert.match(html, /NIM provides optimized inference microservices/);
  assert.match(html, /rank/);
  assert.match(html, /BM25 score/);
  assert.match(html, /vector score/);
  assert.match(html, /hybrid score/);
  assert.match(html, /0.84/);
  assert.match(html, /0.71/);
  assert.match(html, /0.92/);
});

test("renders reranked Top K output without presenting rerank as a new fact", () => {
  const currentRun = runWithNvidiaPayload({
    nvidia_match: recommendationSet(),
    rerank_results: [rerankResult()]
  });

  const html = renderApp(createInitialState({ activeSection: "nvidia-match", currentRun }));

  assert.match(html, /Reranking/);
  assert.match(html, /supplied Top K/);
  assert.match(html, /do not create new facts/);
  assert.match(html, /reranked_only_supplied_top_k_candidates/);
  assert.match(html, /original rank/);
  assert.match(html, /original score/);
  assert.match(html, /rerank score/);
  assert.match(html, /Cross-encoder scored query and candidate chunk text/);
  assert.match(html, /0.77/);
  assert.match(html, /0.94/);
});

function runWithNvidiaPayload(finalPayloadOverrides, runOverrides = {}) {
  const base = buildMockRunRecord(
    {
      startup_url: "https://vetai.example/",
      startup_name: "VetAI"
    },
    {
      runId: "mock-run-nvidia-match",
      createdAt: "2026-06-30T15:30:00.000Z"
    }
  );
  const finalPayload = {
    ...base.final_payload,
    ...finalPayloadOverrides
  };
  return {
    ...base,
    ...runOverrides,
    next_action: runOverrides.next_action || finalPayload.next_action || base.next_action,
    human_review_reasons: runOverrides.human_review_reasons || finalPayload.human_review_reasons || base.human_review_reasons,
    final_payload: finalPayload
  };
}

function recommendationSet(overrides = {}) {
  return {
    schema_version: "nvidia_recommendation.v1",
    run_id: "mock-run-nvidia-match",
    startup_identifier: "VetAI",
    corpus_version: "official-nvidia-fixture.v1",
    technical_recommendations: [],
    program_recommendations: [],
    top_recommendations_by_gap: [],
    alternatives: [],
    hypotheses: [],
    blocked_recommendations: [],
    final_nvidia_opportunity_priority: "urgent",
    next_action: "prepare_technical_outreach",
    quality: recommendationQuality(),
    audit_reasons: ["supported_recommendation_ready"],
    ...overrides
  };
}

function supportedRecommendation(overrides = {}) {
  return {
    recommendation_id: "mock-run-nvidia-match:vetai:model_serving:nvidia-nim",
    recommendation_type: "technical",
    state: "supported",
    rank: 1,
    gap: {
      gap_type: "model_serving",
      description: "Needs lower latency production inference.",
      severity: "high",
      confidence: 0.86
    },
    nvidia_technology: "NVIDIA NIM Microservices",
    technical_rationale: "NVIDIA NIM Microservices is cited for the model_serving gap.",
    commercial_rationale: "Official NVIDIA fit is supported for an urgent model_serving gap.",
    complexity: "medium",
    nvidia_opportunity_priority: "urgent",
    next_action: "prepare_technical_outreach",
    startup_evidences: [startupEvidence()],
    nvidia_citations: [officialCitation()],
    selection_reasons: [
      "matched_gap_type:model_serving",
      "has_startup_gap_evidence",
      "has_official_nvidia_citation",
      "top_recommendation_for_gap"
    ],
    ...overrides
  };
}

function recommendationQuality(overrides = {}) {
  return {
    ready_for_briefing: true,
    human_review_requested: false,
    states: ["supported", "ready_for_briefing"],
    reasons: ["supported_recommendation_ready"],
    metrics: recommendationMetrics(),
    ...overrides
  };
}

function recommendationMetrics(overrides = {}) {
  return {
    supported_recommendation_count: 1,
    hypothesis_recommendation_count: 0,
    blocked_recommendation_count: 0,
    recommendations_with_official_nvidia_citation_count: 1,
    recommendations_with_startup_evidence_count: 1,
    gaps_without_recommendation: [],
    blocked_briefing_count: 0,
    human_review_reason_counts: [],
    corpus_expansion_targets: [],
    evidence_collection_targets: [],
    ...overrides
  };
}

function downstreamQualityReport() {
  return {
    schema_version: "downstream_metrics.v1",
    run_id: "mock-run-nvidia-match",
    startup_identifier: "VetAI",
    corpus_version: "official-nvidia-fixture.v1",
    retrieval_metrics: {
      retrieval_strategy: "hybrid_bm25_vector",
      recall: 1,
      precision: 1,
      f1: 1,
      coverage: 1,
      top_1_expected_count: 1
    },
    recommendation_metrics: {
      ...recommendationMetrics(),
      ready_for_briefing: true,
      human_review_requested: false,
      final_nvidia_opportunity_priority: "urgent",
      next_action: "prepare_technical_outreach"
    }
  };
}

function hybridRetrieval() {
  return {
    schema_version: "nvidia_knowledge.v1",
    run_id: "mock-run-nvidia-match",
    corpus_version: "official-nvidia-fixture.v1",
    query: "model_serving lower latency inference",
    results: [
      {
        chunk: {
          schema_version: "nvidia_knowledge_chunk.v1",
          corpus_version: "official-nvidia-fixture.v1",
          chunk_id: "nvidia-nim-developers:0",
          document_id: "nvidia-nim-developers",
          chunk_index: 0,
          topic: "model_serving",
          text: "NIM provides optimized inference microservices."
        },
        citation: officialCitation(),
        score: 0.86,
        retrieval_strategy: "hybrid_bm25_vector",
        rationale: "Hybrid score merged lexical and vector evidence.",
        rank: 1,
        bm25_score: 0.84,
        vector_score: 0.71,
        hybrid_score: 0.92
      }
    ],
    documents: []
  };
}

function rerankResult() {
  return {
    schema_version: "nvidia_rerank.v1",
    run_id: "mock-run-nvidia-match",
    corpus_version: "official-nvidia-fixture.v1",
    query: "model_serving lower latency inference",
    candidate_top_k: 2,
    ranking_strategy: "sentence_transformers_cross_encoder_score_desc",
    audit_reasons: ["reranked_only_supplied_top_k_candidates"],
    reranker_model_name: "cross-encoder/ms-marco-MiniLM-L-6-v2",
    reranker_model_version: "local",
    results: [
      {
        chunk: {
          chunk_id: "nvidia-nim-developers:0",
          document_id: "nvidia-nim-developers",
          chunk_index: 0
        },
        citation: officialCitation(),
        original_score: 0.77,
        original_bm25_score: 0.69,
        original_vector_score: 0.74,
        original_hybrid_score: 0.8,
        original_retrieval_rank: 2,
        original_retrieval_strategy: "hybrid_bm25_vector",
        original_rationale: "Baseline hybrid retrieval candidate.",
        rerank_score: 0.94,
        rerank_rank: 1,
        rerank_rationale: "Cross-encoder scored query and candidate chunk text."
      }
    ]
  };
}

function officialCitation() {
  return {
    schema_version: "nvidia_citation.v1",
    corpus_version: "official-nvidia-fixture.v1",
    document_id: "nvidia-nim-developers",
    document_title: "NVIDIA NIM Microservices",
    source_url: "https://developer.nvidia.com/nim",
    source_type: "official_nvidia_developer_page",
    ingested_at: "2026-06-30T00:00:00Z",
    chunk_id: "nvidia-nim-developers:0",
    excerpt: "NIM provides optimized inference microservices for production model serving.",
    chunk_index: 0
  };
}

function nonOfficialCitation() {
  return {
    ...officialCitation(),
    document_id: "third-party-nvidia-summary",
    document_title: "Third-party NVIDIA summary",
    source_url: "https://example.com/nvidia-summary",
    source_type: "third_party_blog",
    chunk_id: "third-party-nvidia-summary:0"
  };
}

function startupEvidence() {
  return {
    url: "https://vetai.example/product",
    title: "VetAI Product",
    snippet: "VetAI describes production inference latency needs for AI triage.",
    collected_at: "2026-06-30T00:00:00Z",
    source_type: "official_site"
  };
}
