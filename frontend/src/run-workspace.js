export const RUN_ID_QUERY_PARAM = "run_id";
export const SECTION_QUERY_PARAM = "section";

export function runIdFromSearch(search) {
  const params = new URLSearchParams(String(search || ""));
  return String(params.get(RUN_ID_QUERY_PARAM) || params.get("runId") || "").trim();
}

export function updateRunRoute(options) {
  const runId = String(options.runId || "").trim();
  const activeSection = String(options.activeSection || "").trim();
  if ((!runId && !activeSection) || !options.location || !options.history) {
    return;
  }
  const nextUrl = new URL(options.location.href);
  if (runId) {
    nextUrl.searchParams.set(RUN_ID_QUERY_PARAM, runId);
  }
  if (activeSection) {
    nextUrl.searchParams.set(SECTION_QUERY_PARAM, activeSection);
  }
  options.history.replaceState({}, "", String(nextUrl));
}

export async function loadRunWorkspace(options) {
  const runId = String(options.runId || "").trim();
  if (!runId) {
    return null;
  }
  options.commit({
    routeRunId: runId,
    runLoadState: "loading",
    isBusy: true,
    notice: `Loading run ${runId}.`,
    errorMessage: ""
  });
  try {
    const currentRun = await options.apiClient.getRun(runId);
    options.commit({
      currentRun,
      routeRunId: currentRun.run_id,
      runLoadState: "loaded",
      activeSection: options.activeSection || "runs",
      isBusy: false,
      notice: `Run ${currentRun.run_id} loaded.`,
      errorMessage: ""
    });
    return currentRun;
  } catch (error) {
    const message = error instanceof Error ? error.message : "run_load_failed";
    const notFound = message.includes("run_not_found") || message.includes("status_404");
    options.commit({
      currentRun: null,
      routeRunId: runId,
      runLoadState: notFound ? "not_found" : "failed",
      isBusy: false,
      notice: "",
      errorMessage: notFound ? `Run ${runId} was not found.` : message
    });
    return null;
  }
}
