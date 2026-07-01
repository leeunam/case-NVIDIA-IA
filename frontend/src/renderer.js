import { RUN_LAUNCHER_DEFAULTS, createRunLauncherForm } from "./run-launcher.js";

export const SECTIONS = [
  { id: "runs", label: "Runs" },
  { id: "evidence", label: "Evidence" },
  { id: "assessment", label: "Assessment" },
  { id: "nvidia-match", label: "NVIDIA Match" },
  { id: "briefing", label: "Briefing" },
  { id: "production-smokes", label: "Production Smokes" }
];

const PROFILE_FIELD_ORDER = [
  "company_name",
  "official_site",
  "company_summary",
  "sector",
  "product",
  "customers",
  "funding",
  "founders",
  "technologies_used",
  "ai_signals",
  "location"
];
const LOW_TEXT_THRESHOLD = 80;

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
  const payload = evidencePayload(run);
  const profiles = records(payload.profiles);
  const evidenceGroupsByProfile = objectRecord(payload.evidence_groups_by_profile);
  const collectionResults = collectionResultsFromPayload(payload.collected_pages_by_candidate);
  const quality = objectRecord(payload.quality_summary) || objectRecord(payload.collection_quality);
  const locations = objectEntries(run.artifact_references.artifact_locations || {});
  const persistence = Array.isArray(run.artifact_references.persistence_references)
    ? run.artifact_references.persistence_references
    : [];
  const hasRichEvidence = profiles.length || collectionResults.length || quality;
  if (!hasRichEvidence) {
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

  const groupCount = objectEntries(evidenceGroupsByProfile).reduce(
    (count, [, value]) => count + records(value).length,
    0
  );
  const pageStats = collectionPageStats(collectionResults);
  return renderSectionPanel(
    "Evidence",
    `
      <div class="evidence-term-note">
        <div>
          <p class="eyebrow">Terminology</p>
          <h3>Startup-side Evidence</h3>
          <p>Public startup pages, snippets, collection errors, and profile field support are Evidence. NVIDIA-side Citation records stay in the NVIDIA Match view.</p>
        </div>
      </div>
      <div class="metric-row evidence-metrics">
        ${metric("Startup profiles", String(profiles.length))}
        ${metric("Field evidence groups", String(groupCount))}
        ${metric("Collection errors", String(pageStats.errorCount + run.errors.length))}
      </div>
      ${renderCollectionQualityEvidence(quality, profiles, collectionResults)}
      ${renderStartupProfilesEvidence(profiles, evidenceGroupsByProfile)}
      ${renderCollectedPagesEvidence(collectionResults)}
      ${renderRobotsPolicyEvidence(collectionResults, run)}
      ${renderArtifactEvidenceReferences(locations, persistence)}
      ${renderPersistenceReferences(persistence)}
      ${renderAuditableErrors(run.errors)}
    `
  );
}

function renderCollectionQualityEvidence(quality, profiles, collectionResults) {
  const profileStats = profileFieldStats(profiles);
  const pageStats = collectionPageStats(collectionResults);
  const qualityRecord = quality || {};
  const unknownRate = numericValue(qualityRecord.unknown_field_rate, profileStats.unknownRate);
  const completeness = numericValue(qualityRecord.minimum_profile_complete_rate, 1 - unknownRate);
  const readiness = readinessValue(qualityRecord);
  const reasons = readinessReasons(qualityRecord);
  const unknownFields = unknownFieldsFromQuality(qualityRecord, profiles);
  const strategies = pageStats.extractionStrategies.length ? pageStats.extractionStrategies.join(", ") : "unknown";
  return `
    <section class="evidence-section" aria-label="Collection quality">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Evidence quality</p>
          <h4>Collection quality</h4>
        </div>
        <span class="status-badge ${statusClass(readiness)}">${escapeHtml(readiness)}</span>
      </div>
      <div class="metric-row evidence-quality-grid">
        ${metric("Completeness", formatPercent(completeness))}
        ${metric("Unknown rate", formatPercent(unknownRate))}
        ${metric("Empty/low-text pages", String(pageStats.lowTextCount))}
      </div>
      <dl class="evidence-definition-list">
        <div><dt>Readiness</dt><dd>${escapeHtml(readiness)}</dd></div>
        <div><dt>Readiness/blocking reasons</dt><dd>${renderInlineList(reasons)}</dd></div>
        <div><dt>Extraction strategies</dt><dd>${escapeHtml(strategies)}</dd></div>
        <div><dt>Collected pages</dt><dd>${escapeHtml(String(pageStats.pageCount))}</dd></div>
      </dl>
      ${renderUnknownFieldSummary(unknownFields)}
      ${renderSourceQualitySummary(records(qualityRecord.source_success_rates))}
    </section>
  `;
}

function renderStartupProfilesEvidence(profiles, evidenceGroupsByProfile) {
  if (!profiles.length) {
    return `
      <section class="evidence-section" aria-label="Startup Profile fields">
        ${renderEmptyState("No Startup Profile fields were included.", "The run did not expose profile extraction artifacts.")}
      </section>
    `;
  }
  return `
    <section class="evidence-section" aria-label="Startup Profile fields">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Startup Profile</p>
          <h4>Fields and field-level Evidence</h4>
        </div>
      </div>
      <div class="profile-evidence-list">
        ${profiles
          .map((profile, index) => {
            const fields = profileFields(profile);
            const groups = evidenceGroupsForProfile(profile, evidenceGroupsByProfile, index);
            return `
              <article class="profile-evidence-card">
                <div class="profile-card-header">
                  <div>
                    <p class="eyebrow">Profile ${String(index + 1)}</p>
                    <h3>${escapeHtml(profileDisplayName(profile))}</h3>
                  </div>
                  <span class="schema-pill">${escapeHtml(String(profile.schema_version || "startup_profile.v1"))}</span>
                </div>
                <div class="profile-field-grid">
                  ${fields.map(([fieldName, field]) => renderProfileFieldEvidence(fieldName, field)).join("")}
                </div>
                ${renderFieldEvidenceGroups(groups, fields)}
              </article>
            `;
          })
          .join("")}
      </div>
    </section>
  `;
}

