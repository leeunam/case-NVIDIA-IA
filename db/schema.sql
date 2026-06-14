CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    search_params_json TEXT
);

CREATE TABLE IF NOT EXISTS search_plan_items (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    priority INTEGER NOT NULL,
    term TEXT NOT NULL,
    target_source TEXT NOT NULL,
    scope TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_discovery_results (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    source_name TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidate_startups (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    primary_url TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collected_pages (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    candidate_name TEXT NOT NULL,
    url TEXT NOT NULL,
    status_code INTEGER,
    is_error INTEGER NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS startup_profiles (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    company_name TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS field_evidences (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    company_name TEXT NOT NULL,
    field_name TEXT NOT NULL,
    evidence_url TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collection_quality_summaries (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    ready_for_evaluation INTEGER NOT NULL,
    payload_json TEXT NOT NULL
);
