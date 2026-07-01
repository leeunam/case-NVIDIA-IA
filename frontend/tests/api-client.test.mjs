import assert from "node:assert/strict";
import test from "node:test";

import {
  RUN_CREATE_SCHEMA_VERSION,
  RUN_HISTORY_SCHEMA_VERSION,
  RUN_RECORD_SCHEMA_VERSION,
  SMOKE_MATRIX_SCHEMA_VERSION,
  createFrontendApiClient,
  validateRunRequest
} from "../src/api-contract.js";
import { createMockFrontendApiClient } from "../src/mock-data.js";

test("mock API client starts and retrieves a run record", async () => {
  const client = createMockFrontendApiClient({
    clock: () => new Date("2026-06-30T15:00:00.000Z")
  });

  const record = await client.startRun({
    startup_url: "https://neuralmind.ai/",
    startup_name: "NeuralMind",
    max_pages: 1,
    max_depth: 0
  });

  assert.equal(record.schema_version, RUN_RECORD_SCHEMA_VERSION);
  assert.equal(record.run_id, "mock-run-001");
  assert.equal(record.status, "completed");
  assert.equal(record.workflow_outcome, "briefing_generated");
  assert.equal(record.startup_identifier, "NeuralMind");
  assert.equal(record.final_payload.ai_native_assessment.classification, "ai_native");

  const loaded = await client.getRun("mock-run-001");
  assert.deepEqual(loaded, record);
});

test("mock API client exposes fixture-backed run history", async () => {
  const client = createMockFrontendApiClient({
    clock: () => new Date("2026-06-30T15:00:00.000Z")
  });

  const history = await client.listRuns();

  assert.equal(history.schema_version, RUN_HISTORY_SCHEMA_VERSION);
  assert.equal(history.persistence_mode, "mock-fixtures");
  assert.ok(history.runs.length >= 4);
  assert.ok(history.runs.some((run) => run.run_id === "mock-completed-run"));
  assert.ok(history.runs.some((run) => run.workflow_outcome === "human_review_requested"));
  assert.ok(history.runs.some((run) => run.final_payload.missing_artifacts?.includes("briefing")));
});

test("mock API client exposes read-only production smokes", async () => {
  const client = createMockFrontendApiClient();

  const payload = await client.getProductionSmokeMatrix(["postgres_persistence"]);

  assert.equal(payload.schema_version, SMOKE_MATRIX_SCHEMA_VERSION);
  assert.equal(payload.read_only, true);
  assert.equal(payload.matrix.steps.length, 1);
  assert.equal(payload.matrix.steps[0].integration_id, "postgres_persistence");
  assert.equal(payload.matrix.steps[0].status, "skipped");
});

test("real API client sends the #98 run contract", async () => {
  const calls = [];
  const client = createFrontendApiClient({
    baseUrl: "http://127.0.0.1:8000/",
    fetchImpl: async (url, init = {}) => {
      calls.push({ url, init });
      return response({
        schema_version: RUN_RECORD_SCHEMA_VERSION,
        run_id: "api-run-1",
        status: "completed",
        workflow_outcome: "briefing_generated",
        created_at: "2026-06-30T15:00:00Z",
        input: { startup_url: "https://startup.ai/", query: null, startup_name: "Startup AI" },
        startup_identifier: "Startup AI",
        next_action: "prepare_technical_outreach",
        briefing_reference: null,
        human_review_reasons: [],
        branch_decisions: [],
        artifact_references: { artifact_locations: {}, persistence_references: [] },
        errors: [],
        options: {},
        final_payload: {}
      });
    }
  });

  const record = await client.startRun({ startup_url: "https://startup.ai/" });

  assert.equal(record.run_id, "api-run-1");
  assert.equal(calls[0].url, "http://127.0.0.1:8000/api/runs");
  assert.equal(calls[0].init.method, "POST");
  assert.equal(JSON.parse(calls[0].init.body).schema_version, RUN_CREATE_SCHEMA_VERSION);
});

test("real API client retrieves API-provided run history", async () => {
  const calls = [];
  const client = createFrontendApiClient({
    baseUrl: "http://127.0.0.1:8000/",
    fetchImpl: async (url, init = {}) => {
      calls.push({ url, init });
      return response({
        schema_version: RUN_HISTORY_SCHEMA_VERSION,
        generated_at: "2026-06-30T15:30:00.000Z",
        persistence_mode: "json",
        runs: [
          {
            schema_version: RUN_RECORD_SCHEMA_VERSION,
            run_id: "api-run-history-1",
            status: "completed",
            workflow_outcome: "human_review_requested",
            created_at: "2026-06-30T15:00:00Z",
            input: { startup_url: "https://startup.ai/", query: null, startup_name: "Startup AI" },
            startup_identifier: "Startup AI",
            next_action: "validate_nvidia_fit_with_human",
            briefing_reference: null,
            human_review_reasons: ["missing_official_citation"],
            branch_decisions: [],
            artifact_references: { artifact_locations: {}, persistence_references: [] },
            errors: [],
            options: {},
            final_payload: { missing_artifacts: ["briefing"] }
          }
        ]
      });
    }
  });

  const history = await client.listRuns();

  assert.equal(history.runs.length, 1);
  assert.equal(history.runs[0].run_id, "api-run-history-1");
  assert.equal(calls[0].url, "http://127.0.0.1:8000/api/runs");
  assert.equal(calls[0].init.method, undefined);
});

test("run request validation preserves exactly-one input rule", () => {
  assert.throws(
    () => validateRunRequest({ startup_url: "https://startup.ai/", query: "startups AI" }),
    /provide_exactly_one/
  );
  assert.throws(() => validateRunRequest({}), /provide_exactly_one/);
});

function response(payload, ok = true) {
  return {
    ok,
    status: ok ? 200 : 400,
    async json() {
      return payload;
    }
  };
}
