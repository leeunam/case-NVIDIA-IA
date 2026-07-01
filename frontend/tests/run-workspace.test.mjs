import assert from "node:assert/strict";
import test from "node:test";

import { buildMockRunRecord } from "../src/mock-data.js";
import { loadRunWorkspace, runIdFromSearch, updateRunRoute } from "../src/run-workspace.js";

test("parses run_id route parameter with runId compatibility", () => {
  assert.equal(runIdFromSearch("?run_id=op-20260630T120000Z"), "op-20260630T120000Z");
  assert.equal(runIdFromSearch("?runId=legacy-run"), "legacy-run");
  assert.equal(runIdFromSearch("?api=real"), "");
});

test("loads a single run workspace from the API without starting a run", async () => {
  const record = buildMockRunRecord(
    {
      startup_url: "https://neuralmind.ai/",
      startup_name: "NeuralMind"
    },
    {
      runId: "mock-route-run",
      createdAt: "2026-06-30T15:00:00.000Z"
    }
  );
  const calls = [];
  let state = {};

  const loaded = await loadRunWorkspace({
    runId: "mock-route-run",
    activeSection: "assessment",
    apiClient: {
      async startRun() {
        calls.push(["startRun"]);
        throw new Error("should_not_start_run");
      },
      async getRun(runId) {
        calls.push(["getRun", runId]);
        return record;
      },
      async getProductionSmokeMatrix() {
        throw new Error("not_used");
      }
    },
    commit(updates) {
      state = { ...state, ...updates };
    }
  });

  assert.equal(loaded.run_id, "mock-route-run");
  assert.deepEqual(calls, [["getRun", "mock-route-run"]]);
  assert.equal(state.currentRun.run_id, "mock-route-run");
  assert.equal(state.runLoadState, "loaded");
  assert.equal(state.activeSection, "assessment");
});

test("reports missing route run as not found", async () => {
  let state = {};

  const loaded = await loadRunWorkspace({
    runId: "missing-run",
    apiClient: {
      async startRun() {
        throw new Error("should_not_start_run");
      },
      async getRun() {
        throw new Error("run_not_found");
      },
      async getProductionSmokeMatrix() {
        throw new Error("not_used");
      }
    },
    commit(updates) {
      state = { ...state, ...updates };
    }
  });

  assert.equal(loaded, null);
  assert.equal(state.currentRun, null);
  assert.equal(state.runLoadState, "not_found");
  assert.match(state.errorMessage, /missing-run/);
});

test("updates the route without dropping existing API settings", () => {
  const calls = [];
  updateRunRoute({
    runId: "mock-route-run",
    activeSection: "evidence",
    location: { href: "http://localhost:4173/?api=real&baseUrl=http%3A%2F%2F127.0.0.1%3A8000" },
    history: {
      replaceState(state, title, url) {
        calls.push({ state, title, url: String(url) });
      }
    }
  });

  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /api=real/);
  assert.match(calls[0].url, /run_id=mock-route-run/);
  assert.match(calls[0].url, /section=evidence/);
});

test("updates a section-only route for launcher and smoke QA views", () => {
  const calls = [];
  updateRunRoute({
    activeSection: "production-smokes",
    location: { href: "http://localhost:4173/?api=mock" },
    history: {
      replaceState(state, title, url) {
        calls.push({ state, title, url: String(url) });
      }
    }
  });

  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /api=mock/);
  assert.match(calls[0].url, /section=production-smokes/);
  assert.doesNotMatch(calls[0].url, /run_id=/);
});
