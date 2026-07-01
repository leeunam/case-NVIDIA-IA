import {
  RUN_RECORD_SCHEMA_VERSION,
  SMOKE_MATRIX_SCHEMA_VERSION,
  assertRunRecord,
  assertSmokeMatrix,
  validateRunRequest
} from "./api-contract.js";

/**
 * @typedef {import("./api-contract.js").FrontendApiClient} FrontendApiClient
 * @typedef {import("./api-contract.js").FrontendRunRequest} FrontendRunRequest
 */

/**
 * @param {{delayMs?: number, clock?: () => Date}=} options
 * @returns {FrontendApiClient}
 */
export function createMockFrontendApiClient(options = {}) {
  const delayMs = Number(options.delayMs || 0);
  const clock = options.clock || (() => new Date("2026-06-30T12:00:00.000Z"));
  /** @type {Map<string, import("./api-contract.js").FrontendRunRecord>} */
  const runs = new Map();
  let sequence = 1;
  seedRouteRuns(runs, clock);

  return {
    async startRun(request) {
      validateRunRequest(request);
      await delay(delayMs);
      const record = buildMockRunRecord(request, {
        runId: `mock-run-${String(sequence).padStart(3, "0")}`,
        createdAt: clock().toISOString()
      });
      sequence += 1;
      runs.set(record.run_id, record);
      return record;
    },

    async getRun(runId) {
      await delay(delayMs);
      const record = runs.get(runId);
      if (!record) {
        throw new Error("run_not_found");
      }
      return record;
    },

    async getProductionSmokeMatrix(only = []) {
      await delay(delayMs);
      const matrix = buildMockSmokeMatrix(only);
      return assertSmokeMatrix(matrix);
    }
  };
}

/**
 * @param {FrontendRunRequest} request
 * @param {{runId: string, createdAt: string}} metadata
 */