function renderProfileFieldEvidence(fieldName, field) {
  const record = objectRecord(field) || {};
  const source = String(record.claim_source || "unknown");
  const value = String(record.value || "unknown");
  const evidences = records(record.evidences);
  const isUnknown = value === "unknown" || source === "unknown";
  return `
    <article class="profile-field-item ${isUnknown ? "is-unknown" : ""}">
      <div class="field-title-row">
        <h4>${escapeHtml(fieldName)}</h4>
        <span class="status-badge evidence-source-${escapeAttr(sourceClass(source))}">${escapeHtml(source)}</span>
      </div>
      <p class="field-value">${escapeHtml(value)}</p>
      ${
        evidences.length
          ? renderEvidenceSnippetList(evidences, "Linked evidence snippets")
          : `<p class="insufficient-line">insufficient evidence: missing_field_evidence:${escapeHtml(fieldName)}</p>`
      }
    </article>
  `;
}

function renderFieldEvidenceGroups(groups, fields) {
  const unknowns = fields
    .filter(([, field]) => {
      const record = objectRecord(field) || {};
      return String(record.value || "unknown") === "unknown" || String(record.claim_source || "unknown") === "unknown";
    })
    .map(([fieldName]) => fieldName);
  return `
    <div class="field-evidence-groups">
      <div class="section-heading compact">
        <div>
          <p class="eyebrow">Field evidence groups</p>
          <h4>Supporting snippets, source URLs, and conflicts</h4>
        </div>
      </div>
      ${
        groups.length
          ? groups.map((group) => renderFieldEvidenceGroup(group)).join("")
          : renderEmptyState("No field evidence groups were included.", "Profile fields may still contain direct Evidence snippets.")
      }
      ${renderUnknownFields(unknowns)}
    </div>
  `;
}

function renderFieldEvidenceGroup(group) {
  const evidences = records(group.evidences);
  const hasConflict = Boolean(group.has_conflict);
  const conflictingValues = arrayValues(group.conflicting_values);
  const insufficientReasons = arrayValues(group.insufficient_evidence_reasons);
  return `
    <article class="field-evidence-group ${hasConflict ? "has-conflict" : ""}">
      <div class="field-title-row">
        <h4>${escapeHtml(String(group.field_name || "unknown_field"))}</h4>
        <span class="status-badge ${hasConflict ? "status-failed" : "status-completed"}">${hasConflict ? "Conflict" : "Supported"}</span>
      </div>
      <dl class="evidence-definition-list compact">
        <div><dt>Value</dt><dd>${escapeHtml(String(group.value || "unknown"))}</dd></div>
        ${
          hasConflict
            ? `<div><dt>Conflicting values</dt><dd>${renderInlineList(conflictingValues)}</dd></div>`
            : ""
        }
        ${
          insufficientReasons.length
            ? `<div><dt>Insufficient evidence reasons</dt><dd>${renderInlineList(insufficientReasons)}</dd></div>`
            : ""
        }
      </dl>
      ${
        evidences.length
          ? renderEvidenceSnippetList(evidences, "Supporting snippets and source URL")
          : `<p class="insufficient-line">insufficient evidence: no_supporting_snippets</p>`
      }
    </article>
  `;
}

function renderCollectedPagesEvidence(collectionResults) {
  const pages = collectionResults.flatMap((result) =>
    result.pages.map((page) => ({
      ...page,
      candidate_key: result.candidateKey
    }))
  );
  const errors = collectionResults.flatMap((result) =>
    result.errors.map((error) => ({
      ...error,
      candidate_key: result.candidateKey
    }))
  );
  return `
    <section class="evidence-section" aria-label="Collected pages">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Collection</p>
          <h4>Collected pages</h4>
        </div>
        <span class="schema-pill">${escapeHtml(String(pages.length))} pages</span>
      </div>
      ${
        pages.length
          ? `<div class="collected-page-list">${pages.map((page) => renderCollectedPage(page)).join("")}</div>`
          : renderEmptyState("No collected pages were available.", "Collection errors and policy decisions may explain the gap.")
      }
      ${renderCollectionErrors(errors)}
    </section>
  `;
}

function renderCollectedPage(page) {
  const url = String(page.url || "unknown");
  const textLength = pageTextLength(page);
  return `
    <article class="collected-page-item">
      <div class="field-title-row">
        <h4>${escapeHtml(String(page.title || "unknown"))}</h4>
        <span class="status-badge ${statusClass(String(page.status_code || ""))}">${escapeHtml(String(page.status_code || "unknown"))}</span>
      </div>
      <a class="source-link" href="${escapeAttr(safeHref(url))}" target="_blank" rel="noreferrer">${escapeHtml(url)}</a>
      <dl class="evidence-definition-list compact">
        <div><dt>Candidate</dt><dd>${escapeHtml(String(page.candidate_key || "unknown"))}</dd></div>
        <div><dt>Extraction strategy</dt><dd>${escapeHtml(String(page.extraction_strategy || "unknown"))}</dd></div>
        <div><dt>needs_js_rendering</dt><dd>${escapeHtml(String(Boolean(page.needs_js_rendering)))}</dd></div>
        <div><dt>Text length</dt><dd>${escapeHtml(String(textLength))}</dd></div>
      </dl>
    </article>
  `;
}

