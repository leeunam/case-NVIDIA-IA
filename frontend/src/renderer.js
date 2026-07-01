export const SECTIONS = [
  { id: "runs", label: "Runs" },
  { id: "evidence", label: "Evidence" },
  { id: "assessment", label: "Assessment" },
  { id: "nvidia-match", label: "NVIDIA Match" },
  { id: "briefing", label: "Briefing" },
  { id: "production-smokes", label: "Production Smokes" }
];

/**
 * @typedef {import("./api-contract.js").FrontendRunRecord} FrontendRunRecord
 * @typedef {import("./api-contract.js").ProductionSmokeMatrix} ProductionSmokeMatrix
 *
 * @typedef {Object} WorkbenchState
 * @property {string} activeSection
 * @property {"mock" | "real"} apiMode
 * @property {string} apiBaseUrl
 * @property {FrontendRunRecord | null} currentRun
 * @property {ProductionSmokeMatrix | null} smokeMatrix
 * @property {boolean} isBusy
 * @property {string} notice
 * @property {string} errorMessage
 */

/**
 * @param {Partial<WorkbenchState>=} overrides
 * @returns {WorkbenchState}
 */
export function createInitialState(overrides = {}) {
  return {
    activeSection: "runs",
    apiMode: "mock",
    apiBaseUrl: "http://127.0.0.1:8000",
    currentRun: null,
    smokeMatrix: null,
    isBusy: false,
    notice: "",
    errorMessage: "",
    ...overrides
  };
}

/**
 * @param {WorkbenchState} state
 */
export function renderApp(state) {
  return `
    <div class="app-shell">
      <aside class="sidebar" aria-label="Primary">
        <div class="brand-block">
          <span class="brand-mark" aria-hidden="true"></span>
          <div>
            <p class="eyebrow">NVIDIA Startup Intel</p>
            <h1>Operational Workbench</h1>
          </div>
        </div>
        <nav class="section-nav">
          ${SECTIONS.map((section) => renderNavItem(section, state.activeSection)).join("")}
        </nav>
        <div class="api-panel">
          <span class="mode-dot mode-${escapeAttr(state.apiMode)}" aria-hidden="true"></span>
          <div>
            <p class="panel-label">API mode</p>
            <p class="panel-value">${escapeHtml(state.apiMode)}</p>
          </div>
        </div>
      </aside>
      <main class="workspace">
        <header class="topbar">
          <div>
            <p class="eyebrow">${escapeHtml(activeSectionLabel(state.activeSection))}</p>
            <h2>${escapeHtml(sectionTitle(state.activeSection))}</h2>
          </div>
          <div class="run-chip" data-testid="run-chip">
            <span>${state.currentRun ? escapeHtml(state.currentRun.status) : "idle"}</span>
            <strong>${state.currentRun ? escapeHtml(state.currentRun.run_id) : "no run"}</strong>
          </div>
        </header>
        ${renderMessages(state)}
        ${renderActiveSection(state)}
      </main>
    </div>
  `;
}

function renderNavItem(section, activeSection) {
  const active = section.id === activeSection;
  return `
    <button class="nav-item${active ? " is-active" : ""}" type="button" data-section="${escapeAttr(
      section.id
    )}" aria-current="${active ? "page" : "false"}">
      <span class="nav-glyph" aria-hidden="true"></span>
      <span>${escapeHtml(section.label)}</span>
    </button>
  `;
}

function renderMessages(state) {
  if (!state.notice && !state.errorMessage) {
    return "";
  }
  return `
    <div class="message-stack" aria-live="polite">
      ${state.notice ? `<p class="notice">${escapeHtml(state.notice)}</p>` : ""}
      ${state.errorMessage ? `<p class="error">${escapeHtml(state.errorMessage)}</p>` : ""}
    </div>
  `;
}

function renderActiveSection(state) {
  switch (state.activeSection) {
    case "evidence":
      return renderEvidence(state);
    case "assessment":
      return renderAssessment(state);
    case "nvidia-match":
      return renderNvidiaMatch(state);
    case "briefing":
      return renderBriefing(state);
    case "production-smokes":
      return renderProductionSmokes(state);
    case "runs":
    default:
      return renderRuns(state);
  }
}

