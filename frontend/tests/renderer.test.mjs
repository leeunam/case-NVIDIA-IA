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

test("renders executive briefing workspace with typed claims and source references", () => {
  const currentRun = withBriefingPayload(buildMockRunRecord(defaultRequest(), defaultMetadata()), {
    executive_briefing: executiveBriefing(),
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
  const currentRun = withBriefingPayload(buildMockRunRecord(defaultRequest(), defaultMetadata()), {
    workflow_outcome: "human_review_requested",
    next_action: "resolve_blocking_evidence",
    human_review_reasons: ["high_wrapper_risk_requires_human_review"],
    briefing_reference: {
      briefing_type: "human_review",
      artifact_kind: "briefing",
      startup_identifier: "NeuralMind"
    },
    human_review_briefing: humanReviewBriefing(),
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
  const currentRun = withBriefingPayload(buildMockRunRecord(defaultRequest(), defaultMetadata()), {
    executive_briefing: executiveBriefing(),
    briefing_narrative: null
  });

  const html = renderApp(createInitialState({ activeSection: "briefing", currentRun }));

  assert.match(html, /Deterministic briefing/);
  assert.match(html, /No LLM narrative is attached to this run/);
  assert.match(html, /AI-native assessment classified NeuralMind as ai_native/);
  assert.match(html, /NVIDIA NIM Microservices/);
});

test("renders unsafe LLM fallback without hiding deterministic briefing content", () => {
  const currentRun = withBriefingPayload(buildMockRunRecord(defaultRequest(), defaultMetadata()), {
    executive_briefing: executiveBriefing(),
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
  const currentRun = withBriefingPayload(buildMockRunRecord(defaultRequest(), defaultMetadata()), {
    executive_briefing: executiveBriefing({
      executive_summary: longText,
      diagnosis: `${longText} diagnosis`,
      claims: [
        ...executiveBriefing().claims,
        {
          text: `${longText} with a deliberately long deterministic claim that should wrap inside the briefing workspace instead of forcing horizontal overflow.`,
          claim_type: "observed",
          section: "profile",
          confidence: 0.91,
          evidence_references: [fieldEvidence("https://neuralmind.ai/deep-dive")],
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

function executiveBriefing(overrides = {}) {
  const evidence = [fieldEvidence("https://neuralmind.ai/product")];
  const citation = [nvidiaCitation()];
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

function humanReviewBriefing(overrides = {}) {
  const evidence = [fieldEvidence("https://neuralmind.ai/product")];
  const citation = [nvidiaCitation()];
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
    claims: executiveBriefing().claims,
    unknowns: ["funding is unknown from collected public evidence."],
    risks: ["external_api_dependency: no evidence that APIs are the only AI dependency."],
    review_reasons: [],
    pending_questions: executiveBriefing().pending_questions,
    evidence_references: executiveBriefing().evidence_references,
    citation_references: executiveBriefing().citation_references,
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

function fieldEvidence(url) {
  return {
    url,
    source_type: "public_page",
    snippet: "Public evidence mentions model serving, latency, and proprietary AI signals."
  };
}

function nvidiaCitation() {
  return {
    document_id: "nvidia-nim-developers",
    chunk_id: "nvidia-nim-developers:0",
    document_title: "NVIDIA NIM for Developers",
    source_url: "https://developer.nvidia.com/nim"
  };
}
