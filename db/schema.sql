CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    search_params_json TEXT
);

CREATE TABLE IF NOT EXISTS search_plan_items (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    priority INTEGER NOT NULL,
    term TEXT NOT NULL,
    target_source TEXT NOT NULL,
    scope TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_discovery_results (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    source_name TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidate_startups (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    candidate_key TEXT NOT NULL,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    primary_url TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collected_pages (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    candidate_key TEXT NOT NULL,
    candidate_name TEXT NOT NULL,
    url TEXT NOT NULL,
    status_code INTEGER,
    is_error INTEGER NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS startup_profiles (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    profile_key TEXT NOT NULL,
    company_name TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS field_evidences (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    profile_key TEXT NOT NULL,
    company_name TEXT NOT NULL,
    field_name TEXT NOT NULL,
    evidence_url TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collection_quality_summaries (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    ready_for_evaluation INTEGER NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_native_assessments (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    company_name TEXT NOT NULL,
    classification TEXT NOT NULL,
    ready_for_recommendation INTEGER NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_search_plan_items_run_id ON search_plan_items(run_id);
CREATE INDEX IF NOT EXISTS idx_raw_discovery_results_run_id ON raw_discovery_results(run_id);
CREATE INDEX IF NOT EXISTS idx_candidate_startups_run_id ON candidate_startups(run_id);
CREATE INDEX IF NOT EXISTS idx_collected_pages_run_id ON collected_pages(run_id);
CREATE INDEX IF NOT EXISTS idx_collected_pages_run_candidate_key ON collected_pages(run_id, candidate_key);
CREATE INDEX IF NOT EXISTS idx_startup_profiles_run_id ON startup_profiles(run_id);
CREATE INDEX IF NOT EXISTS idx_startup_profiles_run_profile_key ON startup_profiles(run_id, profile_key);
CREATE INDEX IF NOT EXISTS idx_field_evidences_run_id ON field_evidences(run_id);
CREATE INDEX IF NOT EXISTS idx_field_evidences_run_profile_key ON field_evidences(run_id, profile_key);
CREATE INDEX IF NOT EXISTS idx_collection_quality_summaries_run_id ON collection_quality_summaries(run_id);
CREATE INDEX IF NOT EXISTS idx_ai_native_assessments_run_id ON ai_native_assessments(run_id);
