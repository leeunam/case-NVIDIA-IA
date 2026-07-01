import { loadRunWorkspace, updateRunRoute } from "./run-workspace.js";

export const RUN_HISTORY_FILTER_DEFAULTS = {
  search: "",
  workflow_outcome: "",
  next_action: "",
  human_review_reason: "",
  date: ""
};

/**
 * @typedef {Object} RunHistoryFilters
 * @property {string} search
 * @property {string} workflow_outcome
 * @property {string} next_action
 * @property {string} human_review_reason
 * @property {string} date
 */

/**
 * @param {Partial<RunHistoryFilters>=} overrides
 * @returns {RunHistoryFilters}
 */
export function createRunHistoryFilters(overrides = {}) {
  return {
    ...RUN_HISTORY_FILTER_DEFAULTS,
    ...overrides,
    search: text(overrides.search),
    workflow_outcome: text(overrides.workflow_outcome),
    next_action: text(overrides.next_action),
    human_review_reason: text(overrides.human_review_reason),
    date: text(overrides.date)
  };
}

/**
 * @param {FormData} formData
 * @returns {RunHistoryFilters}
 */
export function runHistoryFiltersFromFormData(formData) {
  return createRunHistoryFilters({
    search: formData.get("history_search"),
    workflow_outcome: formData.get("history_workflow_outcome"),
    next_action: formData.get("history_next_action"),
    human_review_reason: formData.get("history_human_review_reason"),
    date: formData.get("history_date")
  });
}

/**
 * @param {import("./api-contract.js").FrontendRunRecord[]} runs
 * @param {Partial<RunHistoryFilters>=} filters
 */
export function filterRunHistory(runs, filters = {}) {
  const normalized = createRunHistoryFilters(filters);
  const search = normalized.search.toLowerCase();
  return runs.filter((run) => {
    if (search && !historySearchText(run).includes(search)) {
      return false;
    }
    if (normalized.workflow_outcome && run.workflow_outcome !== normalized.workflow_outcome) {
      return false;
    }
    if (normalized.next_action && run.next_action !== normalized.next_action) {
      return false;
    }
    if (normalized.human_review_reason && !arrayValues(run.human_review_reasons).includes(normalized.human_review_reason)) {
      return false;
    }
    if (normalized.date && runDate(run) !== normalized.date) {
      return false;
    }
    return true;
  });
}

export async function loadRunHistory(options) {
  options.commit({
    runHistoryLoadState: "loading",
    isBusy: true,
    notice: options.quiet ? "" : "Loading run history.",
    errorMessage: ""
  });
  try {
    const history = await options.apiClient.listRuns();
    options.commit({
      runHistory: history.runs,
      runHistoryMetadata: {
        schema_version: history.schema_version,
        generated_at: history.generated_at,
        persistence_mode: history.persistence_mode
      },
      runHistoryLoadState: history.runs.length ? "loaded" : "empty",
      isBusy: false,
      notice: options.quiet ? "" : `Loaded ${String(history.runs.length)} run history records.`,
      errorMessage: ""
    });
    return history;
  } catch (error) {
    const message = error instanceof Error ? error.message : "run_history_load_failed";
    options.commit({
      runHistory: [],
      runHistoryLoadState: "failed",
      isBusy: false,
      notice: "",
      errorMessage: message
    });
    return null;
  }
}

export async function openRunFromHistory(options) {
  const currentRun = await loadRunWorkspace({
    runId: options.runId,
    apiClient: options.apiClient,
    commit: options.commit,
    activeSection: "runs"
  });
  if (currentRun) {
    updateRunRoute({
      runId: currentRun.run_id,
      location: options.location,
      history: options.history
    });
  }
  return currentRun;
}

function historySearchText(run) {
  const input = objectRecord(run.input) || {};
  return [
    run.run_id,
    run.startup_identifier,
    input.startup_url,
    hostname(input.startup_url),
    input.query,
    input.startup_name,
    run.workflow_outcome,
    run.next_action,
    run.created_at,
    ...arrayValues(run.human_review_reasons)
  ]
    .map((value) => String(value || "").toLowerCase())
    .join(" ");
}

function runDate(run) {
  return String(run.created_at || "").slice(0, 10);
}

function hostname(value) {
  try {
    return new URL(String(value || "")).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

function arrayValues(value) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item)).filter(Boolean);
  }
  return [];
}

function objectRecord(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return /** @type {Record<string, unknown>} */ (value);
}

function text(value) {
  return String(value || "").trim();
}
