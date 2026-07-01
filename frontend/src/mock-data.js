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
  seedRouteRuns(runs, clock);

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
  const branchDecisions = [
    {
      branch_name: "ready_for_recommendation",
      next_action: "retrieve_nvidia_knowledge",
      audit_reason: "collection_quality_ready"
    },
    {
      branch_name: "ready_for_briefing",
      next_action: "generate_executive_briefing",
      audit_reason: "supported_recommendation_has_official_citation"
    },
    {
      branch_name: "briefing_generated",
      next_action: "prepare_technical_outreach",
      audit_reason: "executive_briefing_ready_for_use"
    }
  ];
  const persistenceReferences = [
    {
      artifact_kind: "briefing",
      startup_identifier: startupIdentifier,
      storage: "json",
      reference: `runs/${metadata.runId}/processed/downstream/${safePathSegment(startupIdentifier)}/briefing.json`
    }
  ];
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
    branch_decisions: branchDecisions,
    artifact_locations: {
      json_run_dir: `runs/${metadata.runId}`,
      processed_dir: `runs/${metadata.runId}/processed`
    },
    persistence_references: persistenceReferences,
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
    branch_decisions: branchDecisions,
    artifact_references: {
      artifact_locations: finalPayload.artifact_locations,
      persistence_references: persistenceReferences
    },
    errors: [],
    options: finalPayload.options,
    final_payload: finalPayload
  });
}

export function buildMockHumanReviewRunRecord(metadata = {}) {
  const record = buildMockRunRecord(
    {
      startup_url: "https://review-startup.ai/",
      startup_name: "Review Startup"
    },
    {
      runId: metadata.runId || "mock-human-review-run",
      createdAt: metadata.createdAt || "2026-06-30T12:15:00.000Z"
    }
  );
  const branchDecisions = [
    {
      branch_name: "ready_for_recommendation",
      next_action: "retrieve_nvidia_knowledge",
      audit_reason: "collection_quality_ready"
    },
    {
      branch_name: "human_review_requested",
      next_action: "generate_human_review_briefing",
      audit_reason: "recommendation_hypothesis_requires_human_review"
    }
  ];
  const humanReviewReasons = ["recommendation_hypothesis_requires_human_review"];
  const briefingReference = {
    briefing_type: "human_review",
    artifact_kind: "briefing",
    startup_identifier: "Review Startup"
  };
  const finalPayload = {
    ...record.final_payload,
    workflow_outcome: "human_review_requested",
    next_action: "validate_nvidia_fit_with_human",
    briefing_reference: briefingReference,
    human_review_reasons: humanReviewReasons,
    branch_decisions: branchDecisions,
    nvidia_match: {
      ...record.final_payload.nvidia_match,
      priority: "human_review",
      supported_recommendations: [],
      blocked_recommendations: [
        {
          recommendation_type: "technical",
          title: "Validate NVIDIA fit with human review",
          rationale: "The recommendation is a hypothesis because official citation support is incomplete."
        }
      ]
    }
  };
  return assertRunRecord({
    ...record,
    workflow_outcome: "human_review_requested",
    next_action: "validate_nvidia_fit_with_human",
    briefing_reference: briefingReference,
    human_review_reasons: humanReviewReasons,
    branch_decisions: branchDecisions,
    final_payload: finalPayload
  });
}

export function buildMockFailedRunRecord(metadata = {}) {
  const runId = metadata.runId || "mock-failed-run";
  const createdAt = metadata.createdAt || "2026-06-30T12:30:00.000Z";
  const error = {
    step: "execute_search",
    error_type: "TimeoutError",
    message: "search provider timeout",
    audit_reason: "search_adapter_failed_structured_error"
  };
  const finalPayload = {
    schema_version: "operational_entrypoint_result.v1",
    run_id: runId,
    created_at: createdAt,
    input: {
      startup_url: null,
      query: "Brazilian AI-native startups",
      startup_name: "unknown"
    },
    startup_identifier: "unknown",
    workflow_outcome: "failed_with_auditable_error",
    next_action: "review_workflow_errors",
    briefing_reference: null,
    human_review_reasons: ["search_adapter_failed_structured_error"],
    branch_decisions: [
      {
        branch_name: "failed_with_auditable_error",
        next_action: "review_workflow_errors",
        audit_reason: "search_adapter_failed_structured_error"
      }
    ],
    artifact_locations: {},
    persistence_references: [],
    errors: [error],
    options: {
      persistence_mode: "json",
      retrieval_mode: "bm25",
      orchestration: "local",
      render_js: false,
      search_provider: true,
      reranking: false,
      llm_narrative: false
    }
  };
  return assertRunRecord({
    schema_version: RUN_RECORD_SCHEMA_VERSION,
    run_id: runId,
    status: "failed",
    workflow_outcome: "failed_with_auditable_error",
    created_at: createdAt,
    input: finalPayload.input,
    startup_identifier: "unknown",
    next_action: "review_workflow_errors",
    briefing_reference: null,
    human_review_reasons: finalPayload.human_review_reasons,
    branch_decisions: finalPayload.branch_decisions,
    artifact_references: {
      artifact_locations: {},
      persistence_references: []
    },
    errors: [error],
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

function seedRouteRuns(runs, clock) {
  const completed = buildMockRunRecord(
    {
      startup_url: "https://neuralmind.ai/",
      startup_name: "NeuralMind"
    },
    {
      runId: "mock-completed-run",
      createdAt: clock().toISOString()
    }
  );
  for (const record of [completed, buildMockHumanReviewRunRecord(), buildMockFailedRunRecord()]) {
    runs.set(record.run_id, record);
  }
}

function safePathSegment(value) {
  return String(value || "unknown")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
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
