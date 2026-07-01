export const RUN_CREATE_SCHEMA_VERSION = "frontend_api_run_create.v1";
export const RUN_RECORD_SCHEMA_VERSION = "frontend_api_run.v1";
export const RUN_HISTORY_SCHEMA_VERSION = "frontend_api_run_history.v1";
export const SMOKE_MATRIX_SCHEMA_VERSION = "frontend_api_production_smoke_matrix.v1";

/**
 * @typedef {"json" | "postgres" | "json-postgres" | "none"} PersistenceMode
 * @typedef {"conservative" | "permissive-on-error" | "off"} RobotsPolicy
 * @typedef {"bm25" | "pgvector"} RetrievalMode
 * @typedef {"local" | "langgraph"} OrchestrationMode
 *
 * @typedef {Object} FrontendRunRequest
 * @property {typeof RUN_CREATE_SCHEMA_VERSION=} schema_version
 * @property {string=} startup_url
 * @property {string=} query
 * @property {string=} startup_name
 * @property {number=} limit
 * @property {number=} max_pages
 * @property {number=} max_depth
 * @property {number=} timeout_seconds
 * @property {string=} output_dir
 * @property {PersistenceMode=} persistence_mode
 * @property {string=} nvidia_corpus_path
 * @property {boolean=} render_js
 * @property {RobotsPolicy=} robots_policy
 * @property {RetrievalMode=} retrieval_mode
 * @property {OrchestrationMode=} orchestration
 * @property {boolean=} enable_search_provider
 * @property {boolean=} enable_reranking
 * @property {string=} reranker_model
 * @property {boolean=} llm_narrative
 *
 * @typedef {Object} FrontendRunRecord
 * @property {typeof RUN_RECORD_SCHEMA_VERSION} schema_version
 * @property {string} run_id
 * @property {"completed" | "failed" | string} status
 * @property {string} workflow_outcome
 * @property {string} created_at
 * @property {Record<string, unknown>} input
 * @property {string} startup_identifier
 * @property {string} next_action
 * @property {unknown} briefing_reference
 * @property {unknown[]} human_review_reasons
 * @property {unknown[]} branch_decisions
 * @property {{artifact_locations?: Record<string, unknown>, persistence_references?: unknown[]}} artifact_references
 * @property {unknown[]} errors
 * @property {Record<string, unknown>} options
 * @property {Record<string, unknown>} final_payload
 *
 * @typedef {Object} FrontendRunHistory
 * @property {typeof RUN_HISTORY_SCHEMA_VERSION} schema_version
 * @property {string} generated_at
 * @property {string} persistence_mode
 * @property {FrontendRunRecord[]} runs
 *
 * @typedef {Object} ProductionSmokeStep
 * @property {string} integration_id
 * @property {string} title
 * @property {string} status
 * @property {string} bottleneck
 * @property {string} message
 * @property {string} command
 * @property {string[]} prerequisites
 * @property {string[]} required_env_vars
 * @property {string[]} expected_artifacts
 * @property {string[]} cleanup
 * @property {Record<string, unknown>} payload
 *
 * @typedef {Object} ProductionSmokeMatrix
 * @property {typeof SMOKE_MATRIX_SCHEMA_VERSION} schema_version
 * @property {boolean} read_only
 * @property {{schema_version: string, overall_status: string, steps: ProductionSmokeStep[]}} matrix
 *
 * @typedef {Object} FrontendApiClient
 * @property {(request: FrontendRunRequest) => Promise<FrontendRunRecord>} startRun
 * @property {(runId: string) => Promise<FrontendRunRecord>} getRun
 * @property {() => Promise<FrontendRunHistory>} listRuns
 * @property {(only?: string[]) => Promise<ProductionSmokeMatrix>} getProductionSmokeMatrix
 */

/**
 * Create a thin client for the #98 backend-for-frontend API.
 *
 * @param {{baseUrl?: string, fetchImpl?: typeof fetch}=} options
 * @returns {FrontendApiClient}
 */
export function createFrontendApiClient(options = {}) {
  const baseUrl = normalizeBaseUrl(options.baseUrl || "");
  const fetchImpl = options.fetchImpl || globalThis.fetch;
  if (typeof fetchImpl !== "function") {
    throw new Error("fetch_impl_required");
  }

  return {
    async startRun(request) {
      validateRunRequest(request);
      const payload = {
        schema_version: RUN_CREATE_SCHEMA_VERSION,
        ...request
      };
      const response = await fetchImpl(apiUrl(baseUrl, "/api/runs"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });
      return assertRunRecord(await readJsonResponse(response));
    },

    async getRun(runId) {
      if (!String(runId || "").trim()) {
        throw new Error("run_id_required");
      }
      const response = await fetchImpl(apiUrl(baseUrl, `/api/runs/${encodeURIComponent(runId)}`));
      return assertRunRecord(await readJsonResponse(response));
    },

    async listRuns() {
      const response = await fetchImpl(apiUrl(baseUrl, "/api/runs"));
      return assertRunHistory(await readJsonResponse(response));
    },

    async getProductionSmokeMatrix(only = []) {
      const selected = only.map((item) => String(item).trim()).filter(Boolean);
      const suffix = selected.length ? `?only=${encodeURIComponent(selected.join(","))}` : "";
      const response = await fetchImpl(apiUrl(baseUrl, `/api/production-smoke-matrix${suffix}`));
      return assertSmokeMatrix(await readJsonResponse(response));
    }
  };
}

