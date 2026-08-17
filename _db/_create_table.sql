PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE,
    group_id TEXT,
    created_at TEXT NOT NULL,
    provider TEXT,
	system_prompt TEXT NOT NULL,
    user_prompt TEXT NOT NULL,
    success INTEGER NOT NULL,
    error TEXT,
    error_type TEXT,
    elapsed_sec REAL,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_responses (
    id INTEGER PRIMARY KEY,
    response_id TEXT NOT NULL UNIQUE,
    run_id TEXT NOT NULL,

    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'answer',
    attempt_no INTEGER NOT NULL DEFAULT 1,

    response_text TEXT,
    finish_reason TEXT,
    raw_response_id TEXT,

    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    cached_tokens INTEGER DEFAULT 0,

    input_usd REAL DEFAULT 0,
    cached_input_usd REAL DEFAULT 0,
    output_usd REAL DEFAULT 0,
    total_usd REAL DEFAULT 0,
    estimated INTEGER NOT NULL DEFAULT 1,
    pricing_updated_at TEXT,
    pricing_source TEXT,

    created_at TEXT NOT NULL,

    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_runs_created_at
ON runs(created_at);

CREATE INDEX IF NOT EXISTS idx_runs_group_id
ON runs(group_id);

CREATE INDEX IF NOT EXISTS idx_model_responses_run_id
ON model_responses(run_id);

CREATE INDEX IF NOT EXISTS idx_model_responses_provider_model
ON model_responses(provider, model);

CREATE UNIQUE INDEX IF NOT EXISTS idx_model_responses_provider_raw_response
ON model_responses(provider, raw_response_id)
WHERE raw_response_id IS NOT NULL;
-- One row per comparison batch: what the batch EXPECTED, so a later reader can
-- tell a complete group from a truncated or half-archived one. The runs table
-- alone cannot say this - a run whose SQLite write failed leaves no trace here,
-- and group_id says nothing about how many rows there should be.
CREATE TABLE IF NOT EXISTS comparison_groups (
    id INTEGER PRIMARY KEY,
    group_id TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    target_count INTEGER NOT NULL,
    collected_count INTEGER NOT NULL,
    usable_count INTEGER NOT NULL,
    quorum INTEGER NOT NULL,
    collection_status TEXT NOT NULL,
    audit_status TEXT NOT NULL,
    persistence_status TEXT,
    raw_json TEXT NOT NULL
);
