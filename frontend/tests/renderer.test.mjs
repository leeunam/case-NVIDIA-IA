import assert from "node:assert/strict";
import test from "node:test";

import { createInitialState, renderApp } from "../src/renderer.js";
import {
  buildMockFailedRunRecord,
  buildMockHumanReviewRunRecord,
  buildMockRunRecord,
  buildMockSmokeMatrix
} from "../src/mock-data.js";

test("renders the operational shell and first-viewport workbench", () => {
  const html = renderApp(createInitialState());

  assert.match(html, /Runs/);
  assert.match(html, /Evidence/);
  assert.match(html, /Assessment/);
  assert.match(html, /NVIDIA Match/);
  assert.match(html, /Briefing/);
  assert.match(html, /Production Smokes/);
  assert.match(html, /role="tablist"/);
  assert.match(html, /Start intelligence run/);
  assert.match(html, /No active run/);
  assert.doesNotMatch(html, /hero/i);
});

test("renders the run launcher with preserved query state and production markers", () => {
  const html = renderApp(
    createInitialState({
      launcherForm: {
        input_mode: "query",
        query: "Brazilian AI-native startups in health",
        limit: 3,
        retrieval_mode: "pgvector",
        enable_reranking: true,
        reranker_model: "cross-encoder"
      }
    })
  );

  assert.match(html, /value="query" type="radio" data-launcher-autosync checked/);
  assert.match(html, /Brazilian AI-native startups in health/);
  assert.match(html, /pgvector production/);
  assert.match(html, /Groq narrative/);
  assert.match(html, /local defaults/);
  assert.match(html, /cross-encoder/);
});

test("renders run-driven status, evidence, assessment, NVIDIA match, and briefing states", () => {
  const currentRun = buildMockRunRecord(
    {
      startup_url: "https://neuralmind.ai/",
      startup_name: "NeuralMind"
    },
    {
      runId: "mock-run-099",
      createdAt: "2026-06-30T15:00:00.000Z"
    }
  );

  const runsHtml = renderApp(createInitialState({ currentRun }));
  assert.match(runsHtml, /mock-run-099/);
  assert.match(runsHtml, /Workflow outcome/);
  assert.match(runsHtml, /executive briefing/);
  assert.match(runsHtml, /prepare_technical_outreach/);
  assert.match(runsHtml, /Branch decisions/);
  assert.match(runsHtml, /ready_for_briefing/);
  assert.match(runsHtml, /Persistence references/);
  assert.match(runsHtml, /available/);

  const evidenceHtml = renderApp(createInitialState({ activeSection: "evidence", currentRun }));
  assert.match(evidenceHtml, /Artifact locations/);
  assert.match(evidenceHtml, /runs\/mock-run-099/);

  const assessmentHtml = renderApp(createInitialState({ activeSection: "assessment", currentRun }));
  assert.match(assessmentHtml, /Classification/);
  assert.match(assessmentHtml, /model_serving/);

  const matchHtml = renderApp(createInitialState({ activeSection: "nvidia-match", currentRun }));
  assert.match(matchHtml, /Supported recommendations/);
  assert.match(matchHtml, /Evaluate NVIDIA inference stack/);

  const briefingHtml = renderApp(createInitialState({ activeSection: "briefing", currentRun }));
  assert.match(briefingHtml, /Workflow outcome/);
  assert.match(briefingHtml, /executive/);
});

test("renders human review run payload with branch decision and review action", () => {
  const currentRun = buildMockHumanReviewRunRecord();
  const html = renderApp(createInitialState({ currentRun }));

  assert.match(html, /human_review_requested/);
  assert.match(html, /human review/);
  assert.match(html, /validate_nvidia_fit_with_human/);
  assert.match(html, /recommendation_hypothesis_requires_human_review/);
  assert.match(html, /Branch decisions/);
});

test("renders failed run payload as auditable workflow data", () => {
  const currentRun = buildMockFailedRunRecord();
  const html = renderApp(createInitialState({ currentRun }));

  assert.match(html, /failed_with_auditable_error/);
  assert.match(html, /review_workflow_errors/);
  assert.match(html, /Auditable errors/);
  assert.match(html, /execute_search/);
  assert.match(html, /TimeoutError/);
  assert.match(html, /search provider timeout/);
  assert.match(html, /search_adapter_failed_structured_error/);
});

test("renders loading and not-found route states without a current run", () => {
  const loadingHtml = renderApp(
    createInitialState({
      routeRunId: "op-20260630T120000Z",
      runLoadState: "loading"
    })
  );
  assert.match(loadingHtml, /Loading run context/);
  assert.match(loadingHtml, /without starting a new run/);

  const missingHtml = renderApp(
    createInitialState({
      routeRunId: "missing-run",
      runLoadState: "not_found"
    })
  );
  assert.match(missingHtml, /Run not found/);
  assert.match(missingHtml, /missing-run/);
});

test("renders production smoke matrix from API contract", () => {
  const smokeMatrix = buildMockSmokeMatrix(["postgres_persistence"]);
  const html = renderApp(createInitialState({ activeSection: "production-smokes", smokeMatrix }));

  assert.match(html, /Postgres persistence/);
  assert.match(html, /skipped/);
  assert.match(html, /postgres/);
});
