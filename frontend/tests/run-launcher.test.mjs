import assert from "node:assert/strict";
import test from "node:test";

import { createInitialState } from "../src/renderer.js";
import { buildMockRunRecord } from "../src/mock-data.js";
import {
  createRunLauncherForm,
  runRequestFromLauncherForm,
  submitRunLauncher,
  validateRunLauncherForm
} from "../src/run-launcher.js";

test("validates empty inputs, invalid URLs, unsafe limits, and contradictory options", () => {
  assert.match(
    validateRunLauncherForm(createRunLauncherForm({ input_mode: "startup_url" })).join(" "),
    /Startup URL is required/
  );
  assert.match(
    validateRunLauncherForm(createRunLauncherForm({ input_mode: "startup_url", startup_url: "not-a-url" })).join(
      " "
    ),
    /valid http or https URL/
  );
  assert.match(
    validateRunLauncherForm(
      createRunLauncherForm({
        input_mode: "query",
        query: "Brazilian AI startups",
        limit: 0,
        max_pages: 6,
        max_depth: 3,
        timeout_seconds: 2
      })
    ).join(" "),
    /Candidate limit.*Max pages.*Max depth.*Timeout seconds/
  );
  assert.match(
    validateRunLauncherForm(
      createRunLauncherForm({
        input_mode: "query",
        query: "Brazilian AI startups",
        retrieval_mode: "bm25",
        enable_reranking: true
      })
    ).join(" "),
    /Reranking requires pgvector retrieval/
  );
});

test("creates the safe default run payload for a startup URL", () => {
  const request = runRequestFromLauncherForm(
    createRunLauncherForm({
      input_mode: "startup_url",
      startup_url: "https://startup.ai/",
      startup_name: "Startup AI"
    })
  );

  assert.equal(request.startup_url, "https://startup.ai/");
  assert.equal(request.query, undefined);
  assert.equal(request.startup_name, "Startup AI");
  assert.equal(request.limit, 1);
  assert.equal(request.max_pages, 1);
  assert.equal(request.max_depth, 0);
  assert.equal(request.persistence_mode, "json");
  assert.equal(request.retrieval_mode, "bm25");
  assert.equal(request.orchestration, "local");
  assert.equal(request.render_js, false);
  assert.equal(request.enable_search_provider, false);
  assert.equal(request.enable_reranking, false);
  assert.equal(request.llm_narrative, false);
});

test("creates an advanced bounded-query payload that maps to the API contract", () => {
  const request = runRequestFromLauncherForm(
    createRunLauncherForm({
      input_mode: "query",
      query: "Brazilian AI-native startups in health",
      limit: 3,
      max_pages: 2,
      max_depth: 1,
      timeout_seconds: 20,
      persistence_mode: "json-postgres",
      retrieval_mode: "pgvector",
      orchestration: "langgraph",
      robots_policy: "permissive-on-error",
      render_js: true,
      enable_search_provider: true,
      enable_reranking: true,
      reranker_model: "cross-encoder/ms-marco-MiniLM-L-6-v2",
      llm_narrative: true
    })
  );

  assert.deepEqual(request, {
    startup_url: undefined,
    query: "Brazilian AI-native startups in health",
    startup_name: "unknown",
    limit: 3,
    max_pages: 2,
    max_depth: 1,
    timeout_seconds: 20,
    output_dir: "runs",
    persistence_mode: "json-postgres",
    nvidia_corpus_path: "tests/fixtures/nvidia_knowledge_official_fixture.json",
    render_js: true,
    robots_policy: "permissive-on-error",
    retrieval_mode: "pgvector",
    orchestration: "langgraph",
    enable_search_provider: true,
    enable_reranking: true,
    reranker_model: "cross-encoder/ms-marco-MiniLM-L-6-v2",
    llm_narrative: true
  });
});

test("submit validates without calling the API and preserves user input", async () => {
  let state = createInitialState();
  let apiCalled = false;

  await submitRunLauncher({
    formData: formData({
      input_mode: "startup_url",
      startup_url: "invalid-url"
    }),
    apiClient: {
      async startRun() {
        apiCalled = true;
        throw new Error("should_not_call_api");
      },
      async getRun() {
        throw new Error("not_used");
      },
      async getProductionSmokeMatrix() {
        throw new Error("not_used");
      }
    },
    commit: (updates) => {
      state = { ...state, ...updates };
    }
  });

  assert.equal(apiCalled, false);
  assert.match(state.errorMessage, /valid http or https URL/);
  assert.equal(state.launcherForm.startup_url, "invalid-url");
});

test("submit creates a run and routes back to the run workspace", async () => {
  let state = createInitialState({ activeSection: "assessment" });
  const commits = [];
  const calls = [];

  await submitRunLauncher({
    formData: formData({
      input_mode: "startup_url",
      startup_url: "https://startup.ai/",
      startup_name: "Startup AI",
      max_pages: "1",
      max_depth: "0"
    }),
    apiClient: {
      async startRun(request) {
        calls.push(request);
        return buildMockRunRecord(request, {
          runId: "mock-run-100",
          createdAt: "2026-06-30T15:00:00.000Z"
        });
      },
      async getRun() {
        throw new Error("not_used");
      },
      async getProductionSmokeMatrix() {
        throw new Error("not_used");
      }
    },
    commit: (updates) => {
      commits.push(updates);
      state = { ...state, ...updates };
    }
  });

  assert.equal(calls.length, 1);
  assert.equal(commits[0].isBusy, true);
  assert.equal(state.activeSection, "runs");
  assert.equal(state.currentRun.run_id, "mock-run-100");
  assert.match(state.notice, /mock-run-100/);
  assert.equal(state.launcherForm.startup_url, "https://startup.ai/");
});

test("submit preserves launcher input on API error", async () => {
  let state = createInitialState();

  await submitRunLauncher({
    formData: formData({
      input_mode: "query",
      query: "Brazilian AI startups",
      limit: "2"
    }),
    apiClient: {
      async startRun() {
        throw new Error("api_request_failed:provider_down");
      },
      async getRun() {
        throw new Error("not_used");
      },
      async getProductionSmokeMatrix() {
        throw new Error("not_used");
      }
    },
    commit: (updates) => {
      state = { ...state, ...updates };
    }
  });

  assert.equal(state.isBusy, false);
  assert.equal(state.errorMessage, "api_request_failed:provider_down");
  assert.equal(state.launcherForm.input_mode, "query");
  assert.equal(state.launcherForm.query, "Brazilian AI startups");
  assert.equal(state.launcherForm.limit, 2);
});

function formData(entries) {
  const data = new FormData();
  for (const [key, value] of Object.entries(entries)) {
    data.set(key, String(value));
  }
  return data;
}