function renderRuns(state) {
  return `
    <section class="run-grid" aria-label="Run workbench">
      <form class="panel launch-panel" data-run-form>
        <div class="panel-header">
          <div>
            <p class="eyebrow">Launcher</p>
            <h3>Start intelligence run</h3>
          </div>
          <span class="schema-pill">frontend_api_run_create.v1</span>
        </div>
        <div class="form-grid">
          <label>
            <span>Startup URL</span>
            <input name="startup_url" type="url" placeholder="https://startup.ai/" />
          </label>
          <label>
            <span>Bounded query</span>
            <input name="query" type="text" placeholder="Brazilian AI-native startups in health" />
          </label>
          <label>
            <span>Startup name</span>
            <input name="startup_name" type="text" placeholder="Startup AI" />
          </label>
          <label>
            <span>Max pages</span>
            <input name="max_pages" type="number" min="1" max="5" value="1" />
          </label>
          <label>
            <span>Max depth</span>
            <input name="max_depth" type="number" min="0" max="2" value="0" />
          </label>
          <label>
            <span>Persistence</span>
            <select name="persistence_mode">
              <option value="json">json</option>
              <option value="none">none</option>
              <option value="postgres">postgres</option>
              <option value="json-postgres">json-postgres</option>
            </select>
          </label>
        </div>
        <div class="toggle-row">
          <label><input name="render_js" type="checkbox" /> Render JS</label>
          <label><input name="enable_search_provider" type="checkbox" /> Search provider</label>
          <label><input name="enable_reranking" type="checkbox" /> Reranking</label>
          <label><input name="llm_narrative" type="checkbox" /> LLM narrative</label>
        </div>
        <button class="primary-action" type="submit" ${state.isBusy ? "disabled" : ""}>
          ${state.isBusy ? "Running" : "Start run"}
        </button>
      </form>
      <section class="panel status-panel" aria-label="Run status">
        <div class="panel-header">
          <div>
            <p class="eyebrow">Status</p>
            <h3>${state.currentRun ? escapeHtml(state.currentRun.startup_identifier) : "No active run"}</h3>
          </div>
          <span class="status-badge ${state.currentRun ? statusClass(state.currentRun.status) : "status-idle"}">
            ${state.currentRun ? escapeHtml(state.currentRun.workflow_outcome) : "waiting"}
          </span>
        </div>
        ${state.currentRun ? renderRunSummary(state.currentRun) : renderEmptyState("Run launcher is ready.", "Submit a URL or bounded query to populate the workbench.")}
      </section>
    </section>
    ${renderStageStrip(state.currentRun)}
  `;
}

function renderRunSummary(run) {
  return `
    <dl class="summary-list">
      <div><dt>Run ID</dt><dd>${escapeHtml(run.run_id)}</dd></div>
      <div><dt>Next action</dt><dd>${escapeHtml(run.next_action)}</dd></div>
      <div><dt>Created</dt><dd>${escapeHtml(run.created_at || "unknown")}</dd></div>
      <div><dt>Human review reasons</dt><dd>${renderReasonCount(run.human_review_reasons)}</dd></div>
      <div><dt>Errors</dt><dd>${String(run.errors.length)}</dd></div>
    </dl>
    <div class="status-actions">
      <button type="button" class="secondary-action" data-refresh-run="${escapeAttr(run.run_id)}">Refresh</button>
    </div>
  `;
}

function renderStageStrip(run) {
  const stages = [
    ["Evidence", run ? artifactCount(run) : 0],
    ["Assessment", run && run.final_payload.ai_native_assessment ? 1 : 0],
    ["NVIDIA Match", run && run.final_payload.nvidia_match ? 1 : 0],
    ["Briefing", run && run.briefing_reference ? 1 : 0]
  ];
  return `
    <section class="stage-strip" aria-label="Workflow stages">
      ${stages
        .map(
          ([label, count]) => `
            <article class="stage-tile">
              <span class="stage-meter ${count ? "is-ready" : ""}" aria-hidden="true"></span>
              <div>
                <h3>${escapeHtml(label)}</h3>
                <p>${count ? "available" : "empty"}</p>
              </div>
            </article>
          `
        )
        .join("")}
    </section>
  `;
}

function renderEvidence(state) {
  const run = state.currentRun;
  if (!run) {
    return renderSectionPanel("Evidence", renderEmptyState("No evidence record selected.", "Run artifacts will appear after a run starts."));
  }
  const locations = objectEntries(run.artifact_references.artifact_locations || {});
  const persistence = Array.isArray(run.artifact_references.persistence_references)
    ? run.artifact_references.persistence_references
    : [];
  return renderSectionPanel(
    "Evidence",
    `
      <div class="metric-row">
        ${metric("Artifact locations", String(locations.length))}
        ${metric("Persistence references", String(persistence.length))}
        ${metric("Errors", String(run.errors.length))}
      </div>
      ${
        locations.length
          ? `<ul class="key-list">${locations
              .map(([key, value]) => `<li><span>${escapeHtml(key)}</span><strong>${escapeHtml(String(value))}</strong></li>`)
              .join("")}</ul>`
          : renderEmptyState("No artifact references in this run.", "The API record did not include artifact locations.")
      }
    `
  );
}

function renderAssessment(state) {
  const assessment = state.currentRun?.final_payload?.ai_native_assessment;
  if (!assessment || typeof assessment !== "object") {
    return renderSectionPanel("Assessment", renderEmptyState("No assessment payload yet.", "The API record has no AI-Native Assessment details."));
  }
  const record = /** @type {Record<string, unknown>} */ (assessment);
  const gaps = Array.isArray(record.technical_gaps) ? record.technical_gaps : [];
  const risks = Array.isArray(record.wrapper_dependency_risks) ? record.wrapper_dependency_risks : [];
  return renderSectionPanel(
    "Assessment",
    `
      <div class="metric-row">
        ${metric("Classification", String(record.classification || "unknown"))}
        ${metric("Opportunity signal", String(record.opportunity_signal || "unknown"))}
        ${metric("Wrapper risks", String(risks.length))}
      </div>
      ${renderObjectList("Technical gaps", gaps)}
      ${renderObjectList("Wrapper dependency risks", risks)}
    `
  );
}

