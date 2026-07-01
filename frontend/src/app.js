import { createFrontendApiClient } from "./api-contract.js";
import { createMockFrontendApiClient } from "./mock-data.js";
import { createInitialState, renderApp } from "./renderer.js";

const root = document.querySelector("#app");
const params = new URLSearchParams(window.location.search);
const apiMode = params.get("api") === "real" ? "real" : "mock";
const apiBaseUrl = params.get("baseUrl") || "http://127.0.0.1:8000";
const apiClient =
  apiMode === "real"
    ? createFrontendApiClient({ baseUrl: apiBaseUrl })
    : createMockFrontendApiClient({ delayMs: 120 });

let state = createInitialState({ apiMode, apiBaseUrl });

render();
void loadSmokeMatrix({ quiet: true });

function render() {
  root.innerHTML = renderApp(state);
  bindEvents();
}

function commit(updates) {
  state = {
    ...state,
    ...updates
  };
  render();
}

function bindEvents() {
  for (const button of root.querySelectorAll("[data-section]")) {
    button.addEventListener("click", () => {
      commit({
        activeSection: button.getAttribute("data-section") || "runs",
        notice: "",
        errorMessage: ""
      });
    });
  }

  const form = root.querySelector("[data-run-form]");
  if (form) {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      void startRun(new FormData(form));
    });
  }

  for (const button of root.querySelectorAll("[data-refresh-run]")) {
    button.addEventListener("click", () => {
      void refreshRun(button.getAttribute("data-refresh-run") || "");
    });
  }

  for (const button of root.querySelectorAll("[data-load-smokes]")) {
    button.addEventListener("click", () => {
      void loadSmokeMatrix();
    });
  }
}

async function startRun(formData) {
  const request = runRequestFromForm(formData);
  if (Boolean(request.startup_url) === Boolean(request.query)) {
    commit({
      errorMessage: "Provide exactly one startup URL or bounded query.",
      notice: ""
    });
    return;
  }
  commit({ isBusy: true, notice: "Run submitted.", errorMessage: "" });
  try {
    const currentRun = await apiClient.startRun(request);
    commit({
      currentRun,
      activeSection: "runs",
      isBusy: false,
      notice: `Run ${currentRun.run_id} completed.`,
      errorMessage: ""
    });
  } catch (error) {
    commit({
      isBusy: false,
      notice: "",
      errorMessage: error instanceof Error ? error.message : "run_failed"
    });
  }
}

async function refreshRun(runId) {
  if (!runId) {
    return;
  }
  commit({ isBusy: true, notice: "Refreshing run.", errorMessage: "" });
  try {
    const currentRun = await apiClient.getRun(runId);
    commit({
      currentRun,
      isBusy: false,
      notice: `Run ${runId} refreshed.`,
      errorMessage: ""
    });
  } catch (error) {
    commit({
      isBusy: false,
      notice: "",
      errorMessage: error instanceof Error ? error.message : "run_refresh_failed"
    });
  }
}

async function loadSmokeMatrix(options = {}) {
  try {
    const smokeMatrix = await apiClient.getProductionSmokeMatrix();
    commit({
      smokeMatrix,
      notice: options.quiet ? state.notice : "Smoke matrix refreshed.",
      errorMessage: ""
    });
  } catch (error) {
    commit({
      errorMessage: error instanceof Error ? error.message : "smoke_matrix_failed",
      notice: ""
    });
  }
}

function runRequestFromForm(formData) {
  return {
    startup_url: textValue(formData, "startup_url") || undefined,
    query: textValue(formData, "query") || undefined,
    startup_name: textValue(formData, "startup_name") || "unknown",
    max_pages: numberValue(formData, "max_pages", 1),
    max_depth: numberValue(formData, "max_depth", 0),
    limit: 1,
    output_dir: "runs",
    persistence_mode: textValue(formData, "persistence_mode") || "json",
    nvidia_corpus_path: "tests/fixtures/nvidia_knowledge_official_fixture.json",
    render_js: formData.get("render_js") === "on",
    robots_policy: "conservative",
    retrieval_mode: "bm25",
    orchestration: "local",
    enable_search_provider: formData.get("enable_search_provider") === "on",
    enable_reranking: formData.get("enable_reranking") === "on",
    reranker_model: "",
    llm_narrative: formData.get("llm_narrative") === "on"
  };
}

function textValue(formData, key) {
  return String(formData.get(key) || "").trim();
}

function numberValue(formData, key, fallback) {
  const value = Number(formData.get(key));
  return Number.isFinite(value) ? value : fallback;
}
