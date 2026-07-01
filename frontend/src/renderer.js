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
  const activeSection = sectionIdFromValue(overrides.activeSection);
  return {
    activeSection,
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
    activeSection,
    launcherForm
  };
}

export function sectionIdFromValue(value, fallback = "runs") {
  const candidate = String(value || "").trim();
  return SECTIONS.some((section) => section.id === candidate) ? candidate : fallback;
}

/**
 * @param {WorkbenchState} state
 */
export function renderApp(state) {
  return `
    <div class="app-shell">
      <aside class="sidebar" aria-label="Primary navigation">
        <div class="brand-block">
          <span class="brand-mark" aria-hidden="true"></span>
          <div>
            <p class="eyebrow">NVIDIA Startup Intel</p>
            <h1>Operational Workbench</h1>
          </div>
        </div>
        <nav class="section-nav" aria-label="Workbench sections">
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
  const run = state.currentRun;
  const payload = objectRecord(run?.final_payload) || {};
  const match = objectRecord(payload.nvidia_match) || objectRecord(payload.recommendation_set);
  const retrievals = nvidiaRetrievalsFromPayload(payload, match);
  const rerankResults = nvidiaRerankResultsFromPayload(payload, match);
  const metricsReport = nvidiaMetricsReportFromPayload(payload, match);
  if (!match && !retrievals.length && !rerankResults.length && !metricsReport) {
    return renderSectionPanel(
      "NVIDIA Match",
      renderEmptyState(
        "No NVIDIA match payload yet.",
        "Recommendations remain empty until the API record includes matched citations."
      )
    );
  }
  const record = match || {};
  const groups = nvidiaRecommendationGroups(record);
  return renderSectionPanel(
    "NVIDIA Match",
    `
      ${renderNvidiaMatchOverview(record, retrievals, rerankResults, run)}
      ${renderNvidiaQualityMetrics(record, metricsReport, run)}
      ${renderNvidiaRetrievals(retrievals)}
      ${renderNvidiaReranking(rerankResults)}
      ${renderRecommendationSection("Top recommendations per gap", groups.top, "supported", { highlightTop: true })}
      ${renderRecommendationSection("Supported recommendations", groups.supported, "supported")}
      ${renderRecommendationSection("Alternatives", groups.alternatives, "supported")}
      ${renderRecommendationSection("Hypotheses", groups.hypotheses, "hypothesis")}
      ${renderRecommendationSection("Blocked recommendations", groups.blocked, "blocked")}
    `
  );
}

function renderNvidiaMatchOverview(match, retrievals, rerankResults, run) {
  const quality = objectRecord(match.quality) || {};
  const metrics = objectRecord(quality.metrics) || {};
  const supportedFallback = nvidiaSupportedRecommendations(match).length;
  const supported = numericValue(metrics.supported_recommendation_count, supportedFallback);
  const hypotheses = numericValue(metrics.hypothesis_recommendation_count, records(match.hypotheses).length);
  const blocked = numericValue(metrics.blocked_recommendation_count, records(match.blocked_recommendations).length);
  const readyForBriefing = readyForNvidiaBriefing(match, run, supported);
  return `
    <div class="metric-row match-metrics">
      ${metric("Priority", String(match.final_nvidia_opportunity_priority || match.priority || "unknown"))}
      ${metric("Next action", String(match.next_action || run?.next_action || "unknown"))}
      ${metric("Ready for briefing", String(readyForBriefing))}
    </div>
    <div class="metric-row match-metrics">
      ${metric("Supported", String(supported))}
      ${metric("Hypotheses", String(hypotheses))}
      ${metric("Blocked", String(blocked))}
    </div>
    <div class="metric-row match-metrics">
      ${metric("Corpus version", String(match.corpus_version || corpusVersionFromRetrievals(retrievals) || "unknown"))}
      ${metric("Retrieval results", String(retrievals.reduce((total, retrieval) => total + records(retrieval.results).length, 0)))}
      ${metric("Reranked Top K", String(rerankResults.reduce((total, result) => total + records(result.results).length, 0)))}
    </div>
  `;
}

function renderNvidiaQualityMetrics(match, metricsReport, run) {
  const retrievalMetrics = objectRecord(metricsReport?.retrieval_metrics) || objectRecord(match.retrieval_metrics);
  const recommendationMetrics =
    objectRecord(metricsReport?.recommendation_metrics) ||
    objectRecord(objectRecord(match.quality)?.metrics) ||
    objectRecord(match.recommendation_metrics) ||
    objectRecord(match.metrics);
  const quality = objectRecord(match.quality) || {};
  const readyForBriefing = readyForNvidiaBriefing(match, run, nvidiaSupportedRecommendations(match).length);
  if (!retrievalMetrics && !recommendationMetrics && !objectEntries(quality).length && !arrayValues(run?.human_review_reasons).length) {
    return "";
  }
  return `
    <section class="match-section" aria-label="NVIDIA match quality metrics">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Quality metrics</p>
          <h4>Retrieval and recommendation quality</h4>
        </div>
        <span class="schema-pill">${escapeHtml(String(metricsReport?.schema_version || match.schema_version || "metrics"))}</span>
      </div>
      ${
        retrievalMetrics
          ? `<div class="metric-row match-metrics">
              ${metric("Recall", formatPercent(retrievalMetrics.recall))}
              ${metric("Precision", formatPercent(retrievalMetrics.precision))}
              ${metric("F1", formatPercent(retrievalMetrics.f1))}
            </div>
            <div class="metric-row match-metrics">
              ${metric("Coverage", formatPercent(retrievalMetrics.coverage))}
              ${metric("Top-1 expected", String(retrievalMetrics.top_1_expected_count ?? "unknown"))}
              ${metric("Retrieval strategy", String(retrievalMetrics.retrieval_strategy || "unknown"))}
            </div>`
          : renderEmptyState("No retrieval metrics.", "Recall, precision, F1, and coverage were not included in this run.")
      }
      ${
        recommendationMetrics
          ? `<div class="metric-row match-metrics">
              ${metric("Supported recommendations", String(recommendationMetrics.supported_recommendation_count ?? "unknown"))}
              ${metric("Hypothesis recommendations", String(recommendationMetrics.hypothesis_recommendation_count ?? "unknown"))}
              ${metric("Blocked recommendations", String(recommendationMetrics.blocked_recommendation_count ?? "unknown"))}
            </div>
            <div class="metric-row match-metrics">
              ${metric(
                "Official NVIDIA citations",
                String(recommendationMetrics.recommendations_with_official_nvidia_citation_count ?? "unknown")
              )}
              ${metric(
                "Startup evidence refs",
                String(recommendationMetrics.recommendations_with_startup_evidence_count ?? "unknown")
              )}
              ${metric("Blocked briefings", String(recommendationMetrics.blocked_briefing_count ?? "unknown"))}
            </div>`
          : ""
      }
      <div class="unknown-field-strip">
        <h4>Human review reason counts</h4>
        ${renderHumanReviewReasonCounts(recommendationMetrics?.human_review_reason_counts, run)}
      </div>
      <dl class="evidence-definition-list compact">
        <div><dt>Ready for briefing</dt><dd>${escapeHtml(String(readyForBriefing))}</dd></div>
        <div><dt>Human review requested</dt><dd>${escapeHtml(String(Boolean(quality.human_review_requested)))}</dd></div>
        <div><dt>Quality reasons</dt><dd>${renderInlineList(quality.reasons)}</dd></div>
      </dl>
    </section>
  `;
}

function renderNvidiaRetrievals(retrievals) {
  return `
    <section class="match-section" aria-label="Retrieved NVIDIA Knowledge">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Retrieved NVIDIA Knowledge</p>
          <h4>Official source chunks and retrieval scores</h4>
        </div>
      </div>
      ${
        retrievals.length
          ? `<div class="match-card-list">${retrievals.map((retrieval) => renderNvidiaRetrieval(retrieval)).join("")}</div>`
          : renderEmptyState("No retrieval payloads.", "NVIDIA Knowledge chunks were not included in this API record.")
      }
    </section>
  `;
}

function renderNvidiaRetrieval(retrieval) {
  const results = records(retrieval.results);
  return `
    <article class="match-card retrieval-card">
      <div class="field-title-row">
        <h4>${escapeHtml(String(retrieval.query || "unknown retrieval query"))}</h4>
        <span class="status-badge status-completed">${escapeHtml(String(retrieval.schema_version || "nvidia_knowledge.v1"))}</span>
      </div>
      <dl class="evidence-definition-list compact">
        <div><dt>corpus_version</dt><dd>${escapeHtml(String(retrieval.corpus_version || "unknown"))}</dd></div>
        <div><dt>Result count</dt><dd>${escapeHtml(String(results.length))}</dd></div>
        <div><dt>Retrieval strategy</dt><dd>${escapeHtml(retrievalStrategyFor(retrieval))}</dd></div>
      </dl>
      ${
        results.length
          ? `<div class="retrieval-result-list">${results.map((result) => renderNvidiaRetrievalResult(result, retrieval)).join("")}</div>`
          : `<p class="insufficient-line">insufficient citation support: no_retrieved_citation</p>`
      }
    </article>
  `;
}

function renderNvidiaRetrievalResult(result, retrieval) {
  const citation = objectRecord(result.citation) || {};
  const chunk = objectRecord(result.chunk) || {};
  const sourceUrl = String(citation.source_url || "unknown");
  const official = isOfficialNvidiaCitation(citation);
  return `
    <article class="retrieval-result ${official ? "" : "has-hypothesis"}">
      <div class="field-title-row">
        <h4>${escapeHtml(String(citation.document_title || chunk.document_id || "unknown NVIDIA document"))}</h4>
        <span class="status-badge ${official ? "status-completed" : "status-running"}">${
          official ? "Official NVIDIA source" : "Non-official or insufficient citation"
        }</span>
      </div>
      <p class="match-excerpt">${escapeHtml(String(citation.excerpt || chunk.text || "unknown excerpt"))}</p>
      <dl class="evidence-definition-list compact">
        <div><dt>chunk id</dt><dd>${escapeHtml(String(citation.chunk_id || chunk.chunk_id || "unknown"))}</dd></div>
        <div><dt>document title</dt><dd>${escapeHtml(String(citation.document_title || "unknown"))}</dd></div>
        <div><dt>official source URL</dt><dd>${renderSourceUrl(sourceUrl)}</dd></div>
        <div><dt>corpus_version</dt><dd>${escapeHtml(String(citation.corpus_version || retrieval.corpus_version || "unknown"))}</dd></div>
        <div><dt>retrieval strategy</dt><dd>${escapeHtml(String(result.retrieval_strategy || retrievalStrategyFor(retrieval)))}</dd></div>
        <div><dt>rank</dt><dd>${escapeHtml(String(result.rank ?? "unknown"))}</dd></div>
        <div><dt>score</dt><dd>${escapeHtml(formatScore(result.score))}</dd></div>
        <div><dt>BM25 score</dt><dd>${escapeHtml(formatScore(result.bm25_score))}</dd></div>
        <div><dt>vector score</dt><dd>${escapeHtml(formatScore(result.vector_score))}</dd></div>
        <div><dt>hybrid score</dt><dd>${escapeHtml(formatScore(result.hybrid_score))}</dd></div>
      </dl>
      <p class="muted-line">${escapeHtml(String(result.rationale || "retrieval rationale unavailable"))}</p>
    </article>
  `;
}

function renderNvidiaReranking(rerankResults) {
  return `
    <section class="match-section" aria-label="NVIDIA reranking output">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Reranking</p>
          <h4>Top K reorder audit</h4>
        </div>
      </div>
      ${
        rerankResults.length
          ? `<p class="review-signal-line">Rerank scores reorder supplied Top K retrieval candidates only; they do not create new facts.</p>
            <div class="match-card-list">${rerankResults.map((result) => renderNvidiaRerankResult(result)).join("")}</div>`
          : renderEmptyState("No reranking payload.", "Rerank score and rationale will appear only when the run includes nvidia_rerank.v1 output.")
      }
    </section>
  `;
}

function renderNvidiaRerankResult(rerankResult) {
  const results = records(rerankResult.results);
  return `
    <article class="match-card rerank-card">
      <div class="field-title-row">
        <h4>${escapeHtml(String(rerankResult.query || "unknown rerank query"))}</h4>
        <span class="status-badge status-running">${escapeHtml(String(rerankResult.ranking_strategy || "unknown_strategy"))}</span>
      </div>
      <dl class="evidence-definition-list compact">
        <div><dt>candidate_top_k</dt><dd>${escapeHtml(String(rerankResult.candidate_top_k ?? "unknown"))}</dd></div>
        <div><dt>reranker model</dt><dd>${escapeHtml(String(rerankResult.reranker_model_name || "unknown"))}</dd></div>
        <div><dt>audit reasons</dt><dd>${renderInlineList(rerankResult.audit_reasons)}</dd></div>
      </dl>
      <div class="retrieval-result-list">
        ${
          results.length
            ? results.map((result) => renderRerankedNvidiaCandidate(result)).join("")
            : `<p class="insufficient-line">No reranked candidates were included.</p>`
        }
      </div>
    </article>
  `;
}

function renderRerankedNvidiaCandidate(result) {
  const citation = objectRecord(result.citation) || {};
  const chunk = objectRecord(result.chunk) || {};
  return `
    <article class="retrieval-result">
      <div class="field-title-row">
        <h4>${escapeHtml(String(citation.document_title || chunk.document_id || "unknown NVIDIA document"))}</h4>
        <span class="status-badge status-running">Rerank rank ${escapeHtml(String(result.rerank_rank ?? "unknown"))}</span>
      </div>
      <dl class="evidence-definition-list compact">
        <div><dt>chunk id</dt><dd>${escapeHtml(String(citation.chunk_id || chunk.chunk_id || "unknown"))}</dd></div>
        <div><dt>original rank</dt><dd>${escapeHtml(String(result.original_retrieval_rank ?? "unknown"))}</dd></div>
        <div><dt>original score</dt><dd>${escapeHtml(formatScore(result.original_score))}</dd></div>
        <div><dt>original BM25 score</dt><dd>${escapeHtml(formatScore(result.original_bm25_score))}</dd></div>
        <div><dt>original vector score</dt><dd>${escapeHtml(formatScore(result.original_vector_score))}</dd></div>
        <div><dt>original hybrid score</dt><dd>${escapeHtml(formatScore(result.original_hybrid_score))}</dd></div>
        <div><dt>rerank score</dt><dd>${escapeHtml(formatScore(result.rerank_score))}</dd></div>
        <div><dt>rerank rationale</dt><dd>${escapeHtml(String(result.rerank_rationale || "unknown"))}</dd></div>
      </dl>
    </article>
  `;
}

function renderRecommendationSection(title, recommendations, fallbackState, options = {}) {
  return `
    <section class="match-section" aria-label="${escapeAttr(title)}">
      <div class="section-heading">
        <div>
          <p class="eyebrow">${escapeHtml(title)}</p>
          <h4>${escapeHtml(recommendationSectionSubtitle(title))}</h4>
        </div>
      </div>
      ${
        recommendations.length
          ? `<div class="match-card-list">${recommendations
              .map((recommendation) =>
                renderNvidiaRecommendation(recommendation, fallbackState, Boolean(options.highlightTop))
              )
              .join("")}</div>`
          : renderEmptyState(`No ${title.toLowerCase()}.`, "The API record did not include entries for this recommendation group.")
      }
    </section>
  `;
}

function renderNvidiaRecommendation(recommendation, fallbackState, highlightTop) {
  const declaredState = String(recommendation.state || fallbackState || "unknown").toLowerCase();
  const hasOfficialCitation = recommendationHasOfficialCitation(recommendation);
  const effectiveState = declaredState === "supported" && !hasOfficialCitation ? "hypothesis" : declaredState;
  const stateLabel = recommendationStateLabel(effectiveState);
  const citations = records(recommendation.nvidia_citations);
  const startupEvidences = evidenceRecordsFrom(recommendation, [
    "startup_evidences",
    "startup_evidence_refs",
    "evidences",
    "evidence_references",
  ]);
  const title = recommendationTitle(recommendation);
  return `
    <article class="match-card recommendation-card ${highlightTop ? "is-top" : ""} ${
      effectiveState === "blocked" ? "has-block" : effectiveState === "hypothesis" ? "has-hypothesis" : ""
    }">
      <div class="field-title-row">
        <h4>${escapeHtml(title)}</h4>
        <div class="pill-stack">
          ${highlightTop ? `<span class="safe-pill">Top recommendation</span>` : ""}
          <span class="status-badge ${recommendationStateClass(effectiveState)}">${escapeHtml(stateLabel)}</span>
        </div>
      </div>
      <dl class="evidence-definition-list compact">
        <div><dt>Type</dt><dd>${escapeHtml(String(recommendation.recommendation_type || "unknown"))}</dd></div>
        <div><dt>State</dt><dd>${escapeHtml(effectiveState)}</dd></div>
        <div><dt>Priority</dt><dd>${escapeHtml(String(recommendation.nvidia_opportunity_priority || recommendation.priority || "unknown"))}</dd></div>
        <div><dt>Complexity</dt><dd>${escapeHtml(String(recommendation.complexity || "unknown"))}</dd></div>
        <div><dt>Next action</dt><dd>${escapeHtml(String(recommendation.next_action || "unknown"))}</dd></div>
        <div><dt>Gap or opportunity</dt><dd>${escapeHtml(recommendationTarget(recommendation))}</dd></div>
        <div><dt>NVIDIA fit</dt><dd>${escapeHtml(String(recommendation.nvidia_technology || recommendation.nvidia_program || title))}</dd></div>
        <div><dt>Selection reasons</dt><dd>${renderInlineList(recommendation.selection_reasons)}</dd></div>
      </dl>
      <p class="match-excerpt">${escapeHtml(
        String(recommendation.technical_rationale || recommendation.rationale || recommendation.commercial_rationale || "unknown rationale")
      )}</p>
      ${
        hasOfficialCitation
          ? ""
          : `<p class="review-signal-line">Non-official or insufficient NVIDIA citation: treat as ${
              effectiveState === "blocked" ? "blocked" : "hypothesis"
            } until validated.</p>`
      }
      ${renderStartupEvidenceReferences(startupEvidences, recommendation)}
      ${renderNvidiaCitationReferences(citations)}
    </article>
  `;
}

function renderStartupEvidenceReferences(evidences, recommendation) {
  const refValues = textArrayValues(recommendation.startup_evidence_refs || recommendation.evidence_references);
  return `
    <div class="match-evidence-block">
      <div class="match-evidence-toolbar">
        <span>Startup evidence refs: ${escapeHtml(String(evidences.length || refValues.length))}</span>
        <button type="button" class="context-link" data-section="evidence" data-evidence-context="${escapeAttr(
          recommendationTarget(recommendation)
        )}">Evidence tab</button>
      </div>
      ${
        evidences.length
          ? renderEvidenceSnippetList(evidences, "Startup-side evidence")
          : refValues.length
            ? renderInlineList(refValues)
            : `<p class="insufficient-line">insufficient startup evidence: no_linked_evidence</p>`
      }
    </div>
  `;
}

function renderNvidiaCitationReferences(citations) {
  return `
    <div class="match-evidence-block">
      <div class="match-evidence-toolbar">
        <span>NVIDIA citation refs: ${escapeHtml(String(citations.length))}</span>
      </div>
      ${
        citations.length
          ? `<div class="snippet-stack">${citations.map((citation) => renderNvidiaCitationReference(citation)).join("")}</div>`
          : `<p class="insufficient-line">insufficient citation support: missing_official_nvidia_citation</p>`
      }
    </div>
  `;
}

function renderNvidiaCitationReference(citation) {
  const official = isOfficialNvidiaCitation(citation);
  const sourceUrl = String(citation.source_url || "unknown");
  return `
    <article class="snippet-item ${official ? "" : "has-hypothesis"}">
      <div class="field-title-row">
        <h4>${escapeHtml(String(citation.document_title || "unknown NVIDIA citation"))}</h4>
        <span class="status-badge ${official ? "status-completed" : "status-running"}">${
          official ? "Official NVIDIA citation" : "Non-official or insufficient NVIDIA citation"
        }</span>
      </div>
      <p>${escapeHtml(String(citation.excerpt || "unknown excerpt"))}</p>
      <dl class="evidence-definition-list compact">
        <div><dt>chunk id</dt><dd>${escapeHtml(String(citation.chunk_id || "unknown"))}</dd></div>
        <div><dt>document id</dt><dd>${escapeHtml(String(citation.document_id || "unknown"))}</dd></div>
        <div><dt>source URL</dt><dd>${renderSourceUrl(sourceUrl)}</dd></div>
        <div><dt>source type</dt><dd>${escapeHtml(String(citation.source_type || "unknown"))}</dd></div>
        <div><dt>corpus_version</dt><dd>${escapeHtml(String(citation.corpus_version || "unknown"))}</dd></div>
      </dl>
    </article>
  `;
}

function nvidiaRecommendationGroups(match) {
  const supported = nvidiaSupportedRecommendations(match);
  const top = uniqueRecommendations(records(match.top_recommendations_by_gap));
  return {
    top,
    supported: supported.length ? supported : top,
    alternatives: uniqueRecommendations(records(match.alternatives)),
    hypotheses: uniqueRecommendations(records(match.hypotheses)),
    blocked: uniqueRecommendations(records(match.blocked_recommendations))
  };
}

function nvidiaSupportedRecommendations(match) {
  return uniqueRecommendations([
    ...records(match.technical_recommendations),
    ...records(match.program_recommendations),
    ...records(match.supported_recommendations)
  ]);
}

function readyForNvidiaBriefing(match, run, supportedCount) {
  const quality = objectRecord(match.quality) || {};
  if (typeof quality.ready_for_briefing === "boolean") {
    return quality.ready_for_briefing;
  }
  if (typeof match.ready_for_briefing === "boolean") {
    return match.ready_for_briefing;
  }
  return supportedCount > 0 && Boolean(run?.briefing_reference);
}

function uniqueRecommendations(items) {
  return dedupeRecordsByKey(items, (item) =>
    String(
      item.recommendation_id ||
        [
          item.recommendation_type,
          recommendationTarget(item),
          item.nvidia_technology,
          item.nvidia_program,
          item.title,
          item.state
        ].join("|")
    )
  );
}

function recommendationSectionSubtitle(title) {
  const subtitles = {
    "Top recommendations per gap": "Highest-ranked NVIDIA fit for each observed gap",
    "Supported recommendations": "Supported technical and program actions with citation refs",
    Alternatives: "Close alternatives that remain inspectable",
    Hypotheses: "Potential fit that requires citation or evidence validation",
    "Blocked recommendations": "Items blocked from supported briefing use"
  };
  return subtitles[title] || "NVIDIA recommendation details";
}

function recommendationTitle(recommendation) {
  return String(
    recommendation.title ||
      recommendation.nvidia_technology ||
      recommendation.nvidia_program ||
      recommendation.recommendation_id ||
      recommendationTarget(recommendation)
  );
}

function recommendationTarget(recommendation) {
  const gap = objectRecord(recommendation.gap);
  const opportunity = objectRecord(recommendation.opportunity);
  return String(
    gap?.gap_type ||
      opportunity?.opportunity_type ||
      recommendation.gap_type ||
      recommendation.opportunity_type ||
      recommendation.recommendation_type ||
      "unknown_target"
  );
}

function recommendationHasOfficialCitation(recommendation) {
  return records(recommendation.nvidia_citations).some((citation) => isOfficialNvidiaCitation(citation));
}

function recommendationStateLabel(state) {
  const labels = {
    supported: "Supported",
    hypothesis: "Hypothesis",
    blocked: "Blocked"
  };
  return labels[state] || state || "unknown";
}

function recommendationStateClass(state) {
  if (state === "supported") {
    return "status-completed";
  }
  if (state === "blocked") {
    return "status-failed";
  }
  if (state === "hypothesis") {
    return "status-running";
  }
  return statusClass(state);
}

function isOfficialNvidiaCitation(citation) {
  const sourceType = String(citation.source_type || "").toLowerCase();
  if (sourceType.includes("official_nvidia")) {
    return true;
  }
  try {
    const url = new URL(String(citation.source_url || ""));
    const hostname = url.hostname.toLowerCase();
    if (hostname === "github.com") {
      return /^\/nvidia(\/|$)/i.test(url.pathname);
    }
    return hostname === "nvidia.com" || hostname.endsWith(".nvidia.com");
  } catch {
    return false;
  }
}

function nvidiaRetrievalsFromPayload(payload, match) {
  return dedupeRecordsByKey(
    [
      ...versionedPayloadsFrom(payload.retrievals),
      ...versionedPayloadsFrom(payload.nvidia_retrievals),
      ...versionedPayloadsFrom(payload.nvidia_knowledge_retrievals),
      ...versionedPayloadsFrom(payload.downstream_retrievals),
      ...versionedPayloadsFrom(match?.retrievals),
      ...versionedPayloadsFrom(match?.nvidia_retrievals)
    ].filter(isNvidiaRetrievalPayload),
    (retrieval) => [retrieval.run_id, retrieval.query, retrieval.corpus_version, records(retrieval.results).length].join("|")
  );
}

function nvidiaRerankResultsFromPayload(payload, match) {
  return dedupeRecordsByKey(
    [
      ...versionedPayloadsFrom(payload.rerank_results),
      ...versionedPayloadsFrom(payload.nvidia_rerank_results),
      ...versionedPayloadsFrom(payload.reranking_results),
      ...versionedPayloadsFrom(match?.rerank_results),
      ...versionedPayloadsFrom(match?.nvidia_rerank_results)
    ].filter(isNvidiaRerankPayload),
    (result) => [result.run_id, result.query, result.ranking_strategy, records(result.results).length].join("|")
  );
}

function nvidiaMetricsReportFromPayload(payload, match) {
  const reports = [
    ...versionedPayloadsFrom(payload.downstream_quality_report),
    ...versionedPayloadsFrom(payload.downstream_metrics),
    ...versionedPayloadsFrom(payload.metrics),
    ...versionedPayloadsFrom(match?.downstream_quality_report),
    ...versionedPayloadsFrom(match?.metrics_report)
  ].filter(isDownstreamMetricsPayload);
  return reports[0] || null;
}

function versionedPayloadsFrom(value) {
  if (Array.isArray(value)) {
    return value.flatMap((item) => versionedPayloadsFrom(item));
  }
  const record = objectRecord(value);
  if (!record) {
    return [];
  }
  return [
    ...versionedPayloadsFrom(record.payload),
    ...versionedPayloadsFrom(record.items),
    ...versionedPayloadsFrom(record.retrievals),
    ...versionedPayloadsFrom(record.rerank_results),
    record
  ];
}

function isNvidiaRetrievalPayload(record) {
  return (
    record.schema_version === "nvidia_knowledge.v1" ||
    (records(record.results).some((result) => objectRecord(result.citation) || objectRecord(result.chunk)) &&
      ("query" in record || "corpus_version" in record))
  );
}

function isNvidiaRerankPayload(record) {
  return (
    record.schema_version === "nvidia_rerank.v1" ||
    records(record.results).some((result) => "rerank_score" in result || "original_retrieval_rank" in result)
  );
}

function isDownstreamMetricsPayload(record) {
  return Boolean(
    record.schema_version === "downstream_metrics.v1" ||
      objectRecord(record.retrieval_metrics) ||
      objectRecord(record.recommendation_metrics)
  );
}

function corpusVersionFromRetrievals(retrievals) {
  return String(retrievals.find((retrieval) => retrieval.corpus_version)?.corpus_version || "");
}

function retrievalStrategyFor(retrieval) {
  const firstResult = records(retrieval.results)[0];
  return String(firstResult?.retrieval_strategy || retrieval.retrieval_strategy || retrieval.ranking_strategy || "no_results");
}

function formatScore(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "unknown";
  }
  return String(Math.round(number * 1000) / 1000);
}

function renderHumanReviewReasonCounts(counts, run) {
  const items = reasonCountItems(counts);
  if (items.length) {
    return `
      <div class="chip-list">
        ${items
          .map((item) => `<span class="unknown-chip">${escapeHtml(item.reason)} (${escapeHtml(String(item.count))})</span>`)
          .join("")}
      </div>
    `;
  }
  const reasons = arrayValues(run?.human_review_reasons);
  if (reasons.length) {
    return `<div class="chip-list">${reasons
      .map((reason) => `<span class="unknown-chip">${escapeHtml(reason)} (1)</span>`)
      .join("")}</div>`;
  }
  return `<p class="muted-line">none</p>`;
}

function reasonCountItems(counts) {
  if (Array.isArray(counts)) {
    return counts
      .map((item) => {
        if (Array.isArray(item)) {
          return { reason: String(item[0] || "unknown_reason"), count: numericValue(item[1], 1) };
        }
        const record = objectRecord(item);
        if (record) {
          return {
            reason: String(record.reason || record.name || record.human_review_reason || "unknown_reason"),
            count: numericValue(record.count, 1)
          };
        }
        return { reason: String(item || "unknown_reason"), count: 1 };
      })
      .filter((item) => item.reason !== "unknown_reason");
  }
  return objectEntries(counts).map(([reason, count]) => ({ reason, count: numericValue(count, 1) }));
}

function textArrayValues(value) {
  if (Array.isArray(value)) {
    return value
      .filter((item) => !item || typeof item !== "object")
      .map((item) => String(item || "").trim())
      .filter(Boolean);
  }
  const text = String(value || "").trim();
  return text ? [text] : [];
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
  const steps = records(matrix.matrix.steps);
  const counts = smokeStatusCounts(steps);
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
      <div class="smoke-readiness-grid" aria-label="Production validation modes">
        <article class="smoke-guidance">
          <p class="eyebrow">Default local validation</p>
          <h4>Deterministic suite</h4>
          <p>Run without real services, credentials, Postgres, LangGraph, LLM, embedding, or browser dependencies.</p>
          ${renderCodeList(["python -m pytest -q", "python -m ruff check .", "python -m mypy src"])}
        </article>
        <article class="smoke-guidance warning-guidance">
          <p class="eyebrow">Opt-in real integrations</p>
          <h4>Maintainer readiness</h4>
          <p>Set one enable flag at a time, keep secrets in shell env vars, and do not paste credential values into this UI.</p>
          <p>Generated smoke artifacts belong outside commits unless a reviewed fixture intentionally requires them.</p>
        </article>
      </div>
      <div class="metric-row smoke-summary">
        ${metric("Integrations", String(steps.length))}
        ${metric("Passed", String(counts.passed))}
        ${metric("Failed", String(counts.failed))}
        ${metric("Skipped", String(counts.skipped))}
      </div>
      <div class="smoke-card-list" aria-label="Production smoke integrations">
        ${steps.map(renderSmokeStepCard).join("")}
      </div>
    `
  );
}

