import { createFrontendApiClient } from "./api-contract.js";
import { createMockFrontendApiClient } from "./mock-data.js";
import { briefingExportText, createInitialState, renderApp } from "./renderer.js";
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

  for (const button of root.querySelectorAll("[data-load-smokes]")) {
    button.addEventListener("click", () => {
      void loadSmokeMatrix();
    });
  }

  for (const button of root.querySelectorAll("[data-copy-briefing]")) {
    button.addEventListener("click", () => {
      void copyBriefing();
    });
  }

  for (const button of root.querySelectorAll("[data-download-briefing]")) {
    button.addEventListener("click", () => {
      downloadBriefing();
    });
  }

  for (const button of root.querySelectorAll("[data-print-briefing]")) {
    button.addEventListener("click", () => {
      window.print();
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

async function copyBriefing() {
  if (!state.currentRun) {
    return;
  }
  if (!navigator.clipboard || typeof navigator.clipboard.writeText !== "function") {
    commit({
      notice: "",
      errorMessage: "Clipboard API is not available in this browser."
    });
    return;
  }
  try {
    await navigator.clipboard.writeText(briefingExportText(state.currentRun));
    commit({
      notice: "Briefing copied with evidence and citation references.",
      errorMessage: ""
    });
  } catch (error) {
    commit({
      notice: "",
      errorMessage: error instanceof Error ? error.message : "briefing_copy_failed"
    });
  }
}

function downloadBriefing() {
  if (!state.currentRun) {
    return;
  }
  const blob = new Blob([briefingExportText(state.currentRun)], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${state.currentRun.run_id}-briefing.txt`;
  anchor.click();
  URL.revokeObjectURL(url);
  commit({
    notice: "Briefing export prepared with evidence and citation references.",
    errorMessage: ""
  });
}
