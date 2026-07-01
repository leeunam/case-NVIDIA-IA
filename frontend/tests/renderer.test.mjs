import assert from "node:assert/strict";
import test from "node:test";

import { createInitialState, renderApp } from "../src/renderer.js";
import {
  buildMockCollectionFailureEvidenceRunRecord,
  buildMockConflictingEvidenceRunRecord,
  buildMockFailedRunRecord,
  buildMockHumanReviewRunRecord,
  buildMockPartialRunRecord,
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
  assert.match(evidenceHtml, /Startup-side Evidence/);
  assert.match(evidenceHtml, /NVIDIA-side Citation/);
  assert.match(evidenceHtml, /company_summary/);
  assert.match(evidenceHtml, /Plataforma AI-native para documentos/);
  assert.match(evidenceHtml, /trafilatura\+beautifulsoup\+playwright/);
  assert.match(evidenceHtml, /needs_js_rendering/);
  assert.match(evidenceHtml, /ready_for_ai_native_evaluation/);

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

test("renders run history list with metadata, artifact availability, and reopen controls", () => {
  const currentRun = buildMockRunRecord(
    {
      startup_url: "https://neuralmind.ai/",
      startup_name: "NeuralMind"
    },
    {
      runId: "mock-history-current",
      createdAt: "2026-06-30T15:00:00.000Z"
    }
  );
  const runHistory = [
    currentRun,
    buildMockHumanReviewRunRecord({ runId: "mock-history-review" }),
    buildMockFailedRunRecord({ runId: "mock-history-failed" })
  ];

  const html = renderApp(
    createInitialState({
      currentRun,
      runHistory,
      runHistoryLoadState: "loaded",
      runHistoryMetadata: {
        generated_at: "2026-06-30T15:30:00.000Z",
        persistence_mode: "mock-fixtures"
      }
    })
  );

  assert.match(html, /Run history/);
  assert.match(html, /mock-fixtures/);
  assert.match(html, /mock-history-current/);
  assert.match(html, /NeuralMind/);
  assert.match(html, /neuralmind\.ai/);
  assert.match(html, /briefing available/);
  assert.match(html, /human review briefing available/);
  assert.match(html, /data-open-run="mock-history-review"/);
  assert.match(html, /mock-history-failed/);
  assert.match(html, /failed steps/);
});

test("filters run history in the Runs view", () => {
  const html = renderApp(
    createInitialState({
      runHistory: [
        buildMockRunRecord(
          {
            startup_url: "https://neuralmind.ai/",
            startup_name: "NeuralMind"
          },
          {
            runId: "mock-history-completed",
            createdAt: "2026-06-30T15:00:00.000Z"
          }
        ),
        buildMockHumanReviewRunRecord({
          runId: "mock-history-review",
          createdAt: "2026-06-29T10:00:00.000Z"
        })
      ],
      runHistoryLoadState: "loaded",
      runHistoryFilters: {
        search: "review-startup.ai",
        workflow_outcome: "human_review_requested",
        next_action: "validate_nvidia_fit_with_human",
        human_review_reason: "recommendation_hypothesis_requires_human_review",
        date: "2026-06-29"
      }
    })
  );

  assert.match(html, /mock-history-review/);
  assert.match(html, /review-startup\.ai/);
  assert.doesNotMatch(html, /mock-history-completed/);
});

test("renders partial run payloads without treating missing artifacts as success", () => {
  const partialRun = buildMockPartialRunRecord({
    runId: "mock-history-partial",
    createdAt: "2026-06-30T14:00:00.000Z"
  });
  const html = renderApp(
    createInitialState({
      runHistory: [partialRun],
      runHistoryLoadState: "loaded"
    })
  );

  assert.match(html, /mock-history-partial/);
  assert.match(html, /ready_for_ai_native_assessment/);
  assert.match(html, /assessment missing/);
  assert.match(html, /nvidia_match/);
  assert.match(html, /briefing missing/);
  assert.match(html, /collect_missing_artifacts/);
  assert.doesNotMatch(html, /briefing available/);
});

test("renders run history empty, loading, and failed states", () => {
  const loadingHtml = renderApp(createInitialState({ runHistoryLoadState: "loading" }));
  assert.match(loadingHtml, /Loading run history/);

  const emptyHtml = renderApp(createInitialState({ runHistoryLoadState: "empty", runHistory: [] }));
  assert.match(emptyHtml, /No previous runs found/);

  const failedHtml = renderApp(
    createInitialState({
      runHistoryLoadState: "failed",
      errorMessage: "api_request_failed:history_down"
    })
  );
  assert.match(failedHtml, /Run history could not be loaded/);
  assert.match(failedHtml, /api_request_failed:history_down/);
});

test("renders evidence conflicts, unknown fields, and insufficient evidence reasons", () => {
  const currentRun = buildMockConflictingEvidenceRunRecord();
  const html = renderApp(createInitialState({ activeSection: "evidence", currentRun }));

  assert.match(html, /Conflict/);
  assert.match(html, /conflicting_startup_evidence/);
  assert.match(html, /healthtech/);
  assert.match(html, /fintech/);
  assert.match(html, /Unknown fields/);
  assert.match(html, /funding/);
  assert.match(html, /missing_field_evidence:funding/);
  assert.match(html, /source URL/);
});

test("renders collection failure payloads with robots and policy decisions", () => {
  const currentRun = buildMockCollectionFailureEvidenceRunRecord();
  const html = renderApp(createInitialState({ activeSection: "evidence", currentRun }));

  assert.match(html, /Collection errors/);
  assert.match(html, /RobotsPolicyDisallowed/);
  assert.match(html, /robots_disallowed/);
  assert.match(html, /browser render timed out/);
  assert.match(html, /Robots and policy decisions/);
  assert.match(html, /minimum_profile_coverage_below_threshold/);
  assert.match(html, /average_evidence_below_threshold/);
  assert.match(html, /Empty\/low-text pages/);
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