function renderSmokeStepCard(step) {
  const requiredEnvVars = arrayValues(step.required_env_vars);
  const prerequisites = arrayValues(step.prerequisites);
  const expectedArtifacts = arrayValues(step.expected_artifacts);
  const cleanup = arrayValues(step.cleanup);
  return `
    <article class="smoke-card ${statusClass(step.status)}">
      <div class="smoke-card-header">
        <div>
          <p class="eyebrow">${escapeHtml(String(step.integration_id || "unknown_integration"))}</p>
          <h4>${escapeHtml(String(step.title || "Untitled smoke"))}</h4>
        </div>
        <span class="status-badge ${statusClass(step.status)}">${escapeHtml(String(step.status || "unknown"))}</span>
      </div>
      <dl class="smoke-definition-list">
        <div><dt>Bottleneck</dt><dd>${escapeHtml(String(step.bottleneck || "unknown"))}</dd></div>
        <div><dt>Env flag</dt><dd><code>${escapeHtml(smokeEnvFlag(step))}</code></dd></div>
        <div><dt>Message</dt><dd>${escapeHtml(String(step.message || "unknown"))}</dd></div>
        <div><dt>Command</dt><dd><code>${escapeHtml(String(step.command || "unknown"))}</code></dd></div>
      </dl>
      ${renderSmokeEnvStatus(step)}
      <div class="smoke-detail-grid">
        ${renderSmokeList("Prerequisites", prerequisites, "No extra prerequisite listed.")}
        ${renderSmokeList("Required env vars", requiredEnvVars, "No required env vars beyond the enable flag.")}
        ${renderSmokeList("Expected artifacts", expectedArtifacts, "No persisted artifact expected.")}
        ${renderSmokeList("Cleanup", cleanup, "No cleanup step listed.")}
      </div>
      ${renderSmokeDiagnostic(step)}
      ${renderSmokePayloadHygiene(step)}
      ${renderFullOperationalSmokeGuidance(step)}
    </article>
  `;
}

