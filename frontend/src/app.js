import { createFrontendApiClient } from "./api-contract.js";
import { createMockFrontendApiClient } from "./mock-data.js";
import { createInitialState, renderApp } from "./renderer.js";
import {
  createRunHistoryFilters,
  loadRunHistory,
  openRunFromHistory,
  runHistoryFiltersFromFormData
} from "./run-history.js";
import { runLauncherFormFromFormData, submitRunLauncher } from "./run-launcher.js";
import { loadRunWorkspace, runIdFromSearch, updateRunRoute } from "./run-workspace.js";

const root = document.querySelector("#app");
const params = new URLSearchParams(window.location.search);
const apiMode = params.get("api") === "real" ? "real" : "mock";
const apiBaseUrl = params.get("baseUrl") || "http://127.0.0.1:8000";
const initialRouteRunId = runIdFromSearch(window.location.search);
const apiClient =
  apiMode === "real"
    ? createFrontendApiClient({ baseUrl: apiBaseUrl })
    : createMockFrontendApiClient({ delayMs: 120 });

let state = createInitialState({ apiMode, apiBaseUrl, routeRunId: initialRouteRunId });

render();
void loadSmokeMatrix({ quiet: true });
void loadRunHistory({ apiClient, commit, quiet: true });
if (initialRouteRunId) {
  void loadRunFromRoute(initialRouteRunId);
}

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
      void submitRunLauncher({
        formData: new FormData(form),
        apiClient,
        commit
      }).then((currentRun) => {
        if (currentRun) {
          updateRunRoute({ runId: currentRun.run_id, location: window.location, history: window.history });
          commit({ routeRunId: currentRun.run_id, runLoadState: "loaded" });
          void loadRunHistory({ apiClient, commit, quiet: true });
        }
      });
    });

    for (const control of form.querySelectorAll("[data-launcher-autosync]")) {
      control.addEventListener("change", () => {
        commit({
          launcherForm: runLauncherFormFromFormData(new FormData(form)),
          notice: "",
          errorMessage: ""
        });
      });
    }
  }

  for (const button of root.querySelectorAll("[data-refresh-run]")) {
    button.addEventListener("click", () => {
      void loadRunFromRoute(button.getAttribute("data-refresh-run") || "");
    });
  }

  for (const button of root.querySelectorAll("[data-open-run]")) {
    button.addEventListener("click", () => {
      void openRunFromHistory({
        runId: button.getAttribute("data-open-run") || "",
        apiClient,
        commit,
        location: window.location,
        history: window.history
      });
    });
  }

  for (const button of root.querySelectorAll("[data-refresh-history]")) {
    button.addEventListener("click", () => {
      void loadRunHistory({ apiClient, commit });
    });
  }

  const historyFilterForm = root.querySelector("[data-run-history-filters]");
  if (historyFilterForm) {
    historyFilterForm.addEventListener("submit", (event) => {
      event.preventDefault();
      commit({
        runHistoryFilters: runHistoryFiltersFromFormData(new FormData(historyFilterForm)),
        notice: "",
        errorMessage: ""
      });
    });
  }

  for (const button of root.querySelectorAll("[data-reset-history-filters]")) {
    button.addEventListener("click", () => {
      commit({
        runHistoryFilters: createRunHistoryFilters(),
        notice: "",
        errorMessage: ""
      });
    });
  }

  for (const button of root.querySelectorAll("[data-load-smokes]")) {
    button.addEventListener("click", () => {
      void loadSmokeMatrix();
    });
  }
}

async function loadRunFromRoute(runId) {
  const currentRun = await loadRunWorkspace({ runId, apiClient, commit });
  if (currentRun) {
    updateRunRoute({ runId: currentRun.run_id, location: window.location, history: window.history });
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