function renderCollectionErrors(errors) {
  return `
    <div class="audit-section">
      <h4>Collection errors</h4>
      ${
        errors.length
          ? errors
              .map(
                (error) => `
                  <article class="audit-item error-item">
                    <strong>${escapeHtml(String(error.error_type || error.type || "unknown_error"))}</strong>
                    <dl class="audit-grid">
                      <div><dt>URL</dt><dd>${renderSourceUrl(String(error.url || "unknown"))}</dd></div>
                      <div><dt>Message</dt><dd>${escapeHtml(String(error.message || "unknown"))}</dd></div>
                      <div><dt>Category</dt><dd>${escapeHtml(String(error.error_category || error.audit_reason || "unknown"))}</dd></div>
                      <div><dt>Status</dt><dd>${escapeHtml(String(error.status_code ?? "unknown"))}</dd></div>
                    </dl>
                  </article>
                `
              )
              .join("")
          : `<p class="muted-line">No collection errors were recorded.</p>`
      }
    </div>
  `;
}

function renderRobotsPolicyEvidence(collectionResults, run) {
  const errors = collectionResults.flatMap((result) => result.errors);
  const policyErrors = errors.filter((error) => {
    const category = String(error.error_category || error.audit_reason || error.error_type || "").toLowerCase();
    return (
      category.includes("robots") ||
      category.includes("policy") ||
      category.includes("blocked") ||
      category.includes("login") ||
      category.includes("manual")
    );
  });
  const robotsPolicy = String(run.options?.robots_policy || run.final_payload?.options?.robots_policy || "unknown");
  return `
    <section class="evidence-section" aria-label="Robots and policy decisions">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Collection policy</p>
          <h4>Robots and policy decisions</h4>
        </div>
        <span class="schema-pill">robots: ${escapeHtml(robotsPolicy)}</span>
      </div>
      ${
        policyErrors.length
          ? policyErrors
              .map(
                (error) => `
                  <article class="audit-item">
                    <strong>${escapeHtml(String(error.error_category || error.error_type || "policy_decision"))}</strong>
                    <dl class="audit-grid">
                      <div><dt>URL</dt><dd>${renderSourceUrl(String(error.url || "unknown"))}</dd></div>
                      <div><dt>Decision</dt><dd>${escapeHtml(String(error.message || "unknown"))}</dd></div>
                    </dl>
                  </article>
                `
              )
              .join("")
          : `<p class="muted-line">No robots or scraping policy blocks were recorded for this run.</p>`
      }
    </section>
  `;
}

function renderArtifactEvidenceReferences(locations, persistence) {
  return `
    <section class="evidence-section" aria-label="Evidence artifact references">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Artifacts</p>
          <h4>Evidence artifact references</h4>
        </div>
      </div>
      <div class="metric-row evidence-quality-grid">
        ${metric("Artifact locations", String(locations.length))}
        ${metric("Persistence references", String(persistence.length))}
        ${metric("Raw evidence files", String(locations.filter(([key]) => String(key).includes("raw")).length))}
      </div>
      ${
        locations.length
          ? `<ul class="key-list">${locations
              .map(([key, value]) => `<li><span>${escapeHtml(key)}</span><strong>${escapeHtml(String(value))}</strong></li>`)
              .join("")}</ul>`
          : renderEmptyState("No artifact references in this run.", "The API record did not include artifact locations.")
      }
    </section>
  `;
}

function renderUnknownFieldSummary(unknownFields) {
  if (!unknownFields.length) {
    return `<p class="muted-line">No unknown Startup Profile fields were reported.</p>`;
  }
  return `
    <div class="unknown-field-strip">
      <h4>Unknown fields</h4>
      <div class="chip-list">
        ${unknownFields
          .map((field) => `<span class="unknown-chip">${escapeHtml(field.name)} (${escapeHtml(String(field.count))})</span>`)
          .join("")}
      </div>
    </div>
  `;
}

function renderUnknownFields(fieldNames) {
  if (!fieldNames.length) {
    return "";
  }
  return `
    <div class="unknown-field-strip">
      <h4>Unknown fields</h4>
      <ul class="reason-list">
        ${fieldNames
          .map((fieldName) => `<li>${escapeHtml(fieldName)}: missing_field_evidence:${escapeHtml(fieldName)}</li>`)
          .join("")}
      </ul>
    </div>
  `;
}

function renderSourceQualitySummary(items) {
  if (!items.length) {
    return "";
  }
  return `
    <div class="source-quality-list">
      <h4>Source quality</h4>
      ${items
        .map(
          (item) => `
            <article class="source-quality-item">
              <strong>${escapeHtml(String(item.source_name || "unknown_source"))}</strong>
              <dl class="evidence-definition-list compact">
                <div><dt>Attempts</dt><dd>${escapeHtml(String(item.attempts ?? "unknown"))}</dd></div>
                <div><dt>Successes</dt><dd>${escapeHtml(String(item.successes ?? "unknown"))}</dd></div>
                <div><dt>Failures</dt><dd>${escapeHtml(String(item.failures ?? "unknown"))}</dd></div>
                <div><dt>Success rate</dt><dd>${escapeHtml(formatPercent(numericValue(item.success_rate, 0)))}</dd></div>
              </dl>
            </article>
          `
        )
        .join("")}
    </div>
  `;
}