function renderSmokeEnvStatus(step) {
  const rows = smokeEnvStatusRows(step);
  return `
    <div class="smoke-env-status">
      <h4>Configured variables</h4>
      <div class="env-chip-row">
        ${rows
          .map(
            (row) => `
              <span class="env-chip ${row.configured === true ? "is-configured" : ""}">
                <code>${escapeHtml(row.name)}</code>
                <strong>${escapeHtml(envStatusLabel(row))}</strong>
              </span>
            `
          )
          .join("")}
      </div>
    </div>
  `;
}

function renderSmokeList(title, items, emptyText) {
  return `
    <section class="smoke-mini-section">
      <h4>${escapeHtml(title)}</h4>
      ${
        items.length
          ? `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
          : `<p class="muted-line">${escapeHtml(emptyText)}</p>`
      }
    </section>
  `;
}

function renderSmokeDiagnostic(step) {
  const status = String(step.status || "unknown").toLowerCase();
  const bottleneck = String(step.bottleneck || "unknown");
  const message = String(step.message || "unknown");
  let diagnostic = "Review prerequisites, variable names, expected artifacts, and cleanup before running this integration.";
  if (status === "failed" && bottleneck === "credential_hygiene") {
    diagnostic =
      "Credential hygiene failed: inspect the reported smoke payload or generated artifact, remove the leaked value, rotate the credential if it escaped the environment, and rerun the smoke.";
  } else if (status === "failed") {
    diagnostic = `Fix the ${bottleneck} bottleneck, then rerun only this integration. Diagnostic: ${message}`;
  } else if (status === "skipped" && message.includes("missing env vars")) {
    diagnostic = "Missing environment variables: configure the listed variable names in the shell without exposing their values here.";
  } else if (status === "skipped") {
    diagnostic = "Skipped by default: enable only after prerequisites are ready and the maintainer intentionally opts in.";
  } else if (status === "passed") {
    diagnostic = "Passed in the current matrix: confirm expected artifacts and cleanup before sharing results.";
  }
  return `
    <div class="smoke-diagnostic">
      <strong>Actionable diagnostic</strong>
      <p>${escapeHtml(diagnostic)}</p>
    </div>
  `;
}

function renderSmokePayloadHygiene(step) {
  const payload = objectRecord(step.payload);
  if (!payload || !objectEntries(payload).length) {
    return "";
  }
  const redactedFields = redactedPayloadFields(payload);
  const payloadKeys = payloadFieldNames(payload);
  return `
    <div class="smoke-payload-hygiene">
      <strong>Payload hygiene</strong>
      <p>Payload values are not displayed. Field names available: ${renderInlineList(payloadKeys)}</p>
      ${
        redactedFields.length
          ? `<p>Redacted credential fields: ${renderInlineList(redactedFields)}</p>`
          : `<p>No redacted credential field marker was reported.</p>`
      }
    </div>
  `;
}

function renderFullOperationalSmokeGuidance(step) {
  if (String(step.integration_id || "") !== "full_operational_smoke") {
    return "";
  }
  return `
    <aside class="smoke-full-guidance">
      <strong>Full operational smoke boundary</strong>
      <p>Use a bounded public startup URL or bounded query only. Keep generated output under the smoke run directory, review it for credential hygiene, and do not commit generated artifacts.</p>
    </aside>
  `;
}

function renderCodeList(items) {
  return `<ul class="code-list">${items.map((item) => `<li><code>${escapeHtml(item)}</code></li>`).join("")}</ul>`;
}

function smokeStatusCounts(steps) {
  return {
    passed: steps.filter((step) => String(step.status || "").toLowerCase() === "passed").length,
    failed: steps.filter((step) => String(step.status || "").toLowerCase() === "failed").length,
    skipped: steps.filter((step) => String(step.status || "").toLowerCase() === "skipped").length
  };
}

function smokeEnvFlag(step) {
  return String(step.env_flag || smokeEnvStatusRows(step).find((row) => row.role === "enable_flag")?.name || "unknown");
}

function smokeEnvStatusRows(step) {
  const explicitRows = records(step.env_status).map((row) => ({
    name: String(row.name || "unknown_env_var"),
    role: String(row.role || "required"),
    configured: typeof row.configured === "boolean" ? row.configured : null
  }));
  if (explicitRows.length) {
    return explicitRows;
  }
  return [
    {
      name: String(step.env_flag || "unknown_env_flag"),
      role: "enable_flag",
      configured: null
    },
    ...arrayValues(step.required_env_vars).map((name) => ({
      name,
      role: "required",
      configured: null
    }))
  ];
}

function envStatusLabel(row) {
  const role = row.role === "enable_flag" ? "enable flag" : "required";
  if (row.configured === true) {
    return `${role}: configured`;
  }
  if (row.configured === false) {
    return `${role}: missing`;
  }
  return `${role}: status unavailable`;
}

function redactedPayloadFields(payload) {
  const fields = [];
  visitPayload(payload, "", (path, value) => {
    if (value === "[REDACTED]") {
      fields.push(path);
    }
  });
  return fields;
}

function payloadFieldNames(payload) {
  const fields = [];
  visitPayload(payload, "", (path) => {
    fields.push(path);
  });
  return fields.slice(0, 12);
}

function visitPayload(value, prefix, visit) {
  if (Array.isArray(value)) {
    value.forEach((item, index) => visitPayload(item, `${prefix}[${String(index)}]`, visit));
    return;
  }
  if (value && typeof value === "object") {
    for (const [key, child] of Object.entries(value)) {
      const path = prefix ? `${prefix}.${key}` : key;
      visit(path, child);
      visitPayload(child, path, visit);
    }
  }
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
  if (
    normalized.includes("pass") ||
    normalized.includes("complete") ||
    normalized.includes("generated") ||
    normalized.includes("ready")
  ) {
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
