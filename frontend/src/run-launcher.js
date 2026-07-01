export const RUN_LAUNCHER_DEFAULTS = Object.freeze({
  input_mode: "startup_url",
  startup_url: "",
  query: "",
  startup_name: "",
  limit: 1,
  max_pages: 1,
  max_depth: 0,
  timeout_seconds: 15,
  output_dir: "runs",
  persistence_mode: "json",
  nvidia_corpus_path: "tests/fixtures/nvidia_knowledge_official_fixture.json",
  render_js: false,
  robots_policy: "conservative",
  retrieval_mode: "bm25",
  orchestration: "local",
  enable_search_provider: false,
  enable_reranking: false,
  reranker_model: "",
  llm_narrative: false
});

const INPUT_MODES = new Set(["startup_url", "query"]);
const PERSISTENCE_MODES = new Set(["json", "postgres", "json-postgres", "none"]);
const ROBOTS_POLICIES = new Set(["conservative", "permissive-on-error", "off"]);
const RETRIEVAL_MODES = new Set(["bm25", "pgvector"]);
const ORCHESTRATION_MODES = new Set(["local", "langgraph"]);

/**
 * @typedef {Object} RunLauncherForm
 * @property {"startup_url" | "query"} input_mode
 * @property {string} startup_url
 * @property {string} query
 * @property {string} startup_name
 * @property {number} limit
 * @property {number} max_pages
 * @property {number} max_depth
 * @property {number} timeout_seconds
 * @property {string} output_dir
 * @property {"json" | "postgres" | "json-postgres" | "none"} persistence_mode
 * @property {string} nvidia_corpus_path
 * @property {boolean} render_js
 * @property {"conservative" | "permissive-on-error" | "off"} robots_policy
 * @property {"bm25" | "pgvector"} retrieval_mode
 * @property {"local" | "langgraph"} orchestration
 * @property {boolean} enable_search_provider
 * @property {boolean} enable_reranking
 * @property {string} reranker_model
 * @property {boolean} llm_narrative
 */

/**
 * @param {Partial<RunLauncherForm>=} overrides
 * @returns {RunLauncherForm}
 */
export function createRunLauncherForm(overrides = {}) {
  const form = {
    ...RUN_LAUNCHER_DEFAULTS,
    ...overrides
  };
  return {
    ...form,
    input_mode: choice(form.input_mode, INPUT_MODES, RUN_LAUNCHER_DEFAULTS.input_mode),
    limit: integerValue(form.limit, RUN_LAUNCHER_DEFAULTS.limit),
    max_pages: integerValue(form.max_pages, RUN_LAUNCHER_DEFAULTS.max_pages),
    max_depth: integerValue(form.max_depth, RUN_LAUNCHER_DEFAULTS.max_depth),
    timeout_seconds: integerValue(form.timeout_seconds, RUN_LAUNCHER_DEFAULTS.timeout_seconds),
    persistence_mode: choice(form.persistence_mode, PERSISTENCE_MODES, RUN_LAUNCHER_DEFAULTS.persistence_mode),
    robots_policy: choice(form.robots_policy, ROBOTS_POLICIES, RUN_LAUNCHER_DEFAULTS.robots_policy),
    retrieval_mode: choice(form.retrieval_mode, RETRIEVAL_MODES, RUN_LAUNCHER_DEFAULTS.retrieval_mode),
    orchestration: choice(form.orchestration, ORCHESTRATION_MODES, RUN_LAUNCHER_DEFAULTS.orchestration),
    render_js: Boolean(form.render_js),
    enable_search_provider: Boolean(form.enable_search_provider),
    enable_reranking: Boolean(form.enable_reranking),
    llm_narrative: Boolean(form.llm_narrative)
  };
}

/**
 * @param {FormData} formData
 * @returns {RunLauncherForm}
 */
export function runLauncherFormFromFormData(formData) {
  return createRunLauncherForm({
    input_mode: textValue(formData, "input_mode") || RUN_LAUNCHER_DEFAULTS.input_mode,
    startup_url: textValue(formData, "startup_url"),
    query: textValue(formData, "query"),
    startup_name: textValue(formData, "startup_name"),
    limit: numberValue(formData, "limit", RUN_LAUNCHER_DEFAULTS.limit),
    max_pages: numberValue(formData, "max_pages", RUN_LAUNCHER_DEFAULTS.max_pages),
    max_depth: numberValue(formData, "max_depth", RUN_LAUNCHER_DEFAULTS.max_depth),
    timeout_seconds: numberValue(formData, "timeout_seconds", RUN_LAUNCHER_DEFAULTS.timeout_seconds),
    output_dir: textValue(formData, "output_dir") || RUN_LAUNCHER_DEFAULTS.output_dir,
    persistence_mode: textValue(formData, "persistence_mode") || RUN_LAUNCHER_DEFAULTS.persistence_mode,
    nvidia_corpus_path: textValue(formData, "nvidia_corpus_path") || RUN_LAUNCHER_DEFAULTS.nvidia_corpus_path,
    render_js: formData.get("render_js") === "on",
    robots_policy: textValue(formData, "robots_policy") || RUN_LAUNCHER_DEFAULTS.robots_policy,
    retrieval_mode: textValue(formData, "retrieval_mode") || RUN_LAUNCHER_DEFAULTS.retrieval_mode,
    orchestration: textValue(formData, "orchestration") || RUN_LAUNCHER_DEFAULTS.orchestration,
    enable_search_provider: formData.get("enable_search_provider") === "on",
    enable_reranking: formData.get("enable_reranking") === "on",
    reranker_model: textValue(formData, "reranker_model"),
    llm_narrative: formData.get("llm_narrative") === "on"
  });
}

