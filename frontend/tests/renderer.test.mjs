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
