import {
  RUN_RECORD_SCHEMA_VERSION,
  SMOKE_MATRIX_SCHEMA_VERSION,
  assertRunRecord,
  assertSmokeMatrix,
  validateRunRequest
} from "./api-contract.js";

/**
 * @typedef {import("./api-contract.js").FrontendApiClient} FrontendApiClient
 * @typedef {import("./api-contract.js").FrontendRunRequest} FrontendRunRequest
 */

/**
 * @param {{delayMs?: number, clock?: () => Date}=} options
 * @returns {FrontendApiClient}
 */
export function createMockFrontendApiClient(options = {}) {
  const delayMs = Number(options.delayMs || 0);
  const clock = options.clock || (() => new Date("2026-06-30T12:00:00.000Z"));
  /** @type {Map<string, import("./api-contract.js").FrontendRunRecord>} */
  const runs = new Map();
  let sequence = 1;

  return {
    async startRun(request) {
      validateRunRequest(request);
      await delay(delayMs);
      const record = buildMockRunRecord(request, {
        runId: `mock-run-${String(sequence).padStart(3, "0")}`,
        createdAt: clock().toISOString()
      });
      sequence += 1;
      runs.set(record.run_id, record);
      return record;
    },

    async getRun(runId) {
      await delay(delayMs);
      const record = runs.get(runId);
      if (!record) {
        throw new Error("run_not_found");
      }
      return record;
    },

    async getProductionSmokeMatrix(only = []) {
      await delay(delayMs);
      const matrix = buildMockSmokeMatrix(only);
      return assertSmokeMatrix(matrix);
    }
  };
}

/**
 * @param {FrontendRunRequest} request
 * @param {{runId: string, createdAt: string}} metadata
 */
export function buildMockRunRecord(request, metadata) {
  const startupIdentifier =
    textOrUnknown(request.startup_name) !== "unknown"
      ? textOrUnknown(request.startup_name)
      : request.startup_url
        ? hostname(request.startup_url)
        : "Brazilian AI startup search";
  const input = {
    startup_url: request.startup_url || null,
    query: request.query || null,
    startup_name: textOrUnknown(request.startup_name)
  };
  const finalPayload = {
    schema_version: "operational_entrypoint_result.v1",
    run_id: metadata.runId,
    created_at: metadata.createdAt,
    input,
    startup_identifier: startupIdentifier,
    workflow_outcome: "briefing_generated",
    next_action: "prepare_technical_outreach",
    briefing_reference: {
      briefing_type: "executive",
      artifact_kind: "briefing",
      startup_identifier: startupIdentifier
    },
    human_review_reasons: [],
    artifact_locations: {
      json_run_dir: `runs/${metadata.runId}`,
      processed_dir: `runs/${metadata.runId}/processed`
    },
    persistence_references: [],
    errors: [],
    options: {
      persistence_mode: request.persistence_mode || "json",
      retrieval_mode: request.retrieval_mode || "bm25",
      orchestration: request.orchestration || "local",
      render_js: Boolean(request.render_js),
      search_provider: Boolean(request.enable_search_provider),
      reranking: Boolean(request.enable_reranking),
      llm_narrative: Boolean(request.llm_narrative)
    },
    collection_quality: {
      schema_version: "collection_quality_summary.v1",
      readiness: "ready_for_ai_native_assessment",
      collected_pages: 2,
      unknown_field_rate: 0.17,
      conflict_count: 0
    },
    ai_native_assessment: {
      schema_version: "ai_native_assessment.v1",
      classification: "ai_native",
      opportunity_signal: "high",
      technical_gaps: [
        {
          gap_type: "model_serving",
          severity: "medium",
          rationale: "Public evidence suggests production inference and latency constraints."
        }
      ],
      wrapper_dependency_risks: [
        {
          risk_type: "external_api_only",
          severity: "low",
          rationale: "Mock evidence includes proprietary data and production inference signals."
        }
      ]
    },
    nvidia_match: {
      schema_version: "nvidia_recommendation.v1",
      priority: "high",
      supported_recommendations: [
        {
          recommendation_type: "technical",
          title: "Evaluate NVIDIA inference stack for model serving",
          citation_count: 2
        }
      ],
      blocked_recommendations: []
    }
  };
  return assertRunRecord({
    schema_version: RUN_RECORD_SCHEMA_VERSION,
    run_id: metadata.runId,
    status: "completed",
    workflow_outcome: "briefing_generated",
    created_at: metadata.createdAt,
    input,
    startup_identifier: startupIdentifier,
    next_action: "prepare_technical_outreach",
    briefing_reference: finalPayload.briefing_reference,
    human_review_reasons: [],
    artifact_references: {
      artifact_locations: finalPayload.artifact_locations,
      persistence_references: []
    },
    errors: [],
    options: finalPayload.options,
    final_payload: finalPayload
  });
}

/**
 * @param {string[]} only
 */
export function buildMockSmokeMatrix(only = []) {
  const selected = new Set(only.filter(Boolean));
  const steps = [
    step("playwright_collection", "Playwright real collection", "collection"),
    step("postgres_persistence", "Postgres persistence", "postgres"),
    step("pgvector_retrieval", "pgvector retrieval", "pgvector"),
    step("real_embeddings", "Real embedding model", "embedding"),
    step("hybrid_retrieval", "Hybrid BM25 plus pgvector retrieval", "retrieval"),
    step("reranking", "Real reranking", "reranking"),
    step("langgraph_checkpoint", "LangGraph Postgres checkpointing", "langgraph"),
    step("groq_litellm_narrative", "Groq/LiteLLM briefing narrative", "llm"),
    step("full_operational_smoke", "Full bounded operational smoke", "briefing_quality")
  ].filter((item) => !selected.size || selected.has(item.integration_id));
  return {
    schema_version: SMOKE_MATRIX_SCHEMA_VERSION,
    read_only: true,
    matrix: {
      schema_version: "production_smoke_matrix.v1",
      overall_status: "skipped",
      steps
    }
  };
}

function step(integrationId, title, bottleneck) {
  const envFlag = `NVIDIA_STARTUP_INTEL_RUN_${integrationId.toUpperCase()}_SMOKE`;
  return {
    integration_id: integrationId,
    title,
    status: "skipped",
    bottleneck,
    message: `set ${envFlag}=1 to enable`,
    command: "opt-in smoke command",
    prerequisites: [],
    required_env_vars: [],
    expected_artifacts: [],
    cleanup: [],
    payload: {}
  };
}

function textOrUnknown(value) {
  const text = String(value || "").trim();
  return text || "unknown";
}

function hostname(value) {
  try {
    return new URL(String(value)).hostname.replace(/^www\./, "");
  } catch {
    return String(value || "unknown");
  }
}

function delay(ms) {
  if (!ms) {
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}
