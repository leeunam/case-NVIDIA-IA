import assert from "node:assert/strict";
import test from "node:test";

import { createInitialState, renderApp } from "../src/renderer.js";
import {
  buildMockCollectionFailureEvidenceRunRecord,
  buildMockConflictingEvidenceRunRecord,
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

test("renders executive briefing workspace with typed claims and source references", () => {
  const currentRun = withBriefingPayload(buildMockRunRecord(defaultRequest(), briefingMetadata()), {
    executive_briefing: briefingExecutiveBriefing(),
    briefing_narrative: briefingNarrative()
  });

  const html = renderApp(createInitialState({ activeSection: "briefing", currentRun }));

  assert.match(html, /Executive Briefing/);
  assert.match(html, /ready_for_use/);
  assert.match(html, /AI-native assessment classified NeuralMind as ai_native/);
  assert.match(html, /Opportunity/);
  assert.match(html, /urgent/);
  assert.match(html, /Recommendations/);
  assert.match(html, /NVIDIA NIM Microservices/);
  assert.match(html, /Pending questions/);
  assert.match(html, /What is the current funding stage/);
  assert.match(html, /claim-type-observed/);
  assert.match(html, /claim-type-inferred/);
  assert.match(html, /claim-type-recommended/);
  assert.match(html, /claim-type-unknown/);
  assert.match(html, /Evidence refs/);
  assert.match(html, /https:\/\/neuralmind.ai\/product/);
  assert.match(html, /Citation refs/);
  assert.match(html, /nvidia-nim-developers:0/);
  assert.match(html, /LLM narrative/);
  assert.match(html, /Provider/);
  assert.match(html, /litellm/);
  assert.doesNotMatch(html, /sk-test-secret/);
  assert.match(html, /data-copy-briefing/);
  assert.match(html, /data-download-briefing/);
  assert.match(html, /data-print-briefing/);
});

test("renders human review briefing workspace for unsafe final recommendation", () => {
  const currentRun = withBriefingPayload(buildMockRunRecord(defaultRequest(), briefingMetadata()), {
    workflow_outcome: "human_review_requested",
    next_action: "resolve_blocking_evidence",
    human_review_reasons: ["high_wrapper_risk_requires_human_review"],
    briefing_reference: {
      briefing_type: "human_review",
      artifact_kind: "briefing",
      startup_identifier: "NeuralMind"
    },
    human_review_briefing: briefingHumanReviewBriefing(),
    briefing_narrative: briefingNarrative({
      source_briefing_schema_version: "human_review_briefing.v1",
      source_briefing_status: "ready_for_human_review"
    })
  });

  const html = renderApp(createInitialState({ activeSection: "briefing", currentRun }));

  assert.match(html, /Human Review Briefing/);
  assert.match(html, /ready_for_human_review/);
  assert.match(html, /Area/);
  assert.match(html, /enterprise AI search/);
  assert.match(html, /Discoveries/);
  assert.match(html, /Suspected gaps/);
  assert.match(html, /model_serving/);
  assert.match(html, /Commercial opportunities/);
  assert.match(html, /inception_program_fit/);
  assert.match(html, /Wrapper risks/);
  assert.match(html, /external_api_dependency/);
  assert.match(html, /Conflicts/);
  assert.match(html, /sector/);
  assert.match(html, /Unknowns/);
  assert.match(html, /technologies_used/);
  assert.match(html, /Reasons for review/);
  assert.match(html, /high_wrapper_risk_requires_human_review/);
  assert.match(html, /Validation questions/);
  assert.match(html, /Validate dependency on external APIs/);
});

test("renders deterministic briefing when LLM narrative is missing", () => {
  const currentRun = withBriefingPayload(buildMockRunRecord(defaultRequest(), briefingMetadata()), {
    executive_briefing: briefingExecutiveBriefing(),
    briefing_narrative: null
  });

  const html = renderApp(createInitialState({ activeSection: "briefing", currentRun }));

  assert.match(html, /Deterministic briefing/);
  assert.match(html, /No LLM narrative is attached to this run/);
  assert.match(html, /AI-native assessment classified NeuralMind as ai_native/);
  assert.match(html, /NVIDIA NIM Microservices/);
});

test("renders unsafe LLM fallback without hiding deterministic briefing content", () => {
  const currentRun = withBriefingPayload(buildMockRunRecord(defaultRequest(), briefingMetadata()), {
    executive_briefing: briefingExecutiveBriefing(),
    briefing_narrative: briefingNarrative({
      technical_gap_narrative: "Deterministic fallback: use supported recommendation and cited evidence only.",
      commercial_approach_narrative: "Fallback keeps next_action prepare_technical_outreach visible.",
      narrative_text: "Deterministic fallback content.",
      audit_reasons: ["llm_narrative_rejected_unsupported_terms"],
      llm_response: {
        provider: "litellm",
        model: "groq/llama-3.1-8b-instant",
        model_version: "2026-06",
        finish_reason: "stop",
        metadata: {
          content_rejected: true,
          rejection_reason: "unsupported_terms",
          configured_api_key_env_var: "GROQ_API_KEY"
        },
        usage: {}
      }
    })
  });

  const html = renderApp(createInitialState({ activeSection: "briefing", currentRun }));

  assert.match(html, /LLM narrative fallback/);
  assert.match(html, /unsupported_terms/);
  assert.match(html, /Deterministic fallback/);
  assert.match(html, /AI-native assessment classified NeuralMind as ai_native/);
  assert.match(html, /GROQ_API_KEY/);
  assert.doesNotMatch(html, /sk-test-secret/);
});

test("renders long briefing content without dropping references", () => {
  const longText = Array.from({ length: 18 }, (_, index) => `validated claim segment ${index + 1}`).join(" ");
  const currentRun = withBriefingPayload(buildMockRunRecord(defaultRequest(), briefingMetadata()), {
    executive_briefing: briefingExecutiveBriefing({
      executive_summary: longText,
      diagnosis: `${longText} diagnosis`,
      claims: [
        ...briefingExecutiveBriefing().claims,
        {
          text: `${longText} with a deliberately long deterministic claim that should wrap inside the briefing workspace instead of forcing horizontal overflow.`,
          claim_type: "observed",
          section: "profile",
          confidence: 0.91,
          evidence_references: [briefingFieldEvidence("https://neuralmind.ai/deep-dive")],
          citation_references: []
        }
      ]
    })
  });

  const html = renderApp(createInitialState({ activeSection: "briefing", currentRun }));

  assert.match(html, /validated claim segment 18/);
  assert.match(html, /deep-dive/);
  assert.match(html, /briefing-export-text/);
  assert.match(html, /Evidence refs/);
});

test("renders ai-native assessment reasoning with evidence links", () => {
  const currentRun = withAssessmentPayload(buildMockRunRecord(defaultRequest(), defaultMetadata()), aiNativeAssessment(), {
    gap_space_assessment: gapSpaceAssessment()
  });

  const html = renderApp(createInitialState({ activeSection: "assessment", currentRun }));

  assert.match(html, /ai_native/);
  assert.match(html, /84%/);
  assert.match(html, /urgent/);
  assert.match(html, /ready_for_recommendation/);
  assert.match(html, /Criteria results/);
  assert.match(html, /ai_architecture_depth/);
  assert.match(html, /Passed/);
  assert.match(html, /Positive signals/);
  assert.match(html, /Technical gaps/);
  assert.match(html, /model_serving/);
  assert.match(html, /Commercial opportunities/);
  assert.match(html, /inception_program_fit/);
  assert.match(html, /data-section="evidence"/);
  assert.match(html, /source URL/);
});

test("renders ai-enabled assessment without overstating readiness", () => {
  const currentRun = withAssessmentPayload(buildMockRunRecord(defaultRequest(), defaultMetadata()), aiEnabledAssessment());

  const html = renderApp(createInitialState({ activeSection: "assessment", currentRun }));

  assert.match(html, /ai_enabled/);
  assert.match(html, /64%/);
  assert.match(html, /not_ready_for_recommendation/);
  assert.match(html, /ai_architecture_depth/);
  assert.match(html, /Failed/);
  assert.match(html, /classification_confidence_below_threshold/);
  assert.match(html, /Insufficient evidence fields/);
});

test("renders insufficient-evidence assessment review reasons and validation questions", () => {
  const currentRun = withAssessmentPayload(
    buildMockRunRecord(defaultRequest(), defaultMetadata()),
    insufficientEvidenceAssessment(),
    {
      human_review_briefing: humanReviewBriefing({
        reviewReasons: ["collection_quality_not_ready", "unknown_assessment_criteria"],
        pendingQuestions: [
          {
            field_name: "collection_quality",
            question: "Which public sources should be collected before recommendation can be trusted?",
            priority: "critical",
            reason: "collection_quality_requires_validation"
          }
        ]
      })
    }
  );

  const html = renderApp(createInitialState({ activeSection: "assessment", currentRun }));

  assert.match(html, /insufficient_evidence/);
  assert.match(html, /unknown_assessment_criteria/);
  assert.match(html, /collection_quality_not_ready/);
  assert.match(html, /Pending validation questions/);
  assert.match(html, /Which public sources should be collected/);
  assert.match(html, /collection_quality_requires_validation/);
});

test("renders high wrapper risk as a validation signal", () => {
  const currentRun = withAssessmentPayload(
    buildMockRunRecord(defaultRequest(), defaultMetadata()),
    highWrapperRiskAssessment(),
    {
      human_review_briefing: humanReviewBriefing({
        reviewReasons: ["high_wrapper_dependency_risk"],
        pendingQuestions: [
          {
            field_name: "external_api_only",
            question: "Validate dependency on external APIs, proprietary data, and production inference before prioritizing NVIDIA outreach.",
            priority: "critical",
            reason: "wrapper_risk_requires_validation"
          }
        ]
      })
    }
  );

  const html = renderApp(createInitialState({ activeSection: "assessment", currentRun }));

  assert.match(html, /external_api_only/);
  assert.match(html, /high/);
  assert.match(html, /Wrapper\/API-dependency signals/);
  assert.match(html, /Review signal/);
  assert.match(html, /validate before treating this as dependency risk/);
  assert.match(html, /wrapper_risk_requires_validation/);
});

test("renders assessment conflict reasons with evidence context", () => {
  const currentRun = withAssessmentPayload(buildMockConflictingEvidenceRunRecord(), conflictAssessment(), {
    human_review_briefing: humanReviewBriefing({
      reviewReasons: ["conflicting_startup_evidence"],
      pendingQuestions: [
        {
          field_name: "technologies_used",
          question: "Resolve conflicting public evidence for technologies_used.",
          priority: "critical",
          reason: "conflicting_evidence_requires_validation"
        }
      ]
    })
  });

  const html = renderApp(createInitialState({ activeSection: "assessment", currentRun }));

  assert.match(html, /Conflict/);
  assert.match(html, /conflicting_startup_evidence/);
  assert.match(html, /Resolve conflicting public evidence for technologies_used/);
  assert.match(html, /data-section="evidence"/);
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

test("renders all-skipped production smoke matrix with safe opt-in guidance", () => {
  const smokeMatrix = buildMockSmokeMatrix();
  const html = renderApp(createInitialState({ activeSection: "production-smokes", smokeMatrix }));

  assert.match(html, /Default local validation/);
  assert.match(html, /python -m pytest -q/);
  assert.match(html, /Opt-in real integrations/);
  assert.match(html, /do not paste credential values into this UI/);
  assert.match(html, /Integrations/);
  assert.match(html, /Skipped/);
  assert.match(html, /Playwright real collection/);
  assert.match(html, /Postgres persistence/);
  assert.match(html, /pgvector retrieval/);
  assert.match(html, /Real embedding model/);
  assert.match(html, /Hybrid BM25 plus pgvector retrieval/);
  assert.match(html, /Real reranking/);
  assert.match(html, /LangGraph Postgres checkpointing/);
  assert.match(html, /Groq\/LiteLLM briefing narrative/);
  assert.match(html, /Full bounded operational smoke/);
  assert.match(html, /NVIDIA_STARTUP_INTEL_RUN_PGVECTOR_SMOKE/);
  assert.match(html, /Expected artifacts/);
  assert.match(html, /Cleanup/);
  assert.match(html, /public startup URL or bounded query only/);
  assert.match(html, /do not commit generated artifacts/);
});

test("renders passed and failed production smokes with bottleneck diagnostics", () => {
  const smokeMatrix = productionSmokeMatrix(
    [
      smokeStep({
        integration_id: "playwright_collection",
        title: "Playwright real collection",
        status: "passed",
        bottleneck: "collection",
        message: "smoke passed",
        env_flag: "NVIDIA_STARTUP_INTEL_RUN_PLAYWRIGHT_COLLECTION_SMOKE",
        command:
          "NVIDIA_STARTUP_INTEL_RUN_PLAYWRIGHT_COLLECTION_SMOKE=1 python -m pytest -q tests/integration/test_playwright_collection_integration_smoke.py -m playwright_collection_integration",
        prerequisites: ["python -m playwright install chromium"],
        expected_artifacts: ["playwright_collection_smoke.v1 payload"],
        env_status: [
          {
            name: "NVIDIA_STARTUP_INTEL_RUN_PLAYWRIGHT_COLLECTION_SMOKE",
            role: "enable_flag",
            configured: true
          }
        ]
      }),
      smokeStep({
        integration_id: "pgvector_retrieval",
        title: "pgvector retrieval",
        status: "failed",
        bottleneck: "pgvector",
        message: "RuntimeError: pgvector extension is unavailable",
        env_flag: "NVIDIA_STARTUP_INTEL_RUN_PGVECTOR_SMOKE",
        command:
          "NVIDIA_STARTUP_INTEL_RUN_PGVECTOR_SMOKE=1 python -m pytest -q tests/integration/test_pgvector_integration_smoke.py -m pgvector_integration",
        prerequisites: ["docker compose up -d postgres"],
        expected_artifacts: ["persisted NVIDIA Knowledge chunks"],
        cleanup: ["docker compose down"],
        env_status: [
          {
            name: "NVIDIA_STARTUP_INTEL_RUN_PGVECTOR_SMOKE",
            role: "enable_flag",
            configured: true
          }
        ]
      })
    ],
    "failed"
  );
  const html = renderApp(createInitialState({ activeSection: "production-smokes", smokeMatrix }));

  assert.match(html, /passed/);
  assert.match(html, /failed/);
  assert.match(html, /collection/);
  assert.match(html, /pgvector/);
  assert.match(html, /RuntimeError: pgvector extension is unavailable/);
  assert.match(html, /Fix the pgvector bottleneck/);
  assert.match(html, /playwright_collection_smoke\.v1 payload/);
  assert.match(html, /docker compose down/);
});

test("renders missing production smoke env vars without requesting values", () => {
  const smokeMatrix = productionSmokeMatrix(
    [
      smokeStep({
        integration_id: "real_embeddings",
        title: "Real embedding model",
        status: "skipped",
        bottleneck: "embedding",
        message:
          "missing env vars: NVIDIA_STARTUP_INTEL_EMBEDDING_MODEL, NVIDIA_STARTUP_INTEL_EMBEDDING_MODEL_VERSION",
        env_flag: "NVIDIA_STARTUP_INTEL_RUN_REAL_EMBEDDING_SMOKE",
        command:
          "NVIDIA_STARTUP_INTEL_RUN_REAL_EMBEDDING_SMOKE=1 NVIDIA_STARTUP_INTEL_EMBEDDING_PROVIDER=sentence-transformers PYTHONPATH=src python -m nvidia_startup_intel.pgvector_smoke",
        required_env_vars: [
          "NVIDIA_STARTUP_INTEL_EMBEDDING_PROVIDER",
          "NVIDIA_STARTUP_INTEL_EMBEDDING_MODEL",
          "NVIDIA_STARTUP_INTEL_EMBEDDING_MODEL_VERSION"
        ],
        env_status: [
          {
            name: "NVIDIA_STARTUP_INTEL_RUN_REAL_EMBEDDING_SMOKE",
            role: "enable_flag",
            configured: true
          },
          {
            name: "NVIDIA_STARTUP_INTEL_EMBEDDING_PROVIDER",
            role: "required",
            configured: true
          },
          {
            name: "NVIDIA_STARTUP_INTEL_EMBEDDING_MODEL",
            role: "required",
            configured: false
          },
          {
            name: "NVIDIA_STARTUP_INTEL_EMBEDDING_MODEL_VERSION",
            role: "required",
            configured: false
          }
        ]
      })
    ],
    "skipped"
  );
  const html = renderApp(createInitialState({ activeSection: "production-smokes", smokeMatrix }));

  assert.match(html, /NVIDIA_STARTUP_INTEL_EMBEDDING_PROVIDER/);
  assert.match(html, /NVIDIA_STARTUP_INTEL_EMBEDDING_MODEL_VERSION/);
  assert.match(html, /enable flag: configured/);
  assert.match(html, /required: configured/);
  assert.match(html, /required: missing/);
  assert.match(html, /Missing environment variables/);
  assert.match(html, /without exposing their values here/);
  assert.doesNotMatch(html, /api[_-]?key=.*secret/i);
});

test("renders credential hygiene warnings without echoing sensitive payload values", () => {
  const secret = "secret-token-from-env";
  const smokeMatrix = productionSmokeMatrix(
    [
      smokeStep({
        integration_id: "groq_litellm_narrative",
        title: "Groq/LiteLLM briefing narrative",
        status: "failed",
        bottleneck: "credential_hygiene",
        message: "credential leak detected in smoke payload or generated artifact",
        env_flag: "NVIDIA_STARTUP_INTEL_RUN_LLM_ADAPTER_SMOKE",
        required_env_vars: [
          "NVIDIA_STARTUP_INTEL_LLM_PROVIDER",
          "NVIDIA_STARTUP_INTEL_LLM_MODEL",
          "NVIDIA_STARTUP_INTEL_LLM_API_KEY_ENV"
        ],
        env_status: [
          {
            name: "NVIDIA_STARTUP_INTEL_RUN_LLM_ADAPTER_SMOKE",
            role: "enable_flag",
            configured: true
          },
          {
            name: "NVIDIA_STARTUP_INTEL_LLM_API_KEY_ENV",
            role: "required",
            configured: true
          }
        ],
        payload: {
          metadata: {
            api_key: secret,
            sanitized_api_key: "[REDACTED]",
            configured_api_key_env_var: "GROQ_API_KEY"
          }
        }
      })
    ],
    "failed"
  );
  const html = renderApp(createInitialState({ activeSection: "production-smokes", smokeMatrix }));

  assert.match(html, /credential leak detected/);
  assert.match(html, /Credential hygiene failed/);
  assert.match(html, /Payload values are not displayed/);
  assert.match(html, /metadata\.api_key/);
  assert.match(html, /metadata\.sanitized_api_key/);
  assert.match(html, /Redacted credential fields/);
  assert.match(html, /NVIDIA_STARTUP_INTEL_LLM_API_KEY_ENV/);
  assert.doesNotMatch(html, new RegExp(secret));
});

function productionSmokeMatrix(steps, overallStatus) {
  return {
    schema_version: "frontend_api_production_smoke_matrix.v1",
    read_only: true,
    matrix: {
      schema_version: "production_smoke_matrix.v1",
      overall_status: overallStatus,
      steps
    }
  };
}

function smokeStep(overrides = {}) {
  const envFlag = overrides.env_flag || "NVIDIA_STARTUP_INTEL_RUN_TEST_SMOKE";
  return {
    integration_id: "test_smoke",
    title: "Test smoke",
    status: "skipped",
    bottleneck: "test",
    message: `set ${envFlag}=1 to enable`,
    env_flag: envFlag,
    command: `${envFlag}=1 python -m pytest -q tests/integration/test_smoke.py`,
    prerequisites: [],
    required_env_vars: [],
    env_status: [
      {
        name: envFlag,
        role: "enable_flag",
        configured: false
      }
    ],
    expected_artifacts: [],
    cleanup: [],
    payload: {},
    ...overrides
  };
}

function briefingMetadata() {
  return {
    runId: "mock-run-105",
    createdAt: "2026-06-30T15:00:00.000Z"
  };
}

function withBriefingPayload(record, extraPayload) {
  const finalPayload = {
    ...record.final_payload,
    ...extraPayload
  };
  return {
    ...record,
    workflow_outcome: String(extraPayload.workflow_outcome || finalPayload.workflow_outcome),
    next_action: String(extraPayload.next_action || finalPayload.next_action),
    briefing_reference: extraPayload.briefing_reference || finalPayload.briefing_reference,
    human_review_reasons: Array.isArray(extraPayload.human_review_reasons)
      ? extraPayload.human_review_reasons
      : record.human_review_reasons,
    final_payload: finalPayload
  };
}

function briefingExecutiveBriefing(overrides = {}) {
  const evidence = [briefingFieldEvidence("https://neuralmind.ai/product")];
  const citation = [briefingNvidiaCitation()];
  return {
    schema_version: "executive_briefing.v1",
    run_id: "mock-run-105",
    startup_identifier: "NeuralMind",
    status: "ready_for_use",
    executive_summary:
      "NeuralMind is classified as ai_native and has a supported NVIDIA recommendation for model serving.",
    diagnosis: "AI-native assessment classified NeuralMind as ai_native with confidence 0.84.",
    opportunity: "urgent",
    risks: ["external_api_dependency: no evidence that APIs are the only AI dependency."],
    recommendations: ["Recommend NVIDIA NIM Microservices for model_serving."],
    pending_questions: [
      {
        field_name: "funding",
        question: "What is the current funding stage?",
        priority: "complementary",
        reason: "missing_startup_profile_field"
      }
    ],
    claims: [
      {
        text: "company_name: NeuralMind",
        claim_type: "observed",
        section: "profile",
        confidence: 1,
        evidence_references: evidence,
        citation_references: []
      },
      {
        text: "AI-native assessment classified NeuralMind as ai_native with confidence 0.84.",
        claim_type: "inferred",
        section: "diagnosis",
        confidence: 0.84,
        evidence_references: evidence,
        citation_references: []
      },
      {
        text: "Recommend NVIDIA NIM Microservices for model_serving.",
        claim_type: "recommended",
        section: "recommendations",
        confidence: 0.8,
        evidence_references: evidence,
        citation_references: citation,
        reason: "supported_technical_recommendation"
      },
      {
        text: "funding is unknown from collected public evidence.",
        claim_type: "unknown",
        section: "unknowns",
        confidence: 0,
        evidence_references: [],
        citation_references: [],
        reason: "missing_startup_profile_field"
      }
    ],
    evidence_references: evidence,
    citation_references: citation,
    next_action: "prepare_technical_outreach",
    audit_reasons: ["collection_quality_ready"],
    ...overrides
  };
}

function briefingHumanReviewBriefing(overrides = {}) {
  const evidence = [briefingFieldEvidence("https://neuralmind.ai/product")];
  const citation = [briefingNvidiaCitation()];
  return {
    schema_version: "human_review_briefing.v1",
    run_id: "mock-run-105",
    startup_identifier: "NeuralMind",
    status: "ready_for_human_review",
    area_of_operation: "enterprise AI search",
    discoveries: [
      {
        text: "product: enterprise AI search assistant",
        claim_type: "observed",
        section: "profile",
        confidence: 1,
        evidence_references: evidence,
        citation_references: []
      }
    ],
    main_evidence: evidence,
    suspected_gaps: [
      {
        gap_type: "model_serving",
        description: "Latency and cost need validation before NVIDIA recommendation.",
        severity: "high",
        confidence: 0.72,
        evidences: evidence
      }
    ],
    commercial_opportunities: [
      {
        opportunity_type: "inception_program_fit",
        nvidia_program: "NVIDIA Inception Program for Startups",
        commercial_rationale: "Program fit is plausible but needs validation.",
        startup_evidences: evidence,
        nvidia_citations: citation
      }
    ],
    wrapper_risks: [
      {
        risk_type: "external_api_dependency",
        severity: "high",
        confidence: 0.77,
        rationale: "Public evidence does not prove proprietary model or production inference ownership.",
        evidences: evidence
      }
    ],
    conflicts: [
      {
        field_name: "sector",
        value: "enterprise search",
        has_conflict: true,
        conflicting_values: ["legaltech", "enterprise AI search"],
        evidences: evidence
      }
    ],
    unknowns: ["technologies_used", "funding"],
    supported_recommendations: [],
    hypothesis_recommendations: [],
    blocked_recommendations: [
      {
        recommendation_type: "technical",
        nvidia_technology: "NVIDIA NIM Microservices",
        technical_rationale: "Missing startup-side evidence blocks final recommendation.",
        startup_evidences: [],
        nvidia_citations: citation
      }
    ],
    review_reasons: ["high_wrapper_risk_requires_human_review"],
    pending_questions: [
      {
        field_name: "external_api_dependency",
        question: "Validate dependency on external APIs, proprietary data, and production inference before prioritizing NVIDIA outreach.",
        priority: "critical",
        reason: "wrapper_risk_requires_validation"
      }
    ],
    evidence_references: evidence,
    citation_references: citation,
    next_action: "resolve_blocking_evidence",
    audit_reasons: ["high_wrapper_risk_requires_human_review"],
    ...overrides
  };
}

function briefingNarrative(overrides = {}) {
  return {
    schema_version: "briefing_narrative.v1",
    run_id: "mock-run-105",
    startup_identifier: "NeuralMind",
    source_briefing_schema_version: "executive_briefing.v1",
    source_briefing_status: "ready_for_use",
    technical_gap_narrative:
      "Use the deterministic model_serving gap and cited NVIDIA NIM Microservices reference as the technical anchor.",
    commercial_approach_narrative:
      "Lead with prepare_technical_outreach and keep funding as an explicit pending question.",
    narrative_text: "technical_gap_narrative: Use model_serving. commercial_approach_narrative: Prepare outreach.",
    claims: briefingExecutiveBriefing().claims,
    unknowns: ["funding is unknown from collected public evidence."],
    risks: ["external_api_dependency: no evidence that APIs are the only AI dependency."],
    review_reasons: [],
    pending_questions: briefingExecutiveBriefing().pending_questions,
    evidence_references: briefingExecutiveBriefing().evidence_references,
    citation_references: briefingExecutiveBriefing().citation_references,
    next_action: "prepare_technical_outreach",
    llm_request: {
      purpose: "briefing_narrative",
      structured_output_schema: "briefing_narrative.v1",
      metadata: {
        run_id: "mock-run-105",
        source_briefing_schema_version: "executive_briefing.v1"
      }
    },
    llm_response: {
      provider: "litellm",
      model: "groq/llama-3.1-8b-instant",
      model_version: "2026-06",
      finish_reason: "stop",
      metadata: {
        adapter: "litellm",
        configured_api_key_env_var: "GROQ_API_KEY",
        api_base_configured: false,
        ignored_secret_example: "sk-test-secret"
      },
      usage: {
        prompt_tokens: 120,
        completion_tokens: 80
      }
    },
    audit_reasons: ["llm_narrative_generated_from_validated_briefing", "llm_narrative_accepted"],
    ...overrides
  };
}

function briefingFieldEvidence(url) {
  return {
    url,
    source_type: "public_page",
    snippet: "Public evidence mentions model serving, latency, and proprietary AI signals."
  };
}

function briefingNvidiaCitation() {
  return {
    document_id: "nvidia-nim-developers",
    chunk_id: "nvidia-nim-developers:0",
    document_title: "NVIDIA NIM for Developers",
    source_url: "https://developer.nvidia.com/nim"
  };
}

function defaultRequest() {
  return {
    startup_url: "https://neuralmind.ai/",
    startup_name: "NeuralMind"
  };
}

function defaultMetadata() {
  return {
    runId: "mock-run-assessment",
    createdAt: "2026-06-30T15:00:00.000Z"
  };
}

function withAssessmentPayload(record, assessment, extraPayload = {}) {
  const reviewReasons = reviewReasonsFromPayload(assessment, extraPayload);
  return {
    ...record,
    workflow_outcome: reviewReasons.length ? "human_review_requested" : record.workflow_outcome,
    next_action: reviewReasons.length ? "validate_assessment_with_human" : record.next_action,
    human_review_reasons: reviewReasons,
    final_payload: {
      ...record.final_payload,
      workflow_outcome: reviewReasons.length ? "human_review_requested" : record.final_payload.workflow_outcome,
      next_action: reviewReasons.length ? "validate_assessment_with_human" : record.final_payload.next_action,
      human_review_reasons: reviewReasons,
      ai_native_assessment: assessment,
      ...extraPayload
    }
  };
}

function reviewReasonsFromPayload(assessment, extraPayload) {
  return Array.from(
    new Set([
      ...arrayValues(assessment?.diagnostic_quality?.reasons),
      ...arrayValues(extraPayload?.human_review_briefing?.review_reasons)
    ])
  ).filter((reason) => reason && reason !== "ready_for_recommendation");
}

function aiNativeAssessment() {
  const evidences = [assessmentEvidence("https://neuralmind.ai/"), assessmentEvidence("https://neuralmind.ai/product")];
  return {
    schema_version: "ai_native_assessment.v1",
    run_id: "mock-run-assessment",
    company_name: "NeuralMind",
    classification: "ai_native",
    confidence: 0.84,
    nvidia_opportunity_urgency: "urgent",
    criteria_results: [
      criterion("ai_product_centrality", "positive", evidences),
      criterion("ai_architecture_depth", "positive", evidences),
      criterion("proprietary_data_loop", "positive", evidences),
      criterion("production_readiness", "positive", evidences),
      criterion("scale_governance_need", "negative", [])
    ],
    positive_signals: [
      {
        signal_type: "ai_architecture_depth",
        description: "Evidence mentions proprietary models, MLOps, and inference architecture.",
        confidence: 0.8,
        evidences
      }
    ],
    technical_gaps: [
      {
        gap_type: "model_serving",
        description: "Potential need around model serving, latency, cost, or production inference.",
        severity: "high",
        confidence: 0.72,
        evidences,
        is_hypothesis: false
      }
    ],
    wrapper_dependency_risks: [
      {
        risk_type: "external_api_only",
        severity: "low",
        confidence: 0.62,
        rationale: "No evidence that external APIs are the only AI dependency.",
        evidences: [],
        is_hypothesis: true
      }
    ],
    insufficient_evidence_fields: [],
    evidences,
    diagnostic_quality: {
      ready_for_recommendation: true,
      requires_human_review: false,
      reasons: ["ready_for_recommendation"]
    },
    ready_for_recommendation: true
  };
}

function aiEnabledAssessment() {
  const evidences = [assessmentEvidence("https://enabled.ai/")];
  return {
    ...aiNativeAssessment(),
    classification: "ai_enabled",
    confidence: 0.64,
    nvidia_opportunity_urgency: "medium",
    criteria_results: [
      criterion("ai_product_centrality", "positive", evidences),
      criterion("ai_architecture_depth", "negative", []),
      criterion("proprietary_data_loop", "negative", []),
      criterion("production_readiness", "unknown", [])
    ],
    positive_signals: [
      {
        signal_type: "ai_product_centrality",
        description: "AI appears central to product positioning.",
        confidence: 0.8,
        evidences
      }
    ],
    technical_gaps: [
      {
        gap_type: "llm_customization",
        description: "Potential need around LLM customization, tuning, evaluation, or domain adaptation.",
        severity: "medium",
        confidence: 0.62,
        evidences,
        is_hypothesis: true
      }
    ],
    insufficient_evidence_fields: ["technologies_used"],
    diagnostic_quality: {
      ready_for_recommendation: false,
      requires_human_review: false,
      reasons: ["classification_confidence_below_threshold", "unknown_assessment_criteria"]
    },
    ready_for_recommendation: false
  };
}

function insufficientEvidenceAssessment() {
  return {
    ...aiNativeAssessment(),
    classification: "insufficient_evidence",
    confidence: 0,
    nvidia_opportunity_urgency: "human_review",
    criteria_results: [
      {
        criterion: "evidence_quality",
        status: "unknown",
        confidence: 0,
        rationale: "Collection quality is not ready for AI-native evaluation.",
        evidences: []
      }
    ],
    positive_signals: [],
    technical_gaps: [
      {
        gap_type: "unknown",
        description: "No specific technical gap can be supported by current evidence.",
        severity: "unknown",
        confidence: 0,
        evidences: [],
        is_hypothesis: true
      }
    ],
    wrapper_dependency_risks: [
      {
        risk_type: "unknown",
        severity: "unknown",
        confidence: 0,
        rationale: "No AI dependency risk can be assessed from current evidence.",
        evidences: [],
        is_hypothesis: true
      }
    ],
    insufficient_evidence_fields: ["collection_quality", "ai_signals"],
    evidences: [],
    diagnostic_quality: {
      ready_for_recommendation: false,
      requires_human_review: true,
      reasons: ["collection_quality_not_ready", "unknown_assessment_criteria"]
    },
    ready_for_recommendation: false
  };
}

function highWrapperRiskAssessment() {
  const evidences = [
    assessmentEvidence("https://api-wrapper.ai/", "Produto usa OpenAI API e ChatGPT sem dados proprietarios observados.")
  ];
  return {
    ...aiEnabledAssessment(),
    classification: "ai_enabled",
    confidence: 0.58,
    nvidia_opportunity_urgency: "human_review",
    wrapper_dependency_risks: [
      {
        risk_type: "external_api_only",
        severity: "high",
        confidence: 0.82,
        rationale: "Evidence points to external LLM/API dependency without deeper stack signals.",
        evidences,
        is_hypothesis: false
      }
    ],
    diagnostic_quality: {
      ready_for_recommendation: false,
      requires_human_review: true,
      reasons: ["classification_confidence_below_threshold", "high_wrapper_dependency_risk"]
    },
    ready_for_recommendation: false
  };
}

function conflictAssessment() {
  const evidences = [
    assessmentEvidence("https://conflict-startup.ai/product", "Tecnologias: MLOps e model serving."),
    assessmentEvidence("https://directory.example/conflict-startup", "Diretorio indica somente chatbot generico.")
  ];
  return {
    ...aiNativeAssessment(),
    classification: "ai_enabled",
    confidence: 0.52,
    nvidia_opportunity_urgency: "human_review",
    criteria_results: [
      criterion("ai_product_centrality", "positive", evidences),
      criterion("ai_architecture_depth", "conflict", evidences)
    ],
    insufficient_evidence_fields: ["conflicting_technologies_used"],
    diagnostic_quality: {
      ready_for_recommendation: false,
      requires_human_review: true,
      reasons: ["conflicting_startup_evidence", "classification_confidence_below_threshold"]
    },
    ready_for_recommendation: false
  };
}

function gapSpaceAssessment() {
  const evidences = [assessmentEvidence("https://neuralmind.ai/product")];
  return {
    schema_version: "gap_space_assessment.v1",
    commercial_opportunities: [
      {
        opportunity_type: "inception_program_fit",
        description: "Potential startup program support, technical enablement, or go-to-market opportunity.",
        confidence: 0.78,
        evidences,
        is_hypothesis: false
      }
    ],
    quality: {
      ready_for_recommendation: true,
      requires_human_review: false,
      reasons: ["gap_space_ready_for_recommendation"],
      human_review_reasons: []
    }
  };
}

function humanReviewBriefing({ reviewReasons, pendingQuestions }) {
  return {
    schema_version: "human_review_briefing.v1",
    review_reasons: reviewReasons,
    pending_questions: pendingQuestions
  };
}

function criterion(name, status, evidences) {
  return {
    criterion: name,
    status,
    confidence: status === "positive" ? 0.8 : status === "conflict" ? 0.4 : 0.55,
    rationale: `${name} ${status}`,
    evidences
  };
}

function assessmentEvidence(url, snippet = "Tecnologias: MLOps, dados proprietarios, feedback loop e model serving.") {
  return {
    url,
    title: "Assessment source",
    snippet,
    source_type: "collected_page",
    collected_at: "2026-06-30T15:00:00.000Z"
  };
}

function arrayValues(value) {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];
}