export function buildMockRunRecord(request, metadata) {
  const startupIdentifier =
    textOrUnknown(request.startup_name) !== "unknown"
      ? textOrUnknown(request.startup_name)
      : request.startup_url
        ? hostname(request.startup_url)
        : "Brazilian AI startup search";
  const input = {
    startup_url: request.startup_url || null,
    query: request.query || null,
    startup_name: textOrUnknown(request.startup_name)
  };
  const branchDecisions = [
    {
      branch_name: "ready_for_recommendation",
      next_action: "retrieve_nvidia_knowledge",
      audit_reason: "collection_quality_ready"
    },
    {
      branch_name: "ready_for_briefing",
      next_action: "generate_executive_briefing",
      audit_reason: "supported_recommendation_has_official_citation"
    },
    {
      branch_name: "briefing_generated",
      next_action: "prepare_technical_outreach",
      audit_reason: "executive_briefing_ready_for_use"
    }
  ];
  const persistenceReferences = [
    {
      artifact_kind: "briefing",
      startup_identifier: startupIdentifier,
      storage: "json",
      reference: `runs/${metadata.runId}/processed/downstream/${safePathSegment(startupIdentifier)}/briefing.json`
    }
  ];
  const assessmentEvidences = [
    evidenceRecord({
      url: input.startup_url || "https://neuralmind.ai/",
      title: startupIdentifier,
      snippet:
        "Sinais de IA: modelos proprietarios, fine-tuning, inferencia em producao, latencia e dados proprietarios.",
      collectedAt: metadata.createdAt
    }),
    evidenceRecord({
      url: `${input.startup_url || "https://neuralmind.ai/"}product`,
      title: `${startupIdentifier} Product`,
      snippet:
        "Tecnologias: MLOps, dados proprietarios, feedback loop, model serving e suporte tecnico para escala.",
      collectedAt: metadata.createdAt
    })
  ];
  const finalPayload = {
    schema_version: "operational_entrypoint_result.v1",
    run_id: metadata.runId,
    created_at: metadata.createdAt,
    input,
    startup_identifier: startupIdentifier,
    workflow_outcome: "briefing_generated",
    next_action: "prepare_technical_outreach",
    briefing_reference: {
      briefing_type: "executive",
      artifact_kind: "briefing",
      startup_identifier: startupIdentifier
    },
    human_review_reasons: [],
    branch_decisions: branchDecisions,
    artifact_locations: {
      json_run_dir: `runs/${metadata.runId}`,
      processed_dir: `runs/${metadata.runId}/processed`
    },
    persistence_references: persistenceReferences,
    errors: [],
    options: {
      persistence_mode: request.persistence_mode || "json",
      retrieval_mode: request.retrieval_mode || "bm25",
      orchestration: request.orchestration || "local",
      render_js: Boolean(request.render_js),
      search_provider: Boolean(request.enable_search_provider),
      reranking: Boolean(request.enable_reranking),
      llm_narrative: Boolean(request.llm_narrative)
    },
    collection_quality: {
      schema_version: "collection_quality_summary.v1",
      readiness: "ready_for_ai_native_assessment",
      collected_pages: 2,
      unknown_field_rate: 0.17,
      conflict_count: 0
    },
    ...buildMockEvidenceArtifacts({
      startupIdentifier,
      createdAt: metadata.createdAt
    }),
    ai_native_assessment: buildMockAiNativeAssessment({
      runId: metadata.runId,
      startupIdentifier,
      evidences: assessmentEvidences
    }),
    gap_space_assessment: buildMockGapSpaceAssessment({
      runId: metadata.runId,
      startupIdentifier,
      evidences: assessmentEvidences
    }),
    nvidia_match: {
      schema_version: "nvidia_recommendation.v1",
      priority: "high",
      supported_recommendations: [
        {
          recommendation_type: "technical",
          title: "Evaluate NVIDIA inference stack for model serving",
          citation_count: 2
        }
      ],
      blocked_recommendations: []
    },
    executive_briefing: mockExecutiveBriefing(metadata.runId, startupIdentifier),
    briefing_narrative: mockBriefingNarrative(metadata.runId, startupIdentifier)
  };
  return assertRunRecord({
    schema_version: RUN_RECORD_SCHEMA_VERSION,
    run_id: metadata.runId,
    status: "completed",
    workflow_outcome: "briefing_generated",
    created_at: metadata.createdAt,
    input,
    startup_identifier: startupIdentifier,
    next_action: "prepare_technical_outreach",
    briefing_reference: finalPayload.briefing_reference,
    human_review_reasons: [],
    branch_decisions: branchDecisions,
    artifact_references: {
      artifact_locations: finalPayload.artifact_locations,
      persistence_references: persistenceReferences
    },
    errors: [],
    options: finalPayload.options,
    final_payload: finalPayload
  });
}