function renderNvidiaMatch(state) {
  const match = state.currentRun?.final_payload?.nvidia_match;
  if (!match || typeof match !== "object") {
    return renderSectionPanel("NVIDIA Match", renderEmptyState("No NVIDIA match payload yet.", "Recommendations remain empty until the API record includes matched citations."));
  }
  const record = /** @type {Record<string, unknown>} */ (match);
  const supported = Array.isArray(record.supported_recommendations) ? record.supported_recommendations : [];
  const blocked = Array.isArray(record.blocked_recommendations) ? record.blocked_recommendations : [];
  return renderSectionPanel(
    "NVIDIA Match",
    `
      <div class="metric-row">
        ${metric("Priority", String(record.priority || "unknown"))}
        ${metric("Supported", String(supported.length))}
        ${metric("Blocked", String(blocked.length))}
      </div>
      ${renderObjectList("Supported recommendations", supported)}
      ${renderObjectList("Blocked recommendations", blocked)}
    `
  );
}

function renderBriefing(state) {
  const run = state.currentRun;
  if (!run) {
    return renderSectionPanel("Briefing", renderEmptyState("No briefing selected.", "Briefing references will appear after a completed run."));
  }
  const payload = objectRecord(run.final_payload) || {};
  const reference = objectRecord(run.briefing_reference || payload.briefing_reference);
  const artifact = selectBriefingArtifact(run, payload, reference);
  if (!artifact) {
    return renderBriefingReferenceFallback(run, reference);
  }
  if (artifact.type === "human_review") {
    return renderHumanReviewBriefing(run, artifact.record, objectRecord(payload.briefing_narrative));
  }
  return renderExecutiveBriefing(run, artifact.record, objectRecord(payload.briefing_narrative));
}

function renderExecutiveBriefing(run, briefing, narrative) {
  return renderSectionPanel(
    "Executive Briefing",
    `
      ${renderBriefingActions(run)}
      <div class="metric-row briefing-metrics">
        ${metric("Workflow outcome", run.workflow_outcome)}
        ${metric("Status", String(briefing.status || "unknown"))}
        ${metric("Next action", String(briefing.next_action || run.next_action || "unknown"))}
      </div>
      <div class="metric-row briefing-metrics">
        ${metric("Opportunity", String(briefing.opportunity || "unknown"))}
        ${metric("Human review reasons", renderReasonCount(run.human_review_reasons))}
        ${metric("Schema", String(briefing.schema_version || "unknown"))}
      </div>
      ${renderNarrativeSection(narrative, briefing)}
      <div class="briefing-grid">
        ${renderBriefingTextBlock("Summary", briefing.executive_summary)}
        ${renderBriefingTextBlock("Diagnosis", briefing.diagnosis)}
      </div>
      ${renderTextList("Risks", arrayValues(briefing.risks))}
      ${renderTextList("Recommendations", arrayValues(briefing.recommendations))}
      ${renderPendingQuestions("Pending questions", records(briefing.pending_questions))}
      ${renderClaims("Claims", records(briefing.claims))}
      ${renderReferences("Evidence refs", records(briefing.evidence_references), "evidence")}
      ${renderReferences("Citation refs", records(briefing.citation_references), "citation")}
      ${renderTextList("Audit reasons", arrayValues(briefing.audit_reasons))}
    `
  );
}

function renderHumanReviewBriefing(run, briefing, narrative) {
  return renderSectionPanel(
    "Human Review Briefing",
    `
      ${renderBriefingActions(run)}
      <div class="metric-row briefing-metrics">
        ${metric("Workflow outcome", run.workflow_outcome)}
        ${metric("Status", String(briefing.status || "unknown"))}
        ${metric("Area", String(briefing.area_of_operation || "unknown"))}
      </div>
      <div class="metric-row briefing-metrics">
        ${metric("Next action", String(briefing.next_action || run.next_action || "unknown"))}
        ${metric("Reasons for review", String(arrayValues(briefing.review_reasons).length || run.human_review_reasons.length))}
        ${metric("Unknowns", String(arrayValues(briefing.unknowns).length))}
      </div>
      <div class="metric-row briefing-metrics">
        ${metric("Wrapper risks", String(records(briefing.wrapper_risks).length))}
        ${metric("Citation refs", String(records(briefing.citation_references).length))}
        ${metric("Schema", String(briefing.schema_version || "unknown"))}
      </div>
      ${renderNarrativeSection(narrative, briefing)}
      ${renderClaims("Discoveries", records(briefing.discoveries))}
      ${renderBriefingObjectList("Suspected gaps", records(briefing.suspected_gaps))}
      ${renderBriefingObjectList("Commercial opportunities", records(briefing.commercial_opportunities))}
      ${renderBriefingObjectList("Wrapper risks", records(briefing.wrapper_risks))}
      ${renderBriefingObjectList("Conflicts", records(briefing.conflicts))}
      ${renderTextList("Unknowns", arrayValues(briefing.unknowns))}
      ${renderTextList("Reasons for review", arrayValues(briefing.review_reasons))}
      ${renderPendingQuestions("Validation questions", records(briefing.pending_questions))}
      ${renderBriefingObjectList("Supported recommendations", records(briefing.supported_recommendations))}
      ${renderBriefingObjectList("Hypothesis recommendations", records(briefing.hypothesis_recommendations))}
      ${renderBriefingObjectList("Blocked recommendations", records(briefing.blocked_recommendations))}
      ${renderReferences("Evidence refs", records(briefing.evidence_references), "evidence")}
      ${renderReferences("Citation refs", records(briefing.citation_references), "citation")}
      ${renderTextList("Audit reasons", arrayValues(briefing.audit_reasons))}
    `
  );
}