function renderEvidenceSnippetList(evidences, title) {
  return `
    <div class="snippet-stack">
      <p class="snippet-title">${escapeHtml(title)}</p>
      ${evidences.map((evidence) => renderEvidenceSnippet(evidence)).join("")}
    </div>
  `;
}

function renderEvidenceSnippet(evidence) {
  const url = String(evidence.url || "unknown");
  return `
    <article class="snippet-item">
      <p>${escapeHtml(String(evidence.snippet || "unknown"))}</p>
      <dl class="evidence-definition-list compact">
        <div><dt>source URL</dt><dd>${renderSourceUrl(url)}</dd></div>
        <div><dt>Title</dt><dd>${escapeHtml(String(evidence.title || "unknown"))}</dd></div>
        <div><dt>Source type</dt><dd>${escapeHtml(String(evidence.source_type || "unknown"))}</dd></div>
      </dl>
    </article>
  `;
}

function renderSourceUrl(url) {
  return `<a class="source-link" href="${escapeAttr(safeHref(url))}" target="_blank" rel="noreferrer">${escapeHtml(url)}</a>`;
}

function renderAssessment(state) {
  const run = state.currentRun;
  const payload = objectRecord(run?.final_payload) || {};
  const assessment = objectRecord(payload.ai_native_assessment);
  if (!assessment || typeof assessment !== "object") {
    return renderSectionPanel("Assessment", renderEmptyState("No assessment payload yet.", "The API record has no AI-Native Assessment details."));
  }
  const gapSpace = objectRecord(payload.gap_space_assessment);
  const humanReview = firstRecord(
    payload.human_review_briefing,
    payload.briefing_narrative,
    payload.executive_briefing
  );
  const criteria = records(assessment.criteria_results);
  const signals = records(assessment.positive_signals);
  const gaps = records(assessment.technical_gaps);
  const risks = records(assessment.wrapper_dependency_risks);
  const commercialOpportunities = commercialOpportunitiesFromPayload(payload, gapSpace, humanReview);
  const reviewReasons = assessmentReviewReasons(run, assessment, gapSpace, humanReview, payload);
  const pendingQuestions = assessmentPendingQuestions(assessment, payload, humanReview);
  return renderSectionPanel(
    "Assessment",
    `
      ${renderAssessmentOverview(assessment, criteria, gaps, risks)}
      ${renderAssessmentEvidenceContext(assessment, reviewReasons)}
      ${renderAssessmentCriteria(criteria)}
      ${renderPositiveSignals(signals)}
      ${renderAssessmentGaps(gaps)}
      ${renderWrapperRisks(risks)}
      ${renderCommercialOpportunities(commercialOpportunities)}
      ${renderAssessmentHumanReview(assessment, reviewReasons, pendingQuestions)}
    `
  );
}

function renderAssessmentOverview(assessment, criteria, gaps, risks) {
  const readiness = assessmentReadiness(assessment);
  const opportunitySignal = String(assessment.nvidia_opportunity_urgency || assessment.opportunity_signal || "unknown");
  return `
    <div class="metric-row assessment-metrics">
      ${metric("Classification", String(assessment.classification || "unknown"))}
      ${metric("Confidence", formatConfidence(assessment.confidence))}
      ${metric("Opportunity signal", opportunitySignal)}
    </div>
    <div class="metric-row assessment-metrics">
      ${metric("Readiness", readiness)}
      ${metric("Criteria", String(criteria.length))}
      ${metric("Wrapper/API signals", String(risks.length))}
    </div>
    <div class="metric-row assessment-metrics">
      ${metric("Technical gaps", String(gaps.length))}
      ${metric("Evidence references", String(assessmentEvidenceCount(assessment)))}
      ${metric("Schema", String(assessment.schema_version || "unknown"))}
    </div>
  `;
}

function renderAssessmentEvidenceContext(assessment, reviewReasons) {
  const diagnostic = objectRecord(assessment.diagnostic_quality) || {};
  const insufficientFields = arrayValues(assessment.insufficient_evidence_fields);
  return `
    <section class="assessment-section" aria-label="Assessment evidence context">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Evidence context</p>
          <h4>Diagnostic inputs and support</h4>
        </div>
        ${renderEvidenceContextButton("assessment-overview")}
      </div>
      <dl class="evidence-definition-list">
        <div><dt>Company</dt><dd>${escapeHtml(String(assessment.company_name || "unknown"))}</dd></div>
        <div><dt>Diagnostic quality</dt><dd>${escapeHtml(assessmentReadiness(assessment))}</dd></div>
        <div><dt>Human review required</dt><dd>${escapeHtml(String(Boolean(diagnostic.requires_human_review)))}</dd></div>
        <div><dt>Diagnostic reasons</dt><dd>${renderInlineList(reviewReasons.length ? reviewReasons : diagnosticReasons(assessment))}</dd></div>
        <div><dt>Insufficient evidence fields</dt><dd>${renderInlineList(insufficientFields)}</dd></div>
      </dl>
    </section>
  `;
}

function renderAssessmentCriteria(criteria) {
  return `
    <section class="assessment-section" aria-label="Criteria results">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Criteria results</p>
          <h4>Passed, failed, unknown, and conflict conditions</h4>
        </div>
      </div>
      ${
        criteria.length
          ? `<div class="assessment-card-list">${criteria.map((criterion) => renderCriterionResult(criterion)).join("")}</div>`
          : renderEmptyState("No criteria results.", "The assessment payload did not include criterion-level diagnostics.")
      }
    </section>
  `;
}