/**
 * @param {FrontendRunRequest} request
 */
export function validateRunRequest(request) {
  const startupUrl = textOrEmpty(request.startup_url);
  const query = textOrEmpty(request.query);
  if (Boolean(startupUrl) === Boolean(query)) {
    throw new Error("provide_exactly_one_of_startup_url_or_query");
  }
}

/**
 * @param {unknown} payload
 * @returns {FrontendRunRecord}
 */
export function assertRunRecord(payload) {
  const record = objectPayload(payload, "run_record");
  requireSchema(record, RUN_RECORD_SCHEMA_VERSION, "run_record");
  requireString(record, "run_id", "run_record");
  requireString(record, "status", "run_record");
  requireString(record, "workflow_outcome", "run_record");
  requireString(record, "startup_identifier", "run_record");
  requireString(record, "next_action", "run_record");
  requireObject(record, "artifact_references", "run_record");
  requireArray(record, "human_review_reasons", "run_record");
  requireArray(record, "branch_decisions", "run_record");
  requireArray(record, "errors", "run_record");
  requireObject(record, "final_payload", "run_record");
  return /** @type {FrontendRunRecord} */ (record);
}

/**
 * @param {unknown} payload
 * @returns {FrontendRunHistory}
 */
export function assertRunHistory(payload) {
  const record = objectPayload(payload, "run_history");
  requireSchema(record, RUN_HISTORY_SCHEMA_VERSION, "run_history");
  requireString(record, "generated_at", "run_history");
  requireString(record, "persistence_mode", "run_history");
  requireArray(record, "runs", "run_history");
  const runs = record.runs.map((run) => assertRunRecord(run));
  return /** @type {FrontendRunHistory} */ ({
    ...record,
    runs
  });
}

/**
 * @param {unknown} payload
 * @returns {ProductionSmokeMatrix}
 */
export function assertSmokeMatrix(payload) {
  const record = objectPayload(payload, "production_smoke_matrix");
  requireSchema(record, SMOKE_MATRIX_SCHEMA_VERSION, "production_smoke_matrix");
  if (record.read_only !== true) {
    throw new Error("production_smoke_matrix_read_only_required");
  }
  const matrix = requireObject(record, "matrix", "production_smoke_matrix");
  requireString(matrix, "schema_version", "production_smoke_matrix.matrix");
  requireString(matrix, "overall_status", "production_smoke_matrix.matrix");
  requireArray(matrix, "steps", "production_smoke_matrix.matrix");
  return /** @type {ProductionSmokeMatrix} */ (record);
}

/**
 * @param {Response} response
 * @returns {Promise<unknown>}
 */
async function readJsonResponse(response) {
  let payload;
  try {
    payload = await response.json();
  } catch (error) {
    throw new Error(`api_invalid_json:${error instanceof Error ? error.message : "unknown"}`);
  }
  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? String(payload.detail)
        : `status_${response.status}`;
    throw new Error(`api_request_failed:${detail}`);
  }
  return payload;
}

function normalizeBaseUrl(value) {
  return String(value || "").replace(/\/+$/, "");
}

function apiUrl(baseUrl, path) {
  return `${baseUrl}${path}`;
}

function textOrEmpty(value) {
  return String(value || "").trim();
}

function objectPayload(payload, label) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error(`${label}_must_be_object`);
  }
  return /** @type {Record<string, unknown>} */ (payload);
}

function requireSchema(record, expected, label) {
  if (record.schema_version !== expected) {
    throw new Error(`${label}_schema_mismatch:${String(record.schema_version || "missing")}`);
  }
}

function requireString(record, key, label) {
  if (typeof record[key] !== "string") {
    throw new Error(`${label}_${key}_must_be_string`);
  }
}

function requireObject(record, key, label) {
  const value = record[key];
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label}_${key}_must_be_object`);
  }
  return /** @type {Record<string, unknown>} */ (value);
}

function requireArray(record, key, label) {
  if (!Array.isArray(record[key])) {
    throw new Error(`${label}_${key}_must_be_array`);
  }
}