function renderBriefingReferenceFallback(run, reference) {
  return renderSectionPanel(
    "Briefing",
    `
      <div class="metric-row">
        ${metric("Workflow outcome", run.workflow_outcome)}
        ${metric("Next action", run.next_action)}
        ${metric("Human review reasons", renderReasonCount(run.human_review_reasons))}
      </div>
      ${
        reference
          ? `<ul class="key-list">${objectEntries(reference)
              .map(([key, value]) => `<li><span>${escapeHtml(key)}</span><strong>${escapeHtml(String(value))}</strong></li>`)
              .join("")}</ul>`
          : renderEmptyState("No briefing reference in this run.", "The run may need human review or additional collection.")
      }
      ${renderEmptyState("Full briefing artifact is not loaded.", "This frontend can render executive and human-review briefings when the API record includes the downstream briefing payload.")}
    `
  );
}

function renderBriefingActions(run) {
  return `
    <div class="briefing-actions" aria-label="Briefing actions">
      <button type="button" class="secondary-action" data-copy-briefing="${escapeAttr(run.run_id)}">Copy</button>
      <button type="button" class="secondary-action" data-download-briefing="${escapeAttr(run.run_id)}">Export</button>
      <button type="button" class="secondary-action" data-print-briefing>Print</button>
    </div>
    <pre class="briefing-export-text" data-briefing-export>${escapeHtml(briefingExportText(run))}</pre>
  `;
}

function renderNarrativeSection(narrative, sourceBriefing) {
  if (!narrative || !narrativeMatchesSource(narrative, sourceBriefing)) {
    return `
      <section class="briefing-section narrative-section" aria-label="Deterministic briefing">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Deterministic briefing</p>
            <h4>No LLM narrative is attached to this run.</h4>
          </div>
        </div>
        <p class="section-note">The workspace is showing deterministic briefing fields, typed claims, evidence refs, and citation refs from the backend contract.</p>
      </section>
    `;
  }
  const rejected = narrativeRejected(narrative);
  const response = objectRecord(narrative.llm_response) || {};
  return `
    <section class="briefing-section narrative-section${rejected ? " is-fallback" : ""}" aria-label="LLM narrative">
      <div class="section-heading">
        <div>
          <p class="eyebrow">${rejected ? "LLM narrative fallback" : "LLM narrative"}</p>
          <h4>${rejected ? "Unsafe or malformed narrative was replaced with deterministic content." : "Generated narrative draft from validated briefing claims."}</h4>
        </div>
        <span class="schema-pill">${escapeHtml(String(narrative.schema_version || "briefing_narrative.v1"))}</span>
      </div>
      <div class="briefing-grid">
        ${renderBriefingTextBlock("Technical gap narrative", narrative.technical_gap_narrative)}
        ${renderBriefingTextBlock("Commercial approach narrative", narrative.commercial_approach_narrative)}
      </div>
      ${renderLlmMetadata(response, narrative)}
    </section>
  `;
}

