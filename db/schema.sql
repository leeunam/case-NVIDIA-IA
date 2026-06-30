CREATE EXTENSION IF NOT EXISTS vector;

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

CREATE TABLE IF NOT EXISTS downstream_retrievals (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    startup_identifier TEXT NOT NULL,
    corpus_version TEXT NOT NULL,
    retrieval_strategy TEXT NOT NULL,
    position INTEGER NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS downstream_recommendations (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    startup_identifier TEXT NOT NULL,
    corpus_version TEXT NOT NULL,
    final_nvidia_opportunity_priority TEXT NOT NULL,
    ready_for_briefing INTEGER NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS downstream_briefings (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    startup_identifier TEXT NOT NULL,
    briefing_type TEXT NOT NULL,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS downstream_metrics (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    startup_identifier TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    corpus_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
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
CREATE INDEX IF NOT EXISTS idx_downstream_retrievals_run_startup ON downstream_retrievals(run_id, startup_identifier);
CREATE INDEX IF NOT EXISTS idx_downstream_recommendations_run_startup ON downstream_recommendations(run_id, startup_identifier);
CREATE INDEX IF NOT EXISTS idx_downstream_briefings_run_startup ON downstream_briefings(run_id, startup_identifier);
CREATE INDEX IF NOT EXISTS idx_downstream_metrics_run_startup ON downstream_metrics(run_id, startup_identifier);

CREATE TABLE IF NOT EXISTS nvidia_knowledge_documents (
    id BIGSERIAL PRIMARY KEY,
    schema_version TEXT NOT NULL,
    corpus_version TEXT NOT NULL,
    document_id TEXT NOT NULL,
    title TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_type TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE (corpus_version, document_id)
);

CREATE TABLE IF NOT EXISTS nvidia_knowledge_chunks (
    id BIGSERIAL PRIMARY KEY,
    schema_version TEXT NOT NULL,
    corpus_version TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    topic TEXT NOT NULL,
    text TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE (corpus_version, chunk_id),
    FOREIGN KEY (corpus_version, document_id)
        REFERENCES nvidia_knowledge_documents(corpus_version, document_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS nvidia_chunk_embeddings (
    id BIGSERIAL PRIMARY KEY,
    corpus_version TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    embedding_provider TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_version TEXT NOT NULL,
    vector_dimension INTEGER NOT NULL,
    distance_metric TEXT NOT NULL,
    index_parameters_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    embedding vector NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (vector_dims(embedding) = vector_dimension),
    UNIQUE (
        corpus_version,
        chunk_id,
        embedding_provider,
        embedding_model,
        embedding_version,
        vector_dimension
    ),
    FOREIGN KEY (corpus_version, chunk_id)
        REFERENCES nvidia_knowledge_chunks(corpus_version, chunk_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_nvidia_knowledge_documents_corpus ON nvidia_knowledge_documents(corpus_version);
CREATE INDEX IF NOT EXISTS idx_nvidia_knowledge_chunks_corpus_topic ON nvidia_knowledge_chunks(corpus_version, topic);
CREATE INDEX IF NOT EXISTS idx_nvidia_chunk_embeddings_lookup ON nvidia_chunk_embeddings(corpus_version, embedding_model, embedding_version, vector_dimension);
CREATE INDEX IF NOT EXISTS idx_nvidia_chunk_embeddings_chunk ON nvidia_chunk_embeddings(corpus_version, chunk_id);
