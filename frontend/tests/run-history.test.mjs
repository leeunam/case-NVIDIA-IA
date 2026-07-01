import assert from "node:assert/strict";
import test from "node:test";

import {
  buildMockCollectionFailureEvidenceRunRecord,
  buildMockHumanReviewRunRecord,
  buildMockRunRecord
} from "../src/mock-data.js";
import {
  createRunHistoryFilters,
  filterRunHistory,
  loadRunHistory,
  openRunFromHistory,
  runHistoryFiltersFromFormData
} from "../src/run-history.js";

test("filters run history by startup, domain, outcome, next action, review reason, and date", () => {
  const completed = buildMockRunRecord(
    {
      startup_url: "https://neuralmind.ai/",
      startup_name: "NeuralMind"
    },
    {
      runId: "mock-history-completed",
      createdAt: "2026-06-30T15:00:00.000Z"
    }
  );
  const humanReview = buildMockHumanReviewRunRecord({
    runId: "mock-history-review",
    createdAt: "2026-06-29T10:00:00.000Z"
  });
  const collectionFailure = buildMockCollectionFailureEvidenceRunRecord({
    runId: "mock-history-blocked",
    createdAt: "2026-06-30T11:00:00.000Z"
  });

  assert.deepEqual(
    filterRunHistory([completed, humanReview, collectionFailure], createRunHistoryFilters({ search: "neuralmind.ai" }))
      .map((run) => run.run_id),
    ["mock-history-completed"]
  );
  assert.deepEqual(
    filterRunHistory(
      [completed, humanReview, collectionFailure],
      createRunHistoryFilters({
        workflow_outcome: "needs_more_collection_or_human_review",
        next_action: "resolve_blocking_evidence",
        human_review_reason: "robots_blocked_collection",
        date: "2026-06-30"
      })
    ).map((run) => run.run_id),
    ["mock-history-blocked"]
  );
});

test("creates filters from form data without losing empty defaults", () => {
  const data = new FormData();
  data.set("history_search", "review-startup.ai");
  data.set("history_workflow_outcome", "human_review_requested");
  data.set("history_next_action", "validate_nvidia_fit_with_human");
  data.set("history_human_review_reason", "recommendation_hypothesis_requires_human_review");
  data.set("history_date", "2026-06-30");

  assert.deepEqual(runHistoryFiltersFromFormData(data), {
    search: "review-startup.ai",
    workflow_outcome: "human_review_requested",
    next_action: "validate_nvidia_fit_with_human",
    human_review_reason: "recommendation_hypothesis_requires_human_review",
    date: "2026-06-30"
  });
});

test("loads run history through the API client", async () => {
  const record = buildMockHumanReviewRunRecord();
  let state = {};

  const history = await loadRunHistory({
    apiClient: {
      async listRuns() {
        return {
          schema_version: "frontend_api_run_history.v1",
          generated_at: "2026-06-30T15:00:00.000Z",
          persistence_mode: "mock-fixtures",
          runs: [record]
        };
      }
    },
    commit(updates) {
      state = { ...state, ...updates };
    }
  });

  assert.equal(history.runs[0].run_id, record.run_id);
  assert.equal(state.runHistoryLoadState, "loaded");
  assert.equal(state.runHistory.length, 1);
  assert.equal(state.runHistoryMetadata.persistence_mode, "mock-fixtures");
});

test("reports run history API failure as a clear state", async () => {
  let state = {};

  const history = await loadRunHistory({
    apiClient: {
      async listRuns() {
        throw new Error("api_request_failed:history_down");
      }
    },
    commit(updates) {
      state = { ...state, ...updates };
    }
  });

  assert.equal(history, null);
  assert.equal(state.runHistoryLoadState, "failed");
  assert.equal(state.runHistory.length, 0);
  assert.equal(state.errorMessage, "api_request_failed:history_down");
});

test("reopens a run from history without starting a new run", async () => {
  const record = buildMockHumanReviewRunRecord({ runId: "mock-history-open" });
  const calls = [];
  let state = {};

  const loaded = await openRunFromHistory({
    runId: "mock-history-open",
    location: { href: "http://localhost:5173/?api=mock" },
    history: {
      replaceState(_state, _title, url) {
        calls.push(["replaceState", String(url)]);
      }
    },
    apiClient: {
      async startRun() {
        calls.push(["startRun"]);
        throw new Error("should_not_start_run");
      },
      async getRun(runId) {
        calls.push(["getRun", runId]);
        return record;
      }
    },
    commit(updates) {
      state = { ...state, ...updates };
    }
  });

  assert.equal(loaded.run_id, "mock-history-open");
  assert.deepEqual(calls[0], ["getRun", "mock-history-open"]);
  assert.equal(calls.some((call) => call[0] === "startRun"), false);
  assert.match(calls[1][1], /run_id=mock-history-open/);
  assert.equal(state.currentRun.run_id, "mock-history-open");
});
