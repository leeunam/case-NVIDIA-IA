import assert from "node:assert/strict";
import test from "node:test";

import { createInitialState, renderApp } from "../src/renderer.js";
import { buildMockRunRecord, buildMockSmokeMatrix } from "../src/mock-data.js";

test("renders the operational shell and first-viewport workbench", () => {
  const html = renderApp(createInitialState());

  assert.match(html, /Runs/);
  assert.match(html, /Evidence/);
  assert.match(html, /Assessment/);
  assert.match(html, /NVIDIA Match/);
  assert.match(html, /Briefing/);
  assert.match(html, /Production Smokes/);
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
  assert.match(runsHtml, /prepare_technical_outreach/);
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

test("renders production smoke matrix from API contract", () => {
  const smokeMatrix = buildMockSmokeMatrix(["postgres_persistence"]);
  const html = renderApp(createInitialState({ activeSection: "production-smokes", smokeMatrix }));

  assert.match(html, /Postgres persistence/);
  assert.match(html, /skipped/);
  assert.match(html, /postgres/);
});