/**
 * @param {RunLauncherForm} form
 * @returns {string[]}
 */
export function validateRunLauncherForm(form) {
  const errors = [];
  const mode = choice(form.input_mode, INPUT_MODES, "");

  if (!mode) {
    errors.push("Choose startup URL or bounded query.");
  }
  if (mode === "startup_url") {
    if (!form.startup_url) {
      errors.push("Startup URL is required.");
    } else if (!isHttpUrl(form.startup_url)) {
      errors.push("Startup URL must be a valid http or https URL.");
    }
  }
  if (mode === "query" && !form.query) {
    errors.push("Bounded query is required.");
  }
  if (mode === "startup_url" && form.enable_search_provider) {
    errors.push("Search provider can only be enabled for bounded query runs.");
  }

  validateIntegerRange(errors, "Candidate limit", form.limit, 1, 5);
  validateIntegerRange(errors, "Max pages", form.max_pages, 1, 5);
  validateIntegerRange(errors, "Max depth", form.max_depth, 0, 2);
  validateIntegerRange(errors, "Timeout seconds", form.timeout_seconds, 5, 60);

  if (!PERSISTENCE_MODES.has(form.persistence_mode)) {
    errors.push("Persistence mode is not supported.");
  }
  if (!ROBOTS_POLICIES.has(form.robots_policy)) {
    errors.push("Robots policy is not supported.");
  }
  if (!RETRIEVAL_MODES.has(form.retrieval_mode)) {
    errors.push("Retrieval mode is not supported.");
  }
  if (!ORCHESTRATION_MODES.has(form.orchestration)) {
    errors.push("Orchestration mode is not supported.");
  }
  if (form.enable_reranking && form.retrieval_mode !== "pgvector") {
    errors.push("Reranking requires pgvector retrieval.");
  }
  if (!form.enable_reranking && form.reranker_model) {
    errors.push("Reranker model only applies when reranking is enabled.");
  }

  return errors;
}

/**
 * @param {RunLauncherForm} form
 * @returns {import("./api-contract.js").FrontendRunRequest}
 */
export function runRequestFromLauncherForm(form) {
  const errors = validateRunLauncherForm(form);
  if (errors.length) {
    throw new Error(errors.join(" "));
  }
  return {
    startup_url: form.input_mode === "startup_url" ? form.startup_url : undefined,
    query: form.input_mode === "query" ? form.query : undefined,
    startup_name: form.startup_name || "unknown",
    limit: form.input_mode === "query" ? form.limit : 1,
    max_pages: form.max_pages,
    max_depth: form.max_depth,
    timeout_seconds: form.timeout_seconds,
    output_dir: form.output_dir || RUN_LAUNCHER_DEFAULTS.output_dir,
    persistence_mode: form.persistence_mode,
    nvidia_corpus_path: form.nvidia_corpus_path || RUN_LAUNCHER_DEFAULTS.nvidia_corpus_path,
    render_js: form.render_js,
    robots_policy: form.robots_policy,
    retrieval_mode: form.retrieval_mode,
    orchestration: form.orchestration,
    enable_search_provider: form.input_mode === "query" ? form.enable_search_provider : false,
    enable_reranking: form.enable_reranking,
    reranker_model: form.enable_reranking ? form.reranker_model : "",
    llm_narrative: form.llm_narrative
  };
}

/**
 * @param {{
 *   formData: FormData,
 *   apiClient: import("./api-contract.js").FrontendApiClient,
 *   commit: (updates: Record<string, unknown>) => void
 * }} options
 */
export async function submitRunLauncher(options) {
  const launcherForm = runLauncherFormFromFormData(options.formData);
  const errors = validateRunLauncherForm(launcherForm);
  if (errors.length) {
    options.commit({
      launcherForm,
      isBusy: false,
      errorMessage: errors.join(" "),
      notice: ""
    });
    return null;
  }

  const request = runRequestFromLauncherForm(launcherForm);
  options.commit({
    launcherForm,
    isBusy: true,
    notice: "Run submitted.",
    errorMessage: ""
  });
  try {
    const currentRun = await options.apiClient.startRun(request);
    options.commit({
      launcherForm,
      currentRun,
      activeSection: "runs",
      isBusy: false,
      notice: `Run ${currentRun.run_id} completed.`,
      errorMessage: ""
    });
    return currentRun;
  } catch (error) {
    options.commit({
      launcherForm,
      isBusy: false,
      notice: "",
      errorMessage: error instanceof Error ? error.message : "run_failed"
    });
    return null;
  }
}

function textValue(formData, key) {
  return String(formData.get(key) || "").trim();
}

function numberValue(formData, key, fallback) {
  const raw = formData.get(key);
  if (raw === null || raw === "") {
    return fallback;
  }
  return Number(raw);
}

function integerValue(value, fallback) {
  if (value === undefined || value === null || value === "") {
    return fallback;
  }
  const number = Number(value);
  return Number.isInteger(number) ? number : number;
}

function choice(value, choices, fallback) {
  const text = String(value || "").trim();
  return choices.has(text) ? text : fallback;
}

function validateIntegerRange(errors, label, value, min, max) {
  if (!Number.isInteger(value)) {
    errors.push(`${label} must be an integer.`);
    return;
  }
  if (value < min || value > max) {
    errors.push(`${label} must be between ${min} and ${max}.`);
  }
}

function isHttpUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}
