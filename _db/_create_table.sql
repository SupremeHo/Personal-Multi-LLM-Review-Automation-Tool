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