function renderLlmMetadata(response, narrative) {
  const metadata = objectRecord(response.metadata) || {};
  const items = [
    ["Provider", response.provider],
    ["Model", response.model],
    ["Model version", response.model_version],
    ["Finish reason", response.finish_reason],
    ["Source schema", narrative.source_briefing_schema_version],
    ["Source status", narrative.source_briefing_status],
    ["Credential env var", metadata.configured_api_key_env_var],
    ["Adapter", metadata.adapter],
    ["Content rejected", metadata.content_rejected],
    ["Rejection reason", metadata.rejection_reason],
  ].filter(([, value]) => value !== undefined && value !== null && String(value) !== "");
  return `
    <dl class="llm-metadata">
      ${items
        .map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(String(value))}</dd></div>`)
        .join("")}
      <div><dt>Audit</dt><dd>${renderInlineList(arrayValues(narrative.audit_reasons))}</dd></div>
    </dl>
  `;
}

function renderBriefingTextBlock(title, value) {
  const text = String(value || "unknown");
  return `
    <section class="briefing-section">
      <p class="eyebrow">${escapeHtml(title)}</p>
      <p class="briefing-text">${escapeHtml(text)}</p>
    </section>
  `;
}

function renderTextList(title, items) {
  if (!items.length) {
    return renderBriefingEmptySection(title, "No entries in this briefing artifact.");
  }
  return `
    <section class="briefing-section" aria-label="${escapeAttr(title)}">
      <div class="section-heading">
        <div>
          <p class="eyebrow">${escapeHtml(title)}</p>
          <h4>${escapeHtml(title)}</h4>
        </div>
      </div>
      <ul class="briefing-list">
        ${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
      </ul>
    </section>
  `;
}

function renderPendingQuestions(title, questions) {
  if (!questions.length) {
    return renderBriefingEmptySection(title, "No pending questions in this briefing artifact.");
  }
  return `
    <section class="briefing-section" aria-label="${escapeAttr(title)}">
      <div class="section-heading">
        <div>
          <p class="eyebrow">${escapeHtml(title)}</p>
          <h4>${escapeHtml(title)}</h4>
        </div>
      </div>
      <div class="question-list">
        ${questions
          .map(
            (question) => `
              <article class="question-card">
                <span class="status-badge">${escapeHtml(String(question.priority || "unknown"))}</span>
                <strong>${escapeHtml(String(question.field_name || "unknown"))}</strong>
                <p>${escapeHtml(String(question.question || "unknown"))}</p>
                <small>${escapeHtml(String(question.reason || ""))}</small>
              </article>
            `
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderClaims(title, claims) {
  if (!claims.length) {
    return renderBriefingEmptySection(title, "No typed claims in this briefing artifact.");
  }
  return `
    <section class="briefing-section" aria-label="${escapeAttr(title)}">
      <div class="section-heading">
        <div>
          <p class="eyebrow">${escapeHtml(title)}</p>
          <h4>${escapeHtml(title)}</h4>
        </div>
      </div>
      <div class="claim-grid">
        ${claims.map(renderClaim).join("")}
      </div>
    </section>
  `;
}

function renderClaim(claim) {
  const claimType = normalizeClaimType(claim.claim_type);
  const evidenceRefs = records(claim.evidence_references).map(evidenceReferenceLabel);
  const citationRefs = records(claim.citation_references).map(citationReferenceLabel);
  return `
    <article class="claim-card claim-type-${escapeAttr(claimType)}">
      <div class="claim-card-header">
        <span class="claim-pill claim-type-${escapeAttr(claimType)}">${escapeHtml(claimType)}</span>
        <span>${escapeHtml(String(claim.section || "unknown"))} · ${escapeHtml(formatConfidence(claim.confidence))}</span>
      </div>
      <p>${escapeHtml(String(claim.text || "unknown"))}</p>
      ${claim.reason ? `<small>${escapeHtml(String(claim.reason))}</small>` : ""}
      ${renderInlineRefs("Evidence refs", evidenceRefs)}
      ${renderInlineRefs("Citation refs", citationRefs)}
    </article>
  `;
}

function renderBriefingObjectList(title, items) {
  if (!items.length) {
    return renderBriefingEmptySection(title, "No entries in this briefing artifact.");
  }
  return `
    <section class="briefing-section" aria-label="${escapeAttr(title)}">
      <div class="section-heading">
        <div>
          <p class="eyebrow">${escapeHtml(title)}</p>
          <h4>${escapeHtml(title)}</h4>
        </div>
      </div>
      <div class="object-grid">
        ${items.map(renderBriefingObjectCard).join("")}
      </div>
    </section>
  `;
}

function renderBriefingObjectCard(item) {
  const title = String(
    item.title ||
      item.gap_type ||
      item.risk_type ||
      item.opportunity_type ||
      item.nvidia_technology ||
      item.nvidia_program ||
      item.recommendation_type ||
      item.field_name ||
      "item"
  );
  const body = String(
    item.description ||
      item.rationale ||
      item.technical_rationale ||
      item.commercial_rationale ||
      item.value ||
      ""
  );
  const chips = [
    item.severity,
    item.priority,
    item.confidence !== undefined ? formatConfidence(item.confidence) : "",
    item.has_conflict === true ? "conflict" : "",
  ].filter(Boolean);
  const evidenceRefs = [
    ...records(item.evidences),
    ...records(item.evidence_references),
    ...records(item.startup_evidences),
  ].map(evidenceReferenceLabel);
  const citationRefs = [
    ...records(item.nvidia_citations),
    ...records(item.citation_references),
  ].map(citationReferenceLabel);
  const conflicts = arrayValues(item.conflicting_values);
  return `
    <article class="briefing-object-card">
      <div class="claim-card-header">
        <strong>${escapeHtml(title)}</strong>
        <span>${chips.map((chip) => escapeHtml(String(chip))).join(" · ")}</span>
      </div>
      ${body ? `<p>${escapeHtml(body)}</p>` : ""}
      ${conflicts.length ? renderInlineRefs("Conflicting values", conflicts) : ""}
      ${renderInlineRefs("Evidence refs", evidenceRefs)}
      ${renderInlineRefs("Citation refs", citationRefs)}
    </article>
  `;
}

function renderReferences(title, refs, type) {
  if (!refs.length) {
    return renderBriefingEmptySection(title, "No references in this briefing artifact.");
  }
  return `
    <section class="briefing-section" aria-label="${escapeAttr(title)}">
      <div class="section-heading">
        <div>
          <p class="eyebrow">${escapeHtml(title)}</p>
          <h4>${escapeHtml(title)}</h4>
        </div>
      </div>
      <ul class="source-list">
        ${refs
          .map((ref) => {
            const label = type === "citation" ? citationReferenceLabel(ref) : evidenceReferenceLabel(ref);
            const detail = type === "citation" ? ref.document_title || ref.source_url : ref.snippet || ref.source_type;
            return `<li><strong>${escapeHtml(label)}</strong><span>${escapeHtml(String(detail || ""))}</span></li>`;
          })
          .join("")}
      </ul>
    </section>
  `;
}

function renderBriefingEmptySection(title, detail) {
  return `
    <section class="briefing-section" aria-label="${escapeAttr(title)}">
      ${renderEmptyState(`No ${title.toLowerCase()}.`, detail)}
    </section>
  `;
}

function renderInlineRefs(label, refs) {
  if (!refs.length) {
    return "";
  }
  return `
    <dl class="inline-refs">
      <div><dt>${escapeHtml(label)}</dt><dd>${renderInlineList(refs)}</dd></div>
    </dl>
  `;
}

function renderInlineList(items) {
  const values = arrayValues(items);
  if (!values.length) {
    return "none";
  }
  return values.map((item) => `<span>${escapeHtml(item)}</span>`).join("");
}

function selectBriefingArtifact(run, payload, reference) {
  const executive = objectRecord(payload.executive_briefing);
  const humanReview = objectRecord(payload.human_review_briefing);
  const referenceType = String(reference?.briefing_type || "");
  const outcome = String(run.workflow_outcome || payload.workflow_outcome || "");
  if (
    humanReview &&
    (referenceType === "human_review" ||
      outcome.includes("human_review") ||
      String(humanReview.status || "").includes("human_review"))
  ) {
    return { type: "human_review", record: humanReview };
  }
  if (executive && String(executive.status || "") === "ready_for_use") {
    return { type: "executive", record: executive };
  }
  if (humanReview) {
    return { type: "human_review", record: humanReview };
  }
  if (executive) {
    return { type: "executive", record: executive };
  }
  return null;
}

function narrativeMatchesSource(narrative, sourceBriefing) {
  const sourceSchema = String(sourceBriefing.schema_version || "");
  const narrativeSource = String(narrative.source_briefing_schema_version || "");
  return !sourceSchema || !narrativeSource || sourceSchema === narrativeSource;
}

function narrativeRejected(narrative) {
  const metadata = objectRecord(objectRecord(narrative.llm_response)?.metadata) || {};
  return (
    metadata.content_rejected === true ||
    arrayValues(narrative.audit_reasons).some((reason) => reason.includes("llm_narrative_rejected"))
  );
}

export function briefingExportText(run) {
  if (!run) {
    return "No briefing selected.";
  }
  const payload = objectRecord(run.final_payload) || {};
  const reference = objectRecord(run.briefing_reference || payload.briefing_reference);
  const artifact = selectBriefingArtifact(run, payload, reference);
  if (!artifact) {
    const lines = [
      "Briefing reference",
      `Run ID: ${run.run_id}`,
      `Workflow outcome: ${run.workflow_outcome}`,
      `Next action: ${run.next_action}`,
      `Human review reasons: ${arrayValues(run.human_review_reasons).join(", ") || "none"}`,
    ];
    if (reference) {
      lines.push("Reference:");
      for (const [key, value] of objectEntries(reference)) {
        lines.push(`- ${key}: ${String(value)}`);
      }
    }
    return lines.join("\n");
  }
  return artifact.type === "human_review"
    ? humanReviewBriefingExportText(run, artifact.record, objectRecord(payload.briefing_narrative))
    : executiveBriefingExportText(run, artifact.record, objectRecord(payload.briefing_narrative));
}

function executiveBriefingExportText(run, briefing, narrative) {
  const lines = [
    `Executive Briefing: ${String(briefing.startup_identifier || run.startup_identifier)}`,
    `Run ID: ${String(briefing.run_id || run.run_id)}`,
    `Status: ${String(briefing.status || "unknown")}`,
    `Opportunity: ${String(briefing.opportunity || "unknown")}`,
    `Next action: ${String(briefing.next_action || run.next_action || "unknown")}`,
    "",
    "Summary:",
    String(briefing.executive_summary || "unknown"),
    "",
    "Diagnosis:",
    String(briefing.diagnosis || "unknown"),
  ];
  appendExportList(lines, "Risks", arrayValues(briefing.risks));
  appendExportList(lines, "Recommendations", arrayValues(briefing.recommendations));
  appendQuestionsExport(lines, "Pending questions", records(briefing.pending_questions));
  appendClaimsExport(lines, records(briefing.claims));
  appendReferencesExport(lines, "Evidence refs", records(briefing.evidence_references), evidenceReferenceLabel);
  appendReferencesExport(lines, "Citation refs", records(briefing.citation_references), citationReferenceLabel);
  appendNarrativeExport(lines, narrative, briefing);
  return lines.join("\n");
}

function humanReviewBriefingExportText(run, briefing, narrative) {
  const lines = [
    `Human Review Briefing: ${String(briefing.startup_identifier || run.startup_identifier)}`,
    `Run ID: ${String(briefing.run_id || run.run_id)}`,
    `Status: ${String(briefing.status || "unknown")}`,
    `Area: ${String(briefing.area_of_operation || "unknown")}`,
    `Next action: ${String(briefing.next_action || run.next_action || "unknown")}`,
  ];
  appendClaimsExport(lines, records(briefing.discoveries), "Discoveries");
  appendObjectsExport(lines, "Suspected gaps", records(briefing.suspected_gaps));
  appendObjectsExport(lines, "Commercial opportunities", records(briefing.commercial_opportunities));
  appendObjectsExport(lines, "Wrapper risks", records(briefing.wrapper_risks));
  appendObjectsExport(lines, "Conflicts", records(briefing.conflicts));
  appendExportList(lines, "Unknowns", arrayValues(briefing.unknowns));
  appendExportList(lines, "Reasons for review", arrayValues(briefing.review_reasons));
  appendQuestionsExport(lines, "Validation questions", records(briefing.pending_questions));
  appendObjectsExport(lines, "Supported recommendations", records(briefing.supported_recommendations));
  appendObjectsExport(lines, "Hypothesis recommendations", records(briefing.hypothesis_recommendations));
  appendObjectsExport(lines, "Blocked recommendations", records(briefing.blocked_recommendations));
  appendReferencesExport(lines, "Evidence refs", records(briefing.evidence_references), evidenceReferenceLabel);
  appendReferencesExport(lines, "Citation refs", records(briefing.citation_references), citationReferenceLabel);
  appendNarrativeExport(lines, narrative, briefing);
  return lines.join("\n");
}

function appendExportList(lines, title, items) {
  lines.push("", `${title}:`);
  if (!items.length) {
    lines.push("- none");
    return;
  }
  for (const item of items) {
    lines.push(`- ${item}`);
  }
}

function appendQuestionsExport(lines, title, questions) {
  lines.push("", `${title}:`);
  if (!questions.length) {
    lines.push("- none");
    return;
  }
  for (const question of questions) {
    lines.push(`- [${String(question.priority || "unknown")}] ${String(question.field_name || "unknown")}: ${String(question.question || "unknown")} (${String(question.reason || "no reason")})`);
  }
}

function appendClaimsExport(lines, claims, title = "Claims") {
  lines.push("", `${title}:`);
  if (!claims.length) {
    lines.push("- none");
    return;
  }
  for (const claim of claims) {
    lines.push(`- [${normalizeClaimType(claim.claim_type)}] ${String(claim.text || "unknown")}`);
    const evidenceRefs = records(claim.evidence_references).map(evidenceReferenceLabel);
    const citationRefs = records(claim.citation_references).map(citationReferenceLabel);
    if (evidenceRefs.length) {
      lines.push(`  Evidence refs: ${evidenceRefs.join("; ")}`);
    }
    if (citationRefs.length) {
      lines.push(`  Citation refs: ${citationRefs.join("; ")}`);
    }
  }
}

function appendObjectsExport(lines, title, items) {
  lines.push("", `${title}:`);
  if (!items.length) {
    lines.push("- none");
    return;
  }
  for (const item of items) {
    const label = String(
      item.title ||
        item.gap_type ||
        item.risk_type ||
        item.opportunity_type ||
        item.nvidia_technology ||
        item.nvidia_program ||
        item.recommendation_type ||
        item.field_name ||
        "item"
    );
    const detail = String(
      item.description ||
        item.rationale ||
        item.technical_rationale ||
        item.commercial_rationale ||
        item.value ||
        ""
    );
    lines.push(`- ${label}${detail ? `: ${detail}` : ""}`);
  }
}

function appendReferencesExport(lines, title, refs, formatter) {
  lines.push("", `${title}:`);
  if (!refs.length) {
    lines.push("- none");
    return;
  }
  for (const ref of refs) {
    lines.push(`- ${formatter(ref)}`);
  }
}

function appendNarrativeExport(lines, narrative, sourceBriefing) {
  lines.push("", "Narrative:");
  if (!narrative || !narrativeMatchesSource(narrative, sourceBriefing)) {
    lines.push("- No LLM narrative is attached to this run.");
    return;
  }
  lines.push(`- Status: ${narrativeRejected(narrative) ? "fallback" : "accepted"}`);
  lines.push(`- Technical gap narrative: ${String(narrative.technical_gap_narrative || "unknown")}`);
  lines.push(`- Commercial approach narrative: ${String(narrative.commercial_approach_narrative || "unknown")}`);
  const response = objectRecord(narrative.llm_response) || {};
  const metadata = objectRecord(response.metadata) || {};
  lines.push(`- Provider: ${String(response.provider || "unknown")}`);
  lines.push(`- Model: ${String(response.model || "unknown")}`);
  if (metadata.configured_api_key_env_var) {
    lines.push(`- Credential env var: ${String(metadata.configured_api_key_env_var)}`);
  }
  appendExportList(lines, "Narrative audit reasons", arrayValues(narrative.audit_reasons));
}

function evidenceReferenceLabel(ref) {
  const sourceType = String(ref.source_type || "source");
  const url = String(ref.url || "unknown");
  return `${sourceType}: ${url}`;
}

function citationReferenceLabel(ref) {
  const documentId = String(ref.document_id || "unknown");
  const chunkId = String(ref.chunk_id || "unknown");
  const sourceUrl = String(ref.source_url || "");
  return `${documentId}:${chunkId}${sourceUrl ? ` ${sourceUrl}` : ""}`;
}

function normalizeClaimType(value) {
  const claimType = String(value || "unknown").toLowerCase();
  if (["observed", "inferred", "recommended", "unknown"].includes(claimType)) {
    return claimType;
  }
  return "unknown";
}

function formatConfidence(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return "unknown";
  }
  if (numeric <= 1) {
    return `${Math.round(numeric * 100)}%`;
  }
  return String(numeric);
}

function renderProductionSmokes(state) {
  const matrix = state.smokeMatrix;
  if (!matrix) {
    return renderSectionPanel(
      "Production Smokes",
      `
        ${renderEmptyState("Smoke matrix is not loaded.", "The read-only API matrix will populate this view.")}
        <button type="button" class="secondary-action" data-load-smokes>Load matrix</button>
      `
    );
  }
  return renderSectionPanel(
    "Production Smokes",
    `
      <div class="panel-header compact">
        <div>
          <p class="eyebrow">Overall</p>
          <h3>${escapeHtml(matrix.matrix.overall_status)}</h3>
        </div>
        <button type="button" class="secondary-action" data-load-smokes>Refresh</button>
      </div>
      <div class="smoke-table" role="table" aria-label="Production smoke matrix">
        <div class="smoke-row smoke-head" role="row">
          <span role="columnheader">Integration</span>
          <span role="columnheader">Status</span>
          <span role="columnheader">Bottleneck</span>
          <span role="columnheader">Message</span>
        </div>
        ${matrix.matrix.steps
          .map(
            (step) => `
              <div class="smoke-row" role="row">
                <strong role="cell">${escapeHtml(step.title)}</strong>
                <span role="cell" class="status-badge ${statusClass(step.status)}">${escapeHtml(step.status)}</span>
                <span role="cell">${escapeHtml(step.bottleneck)}</span>
                <span role="cell">${escapeHtml(step.message)}</span>
              </div>
            `
          )
          .join("")}
      </div>
    `
  );
}

function renderSectionPanel(title, body) {
  return `
    <section class="panel detail-panel" aria-label="${escapeAttr(title)}">
      <div class="panel-header">
        <div>
          <p class="eyebrow">Workbench</p>
          <h3>${escapeHtml(title)}</h3>
        </div>
      </div>
      ${body}
    </section>
  `;
}

function renderEmptyState(title, detail) {
  return `
    <div class="empty-state">
      <span class="empty-icon" aria-hidden="true"></span>
      <div>
        <h3>${escapeHtml(title)}</h3>
        <p>${escapeHtml(detail)}</p>
      </div>
    </div>
  `;
}

function renderObjectList(title, items) {
  if (!items.length) {
    return renderEmptyState(`No ${title.toLowerCase()}.`, "The API record did not include entries for this section.");
  }
  return `
    <div class="object-list">
      <h4>${escapeHtml(title)}</h4>
      ${items
        .map((item) => {
          const record = item && typeof item === "object" ? /** @type {Record<string, unknown>} */ (item) : {};
          return `
            <article class="object-item">
              <strong>${escapeHtml(String(record.title || record.gap_type || record.risk_type || record.recommendation_type || "item"))}</strong>
              <p>${escapeHtml(String(record.rationale || record.severity || record.priority || ""))}</p>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

function metric(label, value) {
  return `
    <div class="metric-card">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `;
}

function activeSectionLabel(activeSection) {
  return SECTIONS.find((section) => section.id === activeSection)?.label || "Runs";
}

function sectionTitle(activeSection) {
  const labels = {
    runs: "Run command center",
    evidence: "Evidence references",
    assessment: "AI-Native assessment",
    "nvidia-match": "NVIDIA opportunity match",
    briefing: "Briefing workspace",
    "production-smokes": "Production smoke readiness"
  };
  return labels[activeSection] || "Run command center";
}

function statusClass(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized.includes("fail") || normalized.includes("blocked")) {
    return "status-failed";
  }
  if (normalized.includes("complete") || normalized.includes("generated") || normalized.includes("ready")) {
    return "status-completed";
  }
  if (normalized.includes("skip") || normalized.includes("idle")) {
    return "status-idle";
  }
  return "status-running";
}

function artifactCount(run) {
  return objectEntries(run.artifact_references.artifact_locations || {}).length;
}

function renderReasonCount(reasons) {
  return String(Array.isArray(reasons) ? reasons.length : 0);
}

function objectRecord(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return /** @type {Record<string, unknown>} */ (value);
}

function records(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => objectRecord(item))
    .filter((item) => item !== null);
}

function arrayValues(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item || "").trim()).filter(Boolean);
}

function objectEntries(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return [];
  }
  return Object.entries(value);
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function escapeAttr(value) {
  return escapeHtml(value);
}