export function buildMockConflictingEvidenceRunRecord(metadata = {}) {
  const record = buildMockRunRecord(
    {
      startup_url: "https://conflict-startup.ai/",
      startup_name: "Conflict Startup"
    },
    {
      runId: metadata.runId || "mock-conflicting-evidence-run",
      createdAt: metadata.createdAt || "2026-06-30T12:45:00.000Z"
    }
  );
  const artifacts = buildMockEvidenceArtifacts({
    startupIdentifier: "Conflict Startup",
    createdAt: record.created_at,
    conflict: true
  });
  const conflictEvidences = [
    evidenceRecord({
      url: "https://conflict-startup.ai/product",
      title: "Conflict Startup Product",
      snippet: "Tecnologias: MLOps e model serving.",
      collectedAt: record.created_at
    }),
    evidenceRecord({
      url: "https://directory.example/conflict-startup",
      title: "Directory profile",
      snippet: "Diretorio publico indica somente chatbot generico.",
      collectedAt: record.created_at,
      sourceType: "directory_profile"
    })
  ];
  const assessment = buildMockConflictAssessment({
    runId: record.run_id,
    startupIdentifier: "Conflict Startup",
    evidences: conflictEvidences
  });
  return assertRunRecord({
    ...record,
    human_review_reasons: ["conflicting_startup_evidence", "unknown_funding"],
    final_payload: {
      ...record.final_payload,
      ...artifacts,
      human_review_reasons: ["conflicting_startup_evidence", "unknown_funding"],
      ai_native_assessment: assessment,
      human_review_briefing: buildMockHumanReviewBriefing({
        runId: record.run_id,
        startupIdentifier: "Conflict Startup",
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
    }
  });
}

export function buildMockCollectionFailureEvidenceRunRecord(metadata = {}) {
  const record = buildMockRunRecord(
    {
      startup_url: "https://blocked-startup.ai/",
      startup_name: "Blocked Startup"
    },
    {
      runId: metadata.runId || "mock-collection-failure-evidence-run",
      createdAt: metadata.createdAt || "2026-06-30T13:00:00.000Z"
    }
  );
  const artifacts = buildMockEvidenceArtifacts({
    startupIdentifier: "Blocked Startup",
    createdAt: record.created_at,
    collectionFailure: true
  });
  return assertRunRecord({
    ...record,
    workflow_outcome: "needs_more_collection_or_human_review",
    next_action: "resolve_blocking_evidence",
    human_review_reasons: ["robots_blocked_collection", "average_evidence_below_threshold"],
    final_payload: {
      ...record.final_payload,
      ...artifacts,
      workflow_outcome: "needs_more_collection_or_human_review",
      next_action: "resolve_blocking_evidence",
      human_review_reasons: ["robots_blocked_collection", "average_evidence_below_threshold"],
      ai_native_assessment: buildMockInsufficientAssessment({
        runId: record.run_id,
        startupIdentifier: "Blocked Startup"
      }),
      human_review_briefing: buildMockHumanReviewBriefing({
        runId: record.run_id,
        startupIdentifier: "Blocked Startup",
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
  });
}

export function buildMockHumanReviewRunRecord(metadata = {}) {
  const record = buildMockRunRecord(
    {
      startup_url: "https://review-startup.ai/",
      startup_name: "Review Startup"
    },
    {
      runId: metadata.runId || "mock-human-review-run",
      createdAt: metadata.createdAt || "2026-06-30T12:15:00.000Z"
    }
  );
  const branchDecisions = [
    {
      branch_name: "ready_for_recommendation",
      next_action: "retrieve_nvidia_knowledge",
      audit_reason: "collection_quality_ready"
    },
    {
      branch_name: "human_review_requested",
      next_action: "generate_human_review_briefing",
      audit_reason: "recommendation_hypothesis_requires_human_review"
    }
  ];
  const humanReviewReasons = ["recommendation_hypothesis_requires_human_review"];
  const briefingReference = {
    briefing_type: "human_review",
    artifact_kind: "briefing",
    startup_identifier: "Review Startup"
  };
  const wrapperEvidence = [
    evidenceRecord({
      url: "https://review-startup.ai/product",
      title: "Review Startup Product",
      snippet: "Produto usa OpenAI API e ChatGPT sem dados proprietarios observados.",
      collectedAt: record.created_at
    })
  ];
  const finalPayload = {
    ...record.final_payload,
    workflow_outcome: "human_review_requested",
    next_action: "validate_nvidia_fit_with_human",
    briefing_reference: briefingReference,
    human_review_reasons: humanReviewReasons,
    branch_decisions: branchDecisions,
    ai_native_assessment: buildMockHighWrapperRiskAssessment({
      runId: record.run_id,
      startupIdentifier: "Review Startup",
      evidences: wrapperEvidence
    }),
    human_review_briefing: buildMockHumanReviewBriefing({
      runId: record.run_id,
      startupIdentifier: "Review Startup",
      reviewReasons: ["high_wrapper_dependency_risk", "recommendation_hypothesis_requires_human_review"],
      pendingQuestions: [
        {
          field_name: "external_api_only",
          question:
            "Validate dependency on external APIs, proprietary data, and production inference before prioritizing NVIDIA outreach.",
          priority: "critical",
          reason: "wrapper_risk_requires_validation"
        }
      ]
    }),
    nvidia_match: {
      ...record.final_payload.nvidia_match,
      priority: "human_review",
      supported_recommendations: [],
      blocked_recommendations: [
        {
          recommendation_type: "technical",
          title: "Validate NVIDIA fit with human review",
          rationale: "The recommendation is a hypothesis because official citation support is incomplete."
        }
      ]
    }
  };
  return assertRunRecord({
    ...record,
    workflow_outcome: "human_review_requested",
    next_action: "validate_nvidia_fit_with_human",
    briefing_reference: briefingReference,
    human_review_reasons: humanReviewReasons,
    branch_decisions: branchDecisions,
    final_payload: finalPayload
  });
}

export function buildMockFailedRunRecord(metadata = {}) {
  const runId = metadata.runId || "mock-failed-run";
  const createdAt = metadata.createdAt || "2026-06-30T12:30:00.000Z";
  const error = {
    step: "execute_search",
    error_type: "TimeoutError",
    message: "search provider timeout",
    audit_reason: "search_adapter_failed_structured_error"
  };
  const finalPayload = {
    schema_version: "operational_entrypoint_result.v1",
    run_id: runId,
    created_at: createdAt,
    input: {
      startup_url: null,
      query: "Brazilian AI-native startups",
      startup_name: "unknown"
    },
    startup_identifier: "unknown",
    workflow_outcome: "failed_with_auditable_error",
    next_action: "review_workflow_errors",
    briefing_reference: null,
    human_review_reasons: ["search_adapter_failed_structured_error"],
    branch_decisions: [
      {
        branch_name: "failed_with_auditable_error",
        next_action: "review_workflow_errors",
        audit_reason: "search_adapter_failed_structured_error"
      }
    ],
    artifact_locations: {},
    persistence_references: [],
    errors: [error],
    options: {
      persistence_mode: "json",
      retrieval_mode: "bm25",
      orchestration: "local",
      render_js: false,
      search_provider: true,
      reranking: false,
      llm_narrative: false
    }
  };
  return assertRunRecord({
    schema_version: RUN_RECORD_SCHEMA_VERSION,
    run_id: runId,
    status: "failed",
    workflow_outcome: "failed_with_auditable_error",
    created_at: createdAt,
    input: finalPayload.input,
    startup_identifier: "unknown",
    next_action: "review_workflow_errors",
    briefing_reference: null,
    human_review_reasons: finalPayload.human_review_reasons,
    branch_decisions: finalPayload.branch_decisions,
    artifact_references: {
      artifact_locations: {},
      persistence_references: []
    },
    errors: [error],
    options: finalPayload.options,
    final_payload: finalPayload
  });
}

/**
 * @param {string[]} only
 */
export function buildMockSmokeMatrix(only = []) {
  const selected = new Set(only.filter(Boolean));
  const steps = [
    step("playwright_collection", "Playwright real collection", "collection"),
    step("postgres_persistence", "Postgres persistence", "postgres"),
    step("pgvector_retrieval", "pgvector retrieval", "pgvector"),
    step("real_embeddings", "Real embedding model", "embedding"),
    step("hybrid_retrieval", "Hybrid BM25 plus pgvector retrieval", "retrieval"),
    step("reranking", "Real reranking", "reranking"),
    step("langgraph_checkpoint", "LangGraph Postgres checkpointing", "langgraph"),
    step("groq_litellm_narrative", "Groq/LiteLLM briefing narrative", "llm"),
    step("full_operational_smoke", "Full bounded operational smoke", "briefing_quality")
  ].filter((item) => !selected.size || selected.has(item.integration_id));
  return {
    schema_version: SMOKE_MATRIX_SCHEMA_VERSION,
    read_only: true,
    matrix: {
      schema_version: "production_smoke_matrix.v1",
      overall_status: "skipped",
      steps
    }
  };
}

function step(integrationId, title, bottleneck) {
  const envFlag = `NVIDIA_STARTUP_INTEL_RUN_${integrationId.toUpperCase()}_SMOKE`;
  return {
    integration_id: integrationId,
    title,
    status: "skipped",
    bottleneck,
    message: `set ${envFlag}=1 to enable`,
    command: "opt-in smoke command",
    prerequisites: [],
    required_env_vars: [],
    expected_artifacts: [],
    cleanup: [],
    payload: {}
  };
}

function mockExecutiveBriefing(runId, startupIdentifier) {
  const evidence = [mockEvidence("https://neuralmind.ai/product")];
  const citation = [mockCitation()];
  return {
    schema_version: "executive_briefing.v1",
    run_id: runId,
    startup_identifier: startupIdentifier,
    status: "ready_for_use",
    executive_summary: `${startupIdentifier} is classified as ai_native and has a supported NVIDIA recommendation for model serving.`,
    diagnosis: `AI-native assessment classified ${startupIdentifier} as ai_native with confidence 0.84.`,
    opportunity: "high",
    risks: ["external_api_only: mock evidence includes proprietary data and production inference signals."],
    recommendations: ["Recommend NVIDIA NIM Microservices for model_serving."],
    pending_questions: [
      {
        field_name: "funding",
        question: "What is the startup's current funding stage or financing context?",
        priority: "complementary",
        reason: "missing_startup_profile_field"
      }
    ],
    claims: [
      {
        text: `company_name: ${startupIdentifier}`,
        claim_type: "observed",
        section: "profile",
        confidence: 1,
        evidence_references: evidence,
        citation_references: []
      },
      {
        text: `AI-native assessment classified ${startupIdentifier} as ai_native with confidence 0.84.`,
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
    audit_reasons: ["collection_quality_ready"]
  };
}

function mockBriefingNarrative(runId, startupIdentifier) {
  return {
    schema_version: "briefing_narrative.v1",
    run_id: runId,
    startup_identifier: startupIdentifier,
    source_briefing_schema_version: "executive_briefing.v1",
    source_briefing_status: "ready_for_use",
    technical_gap_narrative:
      "Use the supported model_serving gap and cited NVIDIA NIM Microservices reference as the technical anchor.",
    commercial_approach_narrative:
      "Prepare technical outreach while keeping funding as an explicit pending question.",
    narrative_text:
      "technical_gap_narrative: Use model_serving. commercial_approach_narrative: Prepare technical outreach.",
    claims: mockExecutiveBriefing(runId, startupIdentifier).claims,
    unknowns: ["funding is unknown from collected public evidence."],
    risks: ["external_api_only: mock evidence includes proprietary data and production inference signals."],
    review_reasons: [],
    pending_questions: mockExecutiveBriefing(runId, startupIdentifier).pending_questions,
    evidence_references: mockExecutiveBriefing(runId, startupIdentifier).evidence_references,
    citation_references: mockExecutiveBriefing(runId, startupIdentifier).citation_references,
    next_action: "prepare_technical_outreach",
    llm_request: {
      purpose: "briefing_narrative",
      structured_output_schema: "briefing_narrative.v1",
      metadata: {
        run_id: runId,
        source_briefing_schema_version: "executive_briefing.v1"
      }
    },
    llm_response: {
      provider: "local_fake",
      model: "deterministic-briefing-fixture",
      model_version: "mock",
      finish_reason: "stop",
      usage: {},
      metadata: {
        adapter: "fixture",
        configured_api_key_env_var: ""
      }
    },
    audit_reasons: ["llm_narrative_generated_from_validated_briefing", "llm_narrative_accepted"]
  };
}

function mockEvidence(url) {
  return {
    url,
    source_type: "public_page",
    snippet: "Mock public evidence mentions model serving, latency, and proprietary AI signals."
  };
}

function mockCitation() {
  return {
    document_id: "nvidia-nim-developers",
    chunk_id: "nvidia-nim-developers:0",
    document_title: "NVIDIA NIM for Developers",
    source_url: "https://developer.nvidia.com/nim"
  };
}

function buildMockEvidenceArtifacts({ startupIdentifier, createdAt, conflict = false, collectionFailure = false }) {
  const baseUrl = collectionFailure ? "https://blocked-startup.ai/" : "https://neuralmind.ai/";
  const productUrl = collectionFailure ? "https://blocked-startup.ai/product" : "https://neuralmind.ai/product";
  const collectedAt = createdAt || "2026-06-30T12:00:00.000Z";
  const homeEvidence = evidenceRecord({
    url: baseUrl,
    title: startupIdentifier,
    snippet:
      "Resumo: Plataforma AI-native para documentos. Setor: dados. Sinais de IA: modelos proprietarios e inferencia em producao.",
    collectedAt
  });
  const productEvidence = evidenceRecord({
    url: productUrl,
    title: `${startupIdentifier} Product`,
    snippet:
      "Produto: Copiloto documental com IA generativa. Tecnologias: MLOps, dados proprietarios, feedback loop e model serving.",
    collectedAt
  });
  const conflictEvidence = evidenceRecord({
    url: "https://directory.example/conflict-startup",
    title: "Directory profile",
    snippet: "Setor: fintech. Diretorio publico com classificacao divergente para a startup.",
    collectedAt,
    sourceType: "directory_profile"
  });
  const profile = {
    schema_version: "startup_profile.v1",
    company_name: profileField(startupIdentifier, "observed", [homeEvidence]),
    official_site: profileField(baseUrl.replace(/\/$/, ""), "observed", [homeEvidence]),
    company_summary: profileField("Plataforma AI-native para documentos", "observed", [homeEvidence]),
    sector: profileField(conflict ? "healthtech" : "dados", conflict ? "inferred" : "observed", [homeEvidence]),
    product: profileField("Copiloto documental com IA generativa", "observed", [productEvidence]),
    customers: profileField("bancos", "observed", [homeEvidence]),
    funding: profileField("unknown", "unknown", []),
    founders: profileField("Ana Silva", "observed", [homeEvidence]),
    technologies_used: profileField("MLOps, dados proprietarios, feedback loop e model serving", "observed", [
      productEvidence
    ]),
    ai_signals: profileField("modelos proprietarios, inferencia em producao", "inferred", [
      homeEvidence,
      productEvidence
    ]),
    location: profileField("Campinas, SP", "observed", [homeEvidence])
  };
  const evidenceGroups = [
    fieldEvidenceGroup("ai_signals", profile.ai_signals.value, [homeEvidence, productEvidence]),
    fieldEvidenceGroup("company_summary", profile.company_summary.value, [homeEvidence]),
    fieldEvidenceGroup("product", profile.product.value, [productEvidence]),
    fieldEvidenceGroup("sector", profile.sector.value, conflict ? [homeEvidence, conflictEvidence] : [homeEvidence], {
      hasConflict: conflict,
      conflictingValues: conflict ? ["healthtech", "fintech"] : []
    }),
    fieldEvidenceGroup("technologies_used", profile.technologies_used.value, [productEvidence])
  ];
  const collectedPages = collectionFailure
    ? {
        "url:https://blocked-startup.ai": {
          pages: [],
          errors: [
            {
              url: "https://blocked-startup.ai/",
              error_type: "RobotsPolicyDisallowed",
              message: "robots.txt disallowed collection for this path",
              collected_at: collectedAt,
              status_code: null,
              error_category: "robots_disallowed"
            },
            {
              url: "https://blocked-startup.ai/product",
              error_type: "TimeoutError",
              message: "browser render timed out before readable text was extracted",
              collected_at: collectedAt,
              status_code: 504,
              error_category: "browser_render_failed"
            }
          ]
        }
      }
    : {
        "url:https://neuralmind.ai": {
          pages: [
            {
              url: baseUrl,
              title: startupIdentifier,
              main_text:
                "Resumo: Plataforma AI-native para documentos. Setor: dados. Clientes: bancos. Founders: Ana Silva. Localizacao: Campinas, SP.",
              collected_at: collectedAt,
              status_code: 200,
              extraction_strategy: "trafilatura+beautifulsoup+playwright",
              needs_js_rendering: true
            },
            {
              url: productUrl,
              title: `${startupIdentifier} Product`,
              main_text:
                "Produto: Copiloto documental com IA generativa. Tecnologias: MLOps, dados proprietarios, feedback loop e model serving.",
              collected_at: collectedAt,
              status_code: 200,
              extraction_strategy: "trafilatura+beautifulsoup",
              needs_js_rendering: false
            }
          ],
          errors: []
        }
      };
  const qualitySummary = collectionFailure
    ? {
        candidate_count: 1,
        official_site_found_count: 1,
        official_site_found_rate: 1,
        minimum_profile_complete_count: 0,
        minimum_profile_complete_rate: 0,
        average_evidences_per_startup: 0,
        unknown_fields: [
          ["company_summary", 1],
          ["product", 1],
          ["ai_signals", 1]
        ],
        source_success_rates: [
          {
            source_name: "url:https://blocked-startup.ai",
            attempts: 2,
            successes: 0,
            failures: 2,
            success_rate: 0
          }
        ],
        ready_for_evaluation: false,
        readiness_reasons: ["minimum_profile_coverage_below_threshold", "average_evidence_below_threshold"]
      }
    : {
        candidate_count: 1,
        official_site_found_count: 1,
        official_site_found_rate: 1,
        minimum_profile_complete_count: 1,
        minimum_profile_complete_rate: 1,
        average_evidences_per_startup: 8,
        unknown_fields: [["funding", 1]],
        source_success_rates: [
          {
            source_name: "url:https://neuralmind.ai",
            attempts: 2,
            successes: 2,
            failures: 0,
            success_rate: 1
          }
        ],
        ready_for_evaluation: !conflict,
        readiness_reasons: conflict ? ["conflicting_startup_evidence"] : ["ready_for_ai_native_evaluation"]
      };
  const profileKey = `url:${baseUrl.replace(/\/$/, "")}`;
  return {
    collected_pages_by_candidate: collectedPages,
    profiles: collectionFailure ? [] : [profile],
    evidence_groups_by_profile: collectionFailure ? {} : { [profileKey]: evidenceGroups },
    quality_summary: qualitySummary
  };
}

function buildMockAiNativeAssessment({ runId, startupIdentifier, evidences }) {
  return {
    schema_version: "ai_native_assessment.v1",
    run_id: runId,
    company_name: startupIdentifier,
    classification: "ai_native",
    confidence: 0.84,
    nvidia_opportunity_urgency: "urgent",
    criteria_results: [
      assessmentCriterion("ai_product_centrality", "positive", evidences),
      assessmentCriterion("ai_architecture_depth", "positive", evidences),
      assessmentCriterion("proprietary_data_loop", "positive", evidences),
      assessmentCriterion("production_readiness", "positive", evidences),
      assessmentCriterion("scale_governance_need", "positive", evidences),
      {
        criterion: "evidence_quality",
        status: "positive",
        confidence: 0.8,
        rationale: "Collection quality is ready for AI-native evaluation.",
        evidences: []
      }
    ],
    positive_signals: [
      {
        signal_type: "ai_architecture_depth",
        description: "Evidence mentions proprietary models, tuning, MLOps, or inference architecture.",
        confidence: 0.8,
        evidences
      },
      {
        signal_type: "production_readiness",
        description: "Evidence indicates production inference, serving, MLOps, or latency concerns.",
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
      },
      {
        gap_type: "data_acceleration",
        description: "Potential need around data processing, feedback loops, or acceleration.",
        severity: "medium",
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
      },
      {
        risk_type: "no_proprietary_data_evidence",
        severity: "low",
        confidence: 0.8,
        rationale: "Evidence indicates proprietary data or feedback loops.",
        evidences,
        is_hypothesis: false
      }
    ],
    insufficient_evidence_fields: ["funding"],
    evidences,
    diagnostic_quality: {
      ready_for_recommendation: true,
      requires_human_review: false,
      reasons: ["ready_for_recommendation"]
    },
    ready_for_recommendation: true
  };
}

function buildMockGapSpaceAssessment({ runId, startupIdentifier, evidences }) {
  return {
    schema_version: "gap_space_assessment.v1",
    run_id: runId,
    startup_identifier: startupIdentifier,
    corpus_version: "official-nvidia-fixture.v1",
    commercial_opportunities: [
      {
        opportunity_type: "inception_program_fit",
        description: "Potential startup program support, technical enablement, or go-to-market opportunity.",
        confidence: 0.78,
        evidences,
        is_hypothesis: false
      }
    ],
    commercial_mappings: [],
    quality: {
      ready_for_recommendation: true,
      requires_human_review: false,
      reasons: ["gap_space_ready_for_recommendation"],
      human_review_reasons: []
    }
  };
}

function buildMockInsufficientAssessment({ runId, startupIdentifier }) {
  return {
    schema_version: "ai_native_assessment.v1",
    run_id: runId,
    company_name: startupIdentifier,
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
    insufficient_evidence_fields: ["collection_quality", "company_summary", "product", "ai_signals"],
    evidences: [],
    diagnostic_quality: {
      ready_for_recommendation: false,
      requires_human_review: true,
      reasons: ["collection_quality_not_ready", "unknown_assessment_criteria"]
    },
    ready_for_recommendation: false
  };
}

function buildMockHighWrapperRiskAssessment({ runId, startupIdentifier, evidences }) {
  const base = buildMockAiNativeAssessment({ runId, startupIdentifier, evidences });
  return {
    ...base,
    classification: "ai_enabled",
    confidence: 0.58,
    nvidia_opportunity_urgency: "human_review",
    criteria_results: [
      assessmentCriterion("ai_product_centrality", "positive", evidences),
      assessmentCriterion("ai_architecture_depth", "negative", []),
      assessmentCriterion("proprietary_data_loop", "unknown", []),
      assessmentCriterion("production_readiness", "unknown", [])
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
    insufficient_evidence_fields: ["technologies_used"],
    diagnostic_quality: {
      ready_for_recommendation: false,
      requires_human_review: true,
      reasons: ["classification_confidence_below_threshold", "high_wrapper_dependency_risk"]
    },
    ready_for_recommendation: false
  };
}

function buildMockConflictAssessment({ runId, startupIdentifier, evidences }) {
  const base = buildMockAiNativeAssessment({ runId, startupIdentifier, evidences });
  return {
    ...base,
    classification: "ai_enabled",
    confidence: 0.52,
    nvidia_opportunity_urgency: "human_review",
    criteria_results: [
      assessmentCriterion("ai_product_centrality", "positive", evidences),
      assessmentCriterion("ai_architecture_depth", "conflict", evidences),
      assessmentCriterion("production_readiness", "unknown", [])
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

function buildMockHumanReviewBriefing({ runId, startupIdentifier, reviewReasons, pendingQuestions }) {
  return {
    schema_version: "human_review_briefing.v1",
    run_id: runId,
    startup_identifier: startupIdentifier,
    status: "ready_for_human_review",
    review_reasons: reviewReasons,
    pending_questions: pendingQuestions,
    next_action: "validate_nvidia_fit_with_human"
  };
}

function assessmentCriterion(criterion, status, evidences) {
  return {
    criterion,
    status,
    confidence: status === "positive" ? 0.8 : status === "conflict" ? 0.4 : 0.55,
    rationale: assessmentCriterionRationale(criterion, status),
    evidences: status === "negative" || status === "unknown" ? [] : evidences
  };
}

function assessmentCriterionRationale(criterion, status) {
  if (status === "conflict") {
    return `Public evidence conflicts for ${criterion}.`;
  }
  if (status === "negative") {
    return `No strong public support for ${criterion}.`;
  }
  if (status === "unknown") {
    return `Insufficient public evidence for ${criterion}.`;
  }
  return `Public evidence supports ${criterion}.`;
}

function evidenceRecord({ url, title, snippet, collectedAt, sourceType = "collected_page" }) {
  return {
    url,
    title,
    snippet,
    collected_at: collectedAt,
    source_type: sourceType
  };
}

function profileField(value, claimSource, evidences) {
  return {
    value,
    claim_source: claimSource,
    evidences
  };
}

function fieldEvidenceGroup(
  fieldName,
  value,
  evidences,
  { hasConflict = false, conflictingValues = [] } = {}
) {
  return {
    field_name: fieldName,
    value,
    evidences,
    has_conflict: hasConflict,
    conflicting_values: conflictingValues
  };
}

function textOrUnknown(value) {
  const text = String(value || "").trim();
  return text || "unknown";
}

function seedRouteRuns(runs, clock) {
  const completed = buildMockRunRecord(
    {
      startup_url: "https://neuralmind.ai/",
      startup_name: "NeuralMind"
    },
    {
      runId: "mock-completed-run",
      createdAt: clock().toISOString()
    }
  );
  for (const record of [completed, buildMockHumanReviewRunRecord(), buildMockFailedRunRecord()]) {
    runs.set(record.run_id, record);
  }
}

function safePathSegment(value) {
  return String(value || "unknown")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function hostname(value) {
  try {
    return new URL(String(value)).hostname.replace(/^www\./, "");
  } catch {
    return String(value || "unknown");
  }
}

function delay(ms) {
  if (!ms) {
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}
