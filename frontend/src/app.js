import { createFrontendApiClient } from "./api-contract.js";
import { createMockFrontendApiClient } from "./mock-data.js";
import { createInitialState, renderApp } from "./renderer.js";
import { runLauncherFormFromFormData, submitRunLauncher } from "./run-launcher.js";

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
      void submitRunLauncher({
        formData: new FormData(form),
        apiClient,
        commit
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
      void refreshRun(button.getAttribute("data-refresh-run") || "");
    });
  }

  for (const button of root.querySelectorAll("[data-load-smokes]")) {
    button.addEventListener("click", () => {
      void loadSmokeMatrix();
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