function renderCriterionResult(criterion) {
  const status = String(criterion.status || "unknown");
  const evidences = evidenceRecordsFrom(criterion);
  return `
    <article class="assessment-card ${status === "conflict" ? "has-conflict" : ""}">
      <div class="field-title-row">
        <h4>${escapeHtml(String(criterion.criterion || "unknown_criterion"))}</h4>
        <span class="status-badge ${assessmentStatusClass(status)}">${escapeHtml(assessmentStatusLabel(status))}</span>
      </div>
      <dl class="evidence-definition-list compact">
        <div><dt>Status</dt><dd>${escapeHtml(status)}</dd></div>
        <div><dt>Confidence</dt><dd>${escapeHtml(formatConfidence(criterion.confidence))}</dd></div>
        <div><dt>Rationale</dt><dd>${escapeHtml(String(criterion.rationale || "unknown"))}</dd></div>
      </dl>
      ${renderAssessmentEvidenceBlock(evidences, "Criterion evidence", String(criterion.criterion || "criterion"))}
    </article>
  `;
}

function renderPositiveSignals(signals) {
  return `
    <section class="assessment-section" aria-label="Positive signals">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Positive signals</p>
          <h4>Observed or inferred AI-native indicators</h4>
        </div>
      </div>
      ${
        signals.length
          ? `<div class="assessment-card-list">${signals.map((signal) => renderPositiveSignal(signal)).join("")}</div>`
          : renderEmptyState("No positive AI-native signals.", "The assessment payload did not include supported positive signals.")
      }
    </section>
  `;
}

function renderPositiveSignal(signal) {
  const evidences = evidenceRecordsFrom(signal);
  return `
    <article class="assessment-card">
      <div class="field-title-row">
        <h4>${escapeHtml(String(signal.signal_type || "unknown_signal"))}</h4>
        <span class="status-badge status-completed">Supported signal</span>
      </div>
      <dl class="evidence-definition-list compact">
        <div><dt>Description</dt><dd>${escapeHtml(String(signal.description || "unknown"))}</dd></div>
        <div><dt>Confidence</dt><dd>${escapeHtml(formatConfidence(signal.confidence))}</dd></div>
      </dl>
      ${renderAssessmentEvidenceBlock(evidences, "Signal evidence", String(signal.signal_type || "signal"))}
    </article>
  `;
}

function renderAssessmentGaps(gaps) {
  return `
    <section class="assessment-section" aria-label="Technical gaps">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Technical gaps</p>
          <h4>Gap hypotheses tied to startup-side evidence</h4>
        </div>
      </div>
      ${
        gaps.length
          ? `<div class="assessment-card-list">${gaps.map((gap) => renderAssessmentGap(gap)).join("")}</div>`
          : renderEmptyState("No technical gaps.", "The assessment payload did not include supported or hypothesized gaps.")
      }
    </section>
  `;
}

function renderAssessmentGap(gap) {
  const evidences = evidenceRecordsFrom(gap);
  return `
    <article class="assessment-card">
      <div class="field-title-row">
        <h4>${escapeHtml(String(gap.gap_type || "unknown_gap"))}</h4>
        <span class="status-badge ${severityClass(gap.severity)}">${escapeHtml(String(gap.severity || "unknown"))}</span>
      </div>
      <dl class="evidence-definition-list compact">
        <div><dt>Type</dt><dd>${escapeHtml(String(gap.gap_type || "unknown"))}</dd></div>
        <div><dt>Description</dt><dd>${escapeHtml(String(gap.description || gap.rationale || "unknown"))}</dd></div>
        <div><dt>Severity</dt><dd>${escapeHtml(String(gap.severity || "unknown"))}</dd></div>
        <div><dt>Confidence</dt><dd>${escapeHtml(formatConfidence(gap.confidence))}</dd></div>
        <div><dt>Hypothesis</dt><dd>${escapeHtml(String(Boolean(gap.is_hypothesis)))}</dd></div>
      </dl>
      ${renderAssessmentEvidenceBlock(evidences, "Gap evidence", String(gap.gap_type || "gap"))}
    </article>
  `;
}

function renderWrapperRisks(risks) {
  return `
    <section class="assessment-section" aria-label="Wrapper/API-dependency signals">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Wrapper/API-dependency signals</p>
          <h4>Dependency risks and validation status</h4>
        </div>
      </div>
      ${
        risks.length
          ? `<div class="assessment-card-list">${risks.map((risk) => renderWrapperRisk(risk)).join("")}</div>`
          : renderEmptyState("No wrapper/API-dependency signals.", "The assessment payload did not include wrapper risk diagnostics.")
      }
    </section>
  `;
}

