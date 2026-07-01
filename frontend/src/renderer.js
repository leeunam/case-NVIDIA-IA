import { RUN_LAUNCHER_DEFAULTS, createRunLauncherForm } from "./run-launcher.js";

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
 * @property {import("./run-launcher.js").RunLauncherForm} launcherForm
 * @property {FrontendRunRecord | null} currentRun
 * @property {string} routeRunId
 * @property {"idle" | "loading" | "loaded" | "not_found" | "failed"} runLoadState
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
  const launcherForm = createRunLauncherForm(overrides.launcherForm || {});
  return {
    activeSection: "runs",
    apiMode: "mock",
    apiBaseUrl: "http://127.0.0.1:8000",
    launcherForm,
    currentRun: null,
    routeRunId: "",
    runLoadState: "idle",
    smokeMatrix: null,
    isBusy: false,
    notice: "",
    errorMessage: "",
    ...overrides,
    launcherForm
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
        ${renderWorkspaceTabs(state)}
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

function renderWorkspaceTabs(state) {
  return `
    <div class="workspace-tabs" role="tablist" aria-label="Run workspace sections">
      ${SECTIONS.map((section) => {
        const active = section.id === state.activeSection;
        return `
          <button class="workspace-tab${active ? " is-active" : ""}" type="button" role="tab" data-section="${escapeAttr(
            section.id
          )}" aria-selected="${active ? "true" : "false"}">
            ${escapeHtml(section.label)}
          </button>
        `;
      }).join("")}
    </div>
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
  const launcherForm = {
    ...RUN_LAUNCHER_DEFAULTS,
    ...(state.launcherForm || {})
  };
  return `
    <section class="run-grid" aria-label="Run workbench">
      ${renderLauncherForm(state, launcherForm)}
      <section class="panel status-panel" aria-label="Run status">
        <div class="panel-header">
          <div>
            <p class="eyebrow">Status</p>
            <h3>${escapeHtml(runStatusTitle(state))}</h3>
          </div>
          <span class="status-badge ${state.currentRun ? statusClass(state.currentRun.status) : statusClass(state.runLoadState)}">
            ${escapeHtml(runStatusBadge(state))}
          </span>
        </div>
        ${state.currentRun ? renderRunSummary(state.currentRun) : renderRunPlaceholder(state)}
      </section>
    </section>
    ${renderStageStrip(state.currentRun)}
  `;
}

function renderLauncherForm(state, form) {
  const startupMode = form.input_mode !== "query";
  const queryMode = form.input_mode === "query";
  return `
    <form class="panel launch-panel" data-run-form>
      <div class="panel-header">
        <div>
          <p class="eyebrow">Launcher</p>
          <h3>Start intelligence run</h3>
        </div>
        <div class="pill-stack">
          <span class="schema-pill">frontend_api_run_create.v1</span>
          <span class="safe-pill">local defaults</span>
        </div>
      </div>

      <fieldset class="mode-fieldset">
        <legend>Input</legend>
        <div class="segmented-control">
          <label class="segment${startupMode ? " is-selected" : ""}">
            <input name="input_mode" value="startup_url" type="radio" data-launcher-autosync ${checked(startupMode)} />
            <span>Startup URL</span>
          </label>
          <label class="segment${queryMode ? " is-selected" : ""}">
            <input name="input_mode" value="query" type="radio" data-launcher-autosync ${checked(queryMode)} />
            <span>Bounded query</span>
          </label>
        </div>
      </fieldset>

      <div class="source-fields">
        <label class="${startupMode ? "" : "is-disabled"}">
          <span>Startup URL</span>
          <input name="startup_url" type="url" placeholder="https://startup.ai/" value="${escapeAttr(
            form.startup_url
          )}" ${disabled(!startupMode)} />
        </label>
        <label class="${queryMode ? "" : "is-disabled"}">
          <span>Bounded query</span>
          <input name="query" type="text" placeholder="Brazilian AI-native startups in health" value="${escapeAttr(
            form.query
          )}" ${disabled(!queryMode)} />
        </label>
      </div>

      <div class="form-grid">
        <label>
          <span>Startup name</span>
          <input name="startup_name" type="text" placeholder="Startup AI" value="${escapeAttr(form.startup_name)}" />
        </label>
        <label class="${queryMode ? "" : "is-disabled"}">
          <span>Candidate limit</span>
          <input name="limit" type="number" min="1" max="5" step="1" value="${escapeAttr(form.limit)}" ${disabled(
            !queryMode
          )} />
        </label>
      </div>

      <details class="advanced-options" open>
        <summary>
          <span>Advanced options</span>
          <strong>safe defaults</strong>
        </summary>
        <div class="form-grid">
          <label>
            <span>Max pages</span>
            <input name="max_pages" type="number" min="1" max="5" step="1" value="${escapeAttr(form.max_pages)}" />
          </label>
          <label>
            <span>Max depth</span>
            <input name="max_depth" type="number" min="0" max="2" step="1" value="${escapeAttr(form.max_depth)}" />
          </label>
          <label>
            <span>Timeout seconds</span>
            <input name="timeout_seconds" type="number" min="5" max="60" step="1" value="${escapeAttr(
              form.timeout_seconds
            )}" />
          </label>
          <label>
            <span>Persistence</span>
            <select name="persistence_mode">
              <option value="json" ${selected(form.persistence_mode === "json")}>json local</option>
              <option value="none" ${selected(form.persistence_mode === "none")}>none</option>
              <option value="postgres" ${selected(form.persistence_mode === "postgres")}>postgres production</option>
              <option value="json-postgres" ${selected(
                form.persistence_mode === "json-postgres"
              )}>json + postgres production</option>
            </select>
          </label>
          <label>
            <span>Retrieval</span>
            <select name="retrieval_mode" data-launcher-autosync>
              <option value="bm25" ${selected(form.retrieval_mode === "bm25")}>BM25 local</option>
              <option value="pgvector" ${selected(form.retrieval_mode === "pgvector")}>pgvector production</option>
            </select>
          </label>
          <label>
            <span>Orchestration</span>
            <select name="orchestration">
              <option value="local" ${selected(form.orchestration === "local")}>local</option>
              <option value="langgraph" ${selected(form.orchestration === "langgraph")}>LangGraph production</option>
            </select>
          </label>
          <label>
            <span>Robots policy</span>
            <select name="robots_policy">
              <option value="conservative" ${selected(form.robots_policy === "conservative")}>conservative</option>
              <option value="permissive-on-error" ${selected(
                form.robots_policy === "permissive-on-error"
              )}>permissive on error</option>
              <option value="off" ${selected(form.robots_policy === "off")}>off production</option>
            </select>
          </label>
          <label>
            <span>Output dir</span>
            <input name="output_dir" type="text" value="${escapeAttr(form.output_dir)}" />
          </label>
          <label class="wide-field">
            <span>NVIDIA corpus path</span>
            <input name="nvidia_corpus_path" type="text" value="${escapeAttr(form.nvidia_corpus_path)}" />
          </label>
          <label class="${form.enable_reranking ? "" : "is-disabled"}">
            <span>Reranker model</span>
            <input name="reranker_model" type="text" placeholder="cross-encoder model or env default" value="${escapeAttr(
              form.reranker_model
            )}" ${disabled(!form.enable_reranking)} />
          </label>
        </div>
        <div class="toggle-row launcher-toggles">
          ${toggleOption("render_js", form.render_js, "Playwright", "production", true)}
          ${toggleOption(
            "enable_search_provider",
            queryMode && form.enable_search_provider,
            "Search provider",
            "production",
            queryMode
          )}
          ${toggleOption("enable_reranking", form.enable_reranking, "Reranking", "pgvector", true, true)}
          ${toggleOption("llm_narrative", form.llm_narrative, "Groq narrative", "production", true)}
        </div>
      </details>

      <button class="primary-action" type="submit" ${state.isBusy ? "disabled aria-busy=\"true\"" : ""}>
        ${state.isBusy ? "Running" : "Start run"}
      </button>
    </form>
  `;
}

function toggleOption(name, checkedValue, label, badge, enabled = true, autosync = false) {
  return `
    <label class="toggle-option${enabled ? "" : " is-disabled"}">
      <input name="${escapeAttr(name)}" type="checkbox" ${checked(Boolean(checkedValue))} ${disabled(!enabled)} ${
        autosync ? "data-launcher-autosync" : ""
      } />
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(badge)}</strong>
    </label>
  `;
}

function checked(value) {
  return value ? "checked" : "";
}

function selected(value) {
  return value ? "selected" : "";
}

function disabled(value) {
  return value ? "disabled" : "";
}

function renderRunSummary(run) {
  return `
    <div class="metric-row compact-metrics">
      ${metric("Workflow outcome", run.workflow_outcome)}
      ${metric("Result", resultType(run))}
      ${metric("Next action", run.next_action)}
    </div>
    <dl class="summary-list">
      <div><dt>Startup</dt><dd>${escapeHtml(run.startup_identifier)}</dd></div>
      <div><dt>Run ID</dt><dd>${escapeHtml(run.run_id)}</dd></div>
      <div><dt>Status</dt><dd>${escapeHtml(run.status)}</dd></div>
      <div><dt>Next action</dt><dd>${escapeHtml(run.next_action)}</dd></div>
      <div><dt>Created</dt><dd>${escapeHtml(run.created_at || "unknown")}</dd></div>
      <div><dt>Human review reasons</dt><dd>${renderReasonCount(run.human_review_reasons)}</dd></div>
      <div><dt>Errors</dt><dd>${String(run.errors.length)}</dd></div>
    </dl>
    ${renderBranchDecisionList(run.branch_decisions)}
    ${renderPersistenceReferences(run.artifact_references.persistence_references || [])}
    ${renderAuditableErrors(run.errors)}
    <div class="status-actions">
      <button type="button" class="secondary-action" data-refresh-run="${escapeAttr(run.run_id)}">Refresh</button>
    </div>
  `;
}

function renderRunPlaceholder(state) {
  if (state.runLoadState === "loading") {
    return renderEmptyState(
      "Loading run context.",
      `Fetching ${state.routeRunId || "the selected run"} from the API without starting a new run.`
    );
  }
  if (state.runLoadState === "not_found") {
    return renderEmptyState(
      "Run not found.",
      `${state.routeRunId || "The requested run"} is not available from the configured API.`
    );
  }
  if (state.runLoadState === "failed") {
    return renderEmptyState(
      "Run status could not be loaded.",
      "Check the API mode, base URL, and run identifier, then refresh the workspace."
    );
  }
  return renderEmptyState("Run launcher is ready.", "Submit a URL or bounded query to populate the workbench.");
}

function runStatusTitle(state) {
  if (state.currentRun) {
    return state.currentRun.startup_identifier;
  }
  if (state.routeRunId) {
    return `Run ${state.routeRunId}`;
  }
  return "No active run";
}

function runStatusBadge(state) {
  if (state.currentRun) {
    return state.currentRun.workflow_outcome;
  }
  if (state.runLoadState === "loading") {
    return "loading";
  }
  if (state.runLoadState === "not_found") {
    return "not found";
  }
  if (state.runLoadState === "failed") {
    return "load failed";
  }
  return "waiting";
}

function resultType(run) {
  if (String(run.status).toLowerCase().includes("fail") || run.workflow_outcome === "failed_with_auditable_error") {
    return "failed_with_auditable_error";
  }
  const reference =
    run.briefing_reference && typeof run.briefing_reference === "object"
      ? /** @type {Record<string, unknown>} */ (run.briefing_reference)
      : {};
  const briefingType = String(reference.briefing_type || "");
  if (briefingType === "executive") {
    return "executive briefing";
  }
  if (briefingType === "human_review" || run.workflow_outcome === "human_review_requested") {
    return "human review";
  }
  return "unknown";
}

function renderBranchDecisionList(items) {
  const decisions = records(items);
  return `
    <div class="audit-section">
      <h4>Branch decisions</h4>
      ${
        decisions.length
          ? decisions
              .map(
                (decision) => `
                  <article class="audit-item">
                    <strong>${escapeHtml(String(decision.branch_name || "unknown_branch"))}</strong>
                    <dl class="audit-grid">
                      <div><dt>Next action</dt><dd>${escapeHtml(String(decision.next_action || "unknown"))}</dd></div>
                      <div><dt>Reason</dt><dd>${escapeHtml(String(decision.audit_reason || "unknown"))}</dd></div>
                    </dl>
                  </article>
                `
              )
              .join("")
          : `<p class="muted-line">No branch decisions were included in this run record.</p>`
      }
    </div>
  `;
}

function renderPersistenceReferences(items) {
  const references = records(items);
  return `
    <div class="audit-section">
      <h4>Persistence references</h4>
      ${
        references.length
          ? references
              .map(
                (reference) => `
                  <article class="audit-item">
                    <strong>${escapeHtml(String(reference.artifact_kind || "artifact"))}</strong>
                    <dl class="audit-grid">
                      <div><dt>Storage</dt><dd>${escapeHtml(String(reference.storage || "unknown"))}</dd></div>
                      <div><dt>Reference</dt><dd>${escapeHtml(String(reference.reference || "unknown"))}</dd></div>
                      <div><dt>Startup</dt><dd>${escapeHtml(String(reference.startup_identifier || "unknown"))}</dd></div>
                    </dl>
                  </article>
                `
              )
              .join("")
          : `<p class="muted-line">No persistence references were included in this run record.</p>`
      }
    </div>
  `;
}

function renderAuditableErrors(items) {
  const errors = records(items);
  return `
    <div class="audit-section">
      <h4>Auditable errors</h4>
      ${
        errors.length
          ? errors
              .map(
                (error) => `
                  <article class="audit-item error-item">
                    <strong>${escapeHtml(String(error.step || "unknown_step"))}</strong>
                    <dl class="audit-grid">
                      <div><dt>Type</dt><dd>${escapeHtml(String(error.error_type || error.type || "unknown"))}</dd></div>
                      <div><dt>Message</dt><dd>${escapeHtml(String(error.message || "unknown"))}</dd></div>
                      <div><dt>Reason</dt><dd>${escapeHtml(String(error.audit_reason || error.reason || "unknown"))}</dd></div>
                    </dl>
                  </article>
                `
              )
              .join("")
          : `<p class="muted-line">No auditable errors were recorded.</p>`
      }
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
      ${renderPersistenceReferences(persistence)}
      ${renderAuditableErrors(run.errors)}
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
  const reference =
    run.briefing_reference && typeof run.briefing_reference === "object"
      ? /** @type {Record<string, unknown>} */ (run.briefing_reference)
      : null;
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
    `
  );
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
    briefing: "Executive briefing",
    "production-smokes": "Production smoke readiness"
  };
  return labels[activeSection] || "Run command center";
}

function statusClass(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized.includes("fail") || normalized.includes("blocked") || normalized.includes("not_found")) {
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

function objectEntries(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return [];
  }
  return Object.entries(value);
}

function records(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item) => item && typeof item === "object" && !Array.isArray(item))
    .map((item) => /** @type {Record<string, unknown>} */ (item));
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