function renderWrapperRisk(risk) {
  const evidences = evidenceRecordsFrom(risk);
  const shouldValidate = Boolean(risk.is_hypothesis) || !evidences.length || String(risk.severity || "") === "high";
  return `
    <article class="assessment-card ${String(risk.severity || "") === "high" ? "has-conflict" : ""}">
      <div class="field-title-row">
        <h4>${escapeHtml(String(risk.risk_type || "unknown_risk"))}</h4>
        <span class="status-badge ${severityClass(risk.severity)}">${escapeHtml(String(risk.severity || "unknown"))}</span>
      </div>
      <dl class="evidence-definition-list compact">
        <div><dt>Signal</dt><dd>${escapeHtml(String(risk.risk_type || "unknown"))}</dd></div>
        <div><dt>Severity</dt><dd>${escapeHtml(String(risk.severity || "unknown"))}</dd></div>
        <div><dt>Confidence</dt><dd>${escapeHtml(formatConfidence(risk.confidence))}</dd></div>
        <div><dt>Rationale</dt><dd>${escapeHtml(String(risk.rationale || "unknown"))}</dd></div>
        <div><dt>Hypothesis</dt><dd>${escapeHtml(String(Boolean(risk.is_hypothesis)))}</dd></div>
      </dl>
      ${
        shouldValidate
          ? `<p class="review-signal-line">Review signal: public evidence may be incomplete; validate before treating this as dependency risk.</p>`
          : ""
      }
      ${renderAssessmentEvidenceBlock(evidences, "Risk evidence", String(risk.risk_type || "risk"))}
    </article>
  `;
}

function renderCommercialOpportunities(opportunities) {
  return `
    <section class="assessment-section" aria-label="Commercial opportunities">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Commercial opportunities</p>
          <h4>Program or ecosystem opportunities from downstream gap-space context</h4>
        </div>
      </div>
      ${
        opportunities.length
          ? `<div class="assessment-card-list">${opportunities.map((opportunity) => renderCommercialOpportunity(opportunity)).join("")}</div>`
          : renderEmptyState("No commercial opportunities.", "The payload did not include gap-space or human-review commercial opportunities.")
      }
    </section>
  `;
}

function renderCommercialOpportunity(opportunity) {
  const opportunityType = String(
    opportunity.opportunity_type || opportunity.recommendation_type || opportunity.title || "unknown_opportunity"
  );
  const evidences = evidenceRecordsFrom(opportunity, ["evidences", "observed_evidences", "startup_evidences"]);
  return `
    <article class="assessment-card">
      <div class="field-title-row">
        <h4>${escapeHtml(opportunityType)}</h4>
        <span class="status-badge ${Boolean(opportunity.is_hypothesis) ? "status-running" : "status-completed"}">${
          Boolean(opportunity.is_hypothesis) ? "Hypothesis" : "Supported"
        }</span>
      </div>
      <dl class="evidence-definition-list compact">
        <div><dt>Type</dt><dd>${escapeHtml(opportunityType)}</dd></div>
        <div><dt>Description</dt><dd>${escapeHtml(
          String(
            opportunity.description ||
              opportunity.opportunity_description ||
              opportunity.commercial_rationale ||
              opportunity.rationale ||
              "unknown"
          )
        )}</dd></div>
        <div><dt>Confidence</dt><dd>${escapeHtml(formatConfidence(opportunity.confidence))}</dd></div>
        <div><dt>Hypothesis</dt><dd>${escapeHtml(String(Boolean(opportunity.is_hypothesis)))}</dd></div>
      </dl>
      ${renderAssessmentEvidenceBlock(evidences, "Opportunity evidence", opportunityType)}
    </article>
  `;
}

function renderAssessmentHumanReview(assessment, reviewReasons, pendingQuestions) {
  if (assessmentReadiness(assessment) === "ready_for_recommendation" && !reviewReasons.length && !pendingQuestions.length) {
    return "";
  }
  return `
    <section class="assessment-section" aria-label="Human review reasons">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Human review</p>
          <h4>Reasons and pending validation questions</h4>
        </div>
        <span class="status-badge ${reviewReasons.length ? "status-failed" : "status-running"}">${
          reviewReasons.length ? "review_required" : "review_signal"
        }</span>
      </div>
      <div class="unknown-field-strip">
        <h4>Human review reasons</h4>
        <div class="chip-list">
          ${
            reviewReasons.length
              ? reviewReasons.map((reason) => `<span class="unknown-chip">${escapeHtml(reason)}</span>`).join("")
              : `<span class="unknown-chip">none</span>`
          }
        </div>
      </div>
      <div class="pending-question-list">
        <h4>Pending validation questions</h4>
        ${
          pendingQuestions.length
            ? pendingQuestions.map((question) => renderPendingQuestion(question)).join("")
            : `<p class="muted-line">No pending validation questions were included.</p>`
        }
      </div>
    </section>
  `;
}

function renderPendingQuestion(question) {
  return `
    <article class="pending-question-item">
      <div class="field-title-row">
        <h4>${escapeHtml(String(question.field_name || "unknown_field"))}</h4>
        <span class="status-badge ${String(question.priority || "") === "critical" ? "status-failed" : "status-running"}">${
          escapeHtml(String(question.priority || "unknown"))
        }</span>
      </div>
      <p>${escapeHtml(String(question.question || "unknown"))}</p>
      <dl class="evidence-definition-list compact">
        <div><dt>Reason</dt><dd>${escapeHtml(String(question.reason || "unknown"))}</dd></div>
      </dl>
    </article>
  `;
}

function renderAssessmentEvidenceBlock(evidences, title, context) {
  return `
    <div class="assessment-evidence-block">
      <div class="assessment-evidence-toolbar">
        <span>${escapeHtml(title)}: ${escapeHtml(String(evidences.length))}</span>
        ${renderEvidenceContextButton(context)}
      </div>
      ${
        evidences.length
          ? renderEvidenceSnippetList(evidences, title)
          : `<p class="insufficient-line">insufficient evidence: no_linked_evidence</p>`
      }
    </div>
  `;
}

function renderEvidenceContextButton(context) {
  return `<button type="button" class="context-link" data-section="evidence" data-evidence-context="${escapeAttr(
    context
  )}">Evidence tab</button>`;
}

function firstRecord(...values) {
  for (const value of values) {
    const record = objectRecord(value);
    if (record) {
      return record;
    }
  }
  return null;
}

function assessmentReadiness(assessment) {
  const diagnostic = objectRecord(assessment.diagnostic_quality) || {};
  if (typeof assessment.ready_for_recommendation === "boolean") {
    return assessment.ready_for_recommendation ? "ready_for_recommendation" : "not_ready_for_recommendation";
  }
  if (typeof diagnostic.ready_for_recommendation === "boolean") {
    return diagnostic.ready_for_recommendation ? "ready_for_recommendation" : "not_ready_for_recommendation";
  }
  return "unknown";
}

function assessmentEvidenceCount(assessment) {
  return evidenceRecordsFrom(assessment).length;
}

function diagnosticReasons(assessment) {
  const diagnostic = objectRecord(assessment.diagnostic_quality) || {};
  return arrayValues(diagnostic.reasons).filter((reason) => !isReadyReason(reason));
}

function assessmentReviewReasons(run, assessment, gapSpace, humanReview, payload) {
  const diagnostic = objectRecord(assessment.diagnostic_quality) || {};
  const gapQuality = objectRecord(gapSpace?.quality) || {};
  const reasons = [
    ...arrayValues(run?.human_review_reasons),
    ...arrayValues(payload.human_review_reasons),
    ...arrayValues(diagnostic.reasons),
    ...arrayValues(gapQuality.human_review_reasons),
    ...arrayValues(humanReview?.review_reasons)
  ];
  if (gapQuality.ready_for_recommendation === false || gapQuality.requires_human_review === true) {
    reasons.push(...arrayValues(gapQuality.reasons));
  }
  return dedupeStrings(reasons.filter((reason) => !isReadyReason(reason)));
}

function assessmentPendingQuestions(assessment, payload, humanReview) {
  return dedupeRecordsByKey(
    [
      ...records(assessment.pending_questions),
      ...records(payload.pending_questions),
      ...records(humanReview?.pending_questions),
      ...records(objectRecord(payload.briefing_narrative)?.pending_questions),
      ...records(objectRecord(payload.executive_briefing)?.pending_questions)
    ],
    (question) =>
      [
        String(question.field_name || "unknown_field"),
        String(question.question || "unknown"),
        String(question.reason || "unknown")
      ].join("|")
  );
}

function commercialOpportunitiesFromPayload(payload, gapSpace, humanReview) {
  return dedupeRecordsByKey(
    [
      ...records(payload.commercial_opportunities),
      ...records(gapSpace?.commercial_opportunities),
      ...records(gapSpace?.commercial_mappings),
      ...records(humanReview?.commercial_opportunities)
    ],
    (opportunity) =>
      String(
        opportunity.opportunity_type ||
          opportunity.recommendation_type ||
          opportunity.opportunity_description ||
          opportunity.title ||
          "unknown_opportunity"
      )
  );
}

function evidenceRecordsFrom(record, keys = ["evidences", "evidence_references", "observed_evidences"]) {
  const evidences = [];
  for (const key of keys) {
    evidences.push(...records(objectRecord(record)?.[key]));
  }
  return dedupeRecordsByKey(evidences, (evidence) =>
    [String(evidence.url || "unknown"), String(evidence.snippet || "unknown"), String(evidence.source_type || "unknown")].join("|")
  );
}

function dedupeRecordsByKey(items, keyFn) {
  const seen = new Set();
  const unique = [];
  for (const item of items) {
    const key = keyFn(item);
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    unique.push(item);
  }
  return unique;
}

function dedupeStrings(items) {
  return Array.from(new Set(items.map((item) => String(item || "").trim()).filter(Boolean)));
}

function isReadyReason(reason) {
  return new Set(["ready_for_recommendation", "gap_space_ready_for_recommendation"]).has(String(reason));
}

function formatConfidence(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "unknown";
  }
  return formatPercent(number);
}

function assessmentStatusLabel(status) {
  const normalized = String(status || "unknown");
  const labels = {
    positive: "Passed",
    negative: "Failed",
    unknown: "Unknown",
    conflict: "Conflict"
  };
  return labels[normalized] || normalized;
}

function assessmentStatusClass(status) {
  const normalized = String(status || "unknown").toLowerCase();
  if (normalized === "positive") {
    return "status-completed";
  }
  if (normalized === "negative" || normalized === "conflict") {
    return "status-failed";
  }
  if (normalized === "unknown") {
    return "status-idle";
  }
  return statusClass(normalized);
}

function severityClass(severity) {
  const normalized = String(severity || "unknown").toLowerCase();
  if (normalized === "high") {
    return "status-failed";
  }
  if (normalized === "medium") {
    return "status-running";
  }
  if (normalized === "low") {
    return "status-completed";
  }
  return "status-idle";
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

function evidencePayload(run) {
  return objectRecord(run.final_payload) || {};
}

function collectionResultsFromPayload(value) {
  if (Array.isArray(value)) {
    return [{ candidateKey: "run", pages: records(value), errors: [] }];
  }
  return objectEntries(value).map(([candidateKey, result]) => {
    const record = objectRecord(result) || {};
    return {
      candidateKey,
      pages: records(record.pages),
      errors: records(record.errors)
    };
  });
}

function collectionPageStats(collectionResults) {
  const pages = collectionResults.flatMap((result) => result.pages);
  const errors = collectionResults.flatMap((result) => result.errors);
  const lengths = pages.map((page) => pageTextLength(page));
  return {
    pageCount: pages.length,
    errorCount: errors.length,
    lowTextCount: lengths.filter((length) => length < LOW_TEXT_THRESHOLD).length,
    extractionStrategies: Array.from(
      new Set(pages.map((page) => String(page.extraction_strategy || "")).filter(Boolean))
    ).sort()
  };
}

function profileFieldStats(profiles) {
  const fields = profiles.flatMap((profile) => profileFields(profile));
  const total = fields.length;
  const unknownCount = fields.filter(([, field]) => {
    const record = objectRecord(field) || {};
    return String(record.value || "unknown") === "unknown" || String(record.claim_source || "unknown") === "unknown";
  }).length;
  return {
    total,
    unknownCount,
    unknownRate: total ? unknownCount / total : 0
  };
}

function profileFields(profile) {
  const record = objectRecord(profile) || {};
  const fields = [];
  const seen = new Set();
  for (const fieldName of PROFILE_FIELD_ORDER) {
    const field = objectRecord(record[fieldName]);
    if (field) {
      fields.push([fieldName, field]);
      seen.add(fieldName);
    }
  }
  for (const [fieldName, field] of objectEntries(record)) {
    if (fieldName === "schema_version" || seen.has(fieldName)) {
      continue;
    }
    const fieldRecord = objectRecord(field);
    if (fieldRecord && ("value" in fieldRecord || "claim_source" in fieldRecord)) {
      fields.push([fieldName, fieldRecord]);
    }
  }
  return fields;
}

function evidenceGroupsForProfile(profile, evidenceGroupsByProfile, index) {
  const entries = objectEntries(evidenceGroupsByProfile);
  if (!entries.length) {
    return [];
  }
  const profileUrl = profileFieldValue(profile, "official_site");
  const profileName = profileFieldValue(profile, "company_name");
  const tokens = [profileUrl, profileName]
    .map((value) => String(value || "").trim().toLowerCase())
    .filter((value) => value && value !== "unknown");
  const matched = entries.find(([key]) => {
    const normalizedKey = String(key).toLowerCase();
    return tokens.some((token) => normalizedKey.includes(token));
  });
  if (matched) {
    return records(matched[1]);
  }
  return records(entries[index]?.[1]);
}

function profileDisplayName(profile) {
  return profileFieldValue(profile, "company_name") || "unknown startup";
}

function profileFieldValue(profile, fieldName) {
  const field = objectRecord(objectRecord(profile)?.[fieldName]);
  return String(field?.value || "");
}

function unknownFieldsFromQuality(qualityRecord, profiles) {
  const qualityUnknowns = Array.isArray(qualityRecord.unknown_fields)
    ? qualityRecord.unknown_fields
        .map((item) => {
          if (Array.isArray(item)) {
            return { name: String(item[0] || "unknown_field"), count: numericValue(item[1], 1) };
          }
          const record = objectRecord(item) || {};
          return {
            name: String(record.field_name || record.name || "unknown_field"),
            count: numericValue(record.count, 1)
          };
        })
        .filter((item) => item.name !== "unknown_field")
    : [];
  if (qualityUnknowns.length) {
    return qualityUnknowns;
  }
  const counts = new Map();
  for (const profile of profiles) {
    for (const [fieldName, field] of profileFields(profile)) {
      const record = objectRecord(field) || {};
      if (String(record.value || "unknown") === "unknown" || String(record.claim_source || "unknown") === "unknown") {
        counts.set(fieldName, (counts.get(fieldName) || 0) + 1);
      }
    }
  }
  return Array.from(counts.entries()).map(([name, count]) => ({ name, count }));
}

function readinessValue(qualityRecord) {
  if (typeof qualityRecord.ready_for_evaluation === "boolean") {
    return qualityRecord.ready_for_evaluation
      ? "ready_for_ai_native_evaluation"
      : "needs_more_collection_or_human_review";
  }
  return String(qualityRecord.readiness || qualityRecord.status || "unknown");
}

function readinessReasons(qualityRecord) {
  return [
    ...arrayValues(qualityRecord.readiness_reasons),
    ...arrayValues(qualityRecord.blocking_reasons),
    ...arrayValues(qualityRecord.human_review_reasons)
  ];
}

function pageTextLength(page) {
  const explicit = Number(page.text_length);
  if (Number.isFinite(explicit)) {
    return explicit;
  }
  const text = String(page.main_text || "");
  if (!text || text === "unknown") {
    return 0;
  }
  return text.length;
}

function renderInlineList(items) {
  const values = arrayValues(items);
  if (!values.length) {
    return "none";
  }
  return `<span class="inline-list">${values.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</span>`;
}

function arrayValues(value) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item)).filter(Boolean);
  }
  const text = String(value || "").trim();
  return text ? [text] : [];
}

function numericValue(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function formatPercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "unknown";
  }
  const percent = Math.abs(number) <= 1 ? number * 100 : number;
  const rounded = Math.round(percent * 10) / 10;
  return `${String(rounded)}%`;
}

function sourceClass(value) {
  return String(value || "unknown")
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-|-$/g, "");
}

function safeHref(value) {
  try {
    const url = new URL(String(value));
    if (url.protocol === "http:" || url.protocol === "https:") {
      return url.href;
    }
  } catch {
    return "#";
  }
  return "#";
}

function statusClass(status) {
  const normalized = String(status || "").toLowerCase();
  if (/^2\d\d$/.test(normalized)) {
    return "status-completed";
  }
  if (/^[45]\d\d$/.test(normalized)) {
    return "status-failed";
  }
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
