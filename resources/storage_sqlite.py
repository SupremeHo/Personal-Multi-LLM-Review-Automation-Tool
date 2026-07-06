# Module for SQLite database management.
# Store them in a SQLite database for later retrieval and analysis.

import json
import sqlite3

from resources.diagnostics import print_error
from resources.storage_json import load_jsonl_file


def ensure_audit_columns(conn: sqlite3.Connection) -> None:
    """
    Add audit columns to the "runs" table if an older database predates them.Idempotent: safe to call every time.
    Keeps failed-call metadata (provider, error_type) queryable without recreating the database.
    """
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(runs)")}

    if "provider" not in existing_columns:
        conn.execute("ALTER TABLE runs ADD COLUMN provider TEXT")

    if "error_type" not in existing_columns:
        conn.execute("ALTER TABLE runs ADD COLUMN error_type TEXT")


def insert_log_record(conn: sqlite3.Connection, json_record: dict) -> None:
    """
    Insert the LLM's log record to the SQLite Database.
    """

    result = json_record.get("result") or {}
    usage = result.get("usage") or {}
    cost = result.get("cost") or {}

    # Map the provider-neutral schema fields onto the flat DB columns.
    input_tokens = usage.get("input_tokens", 0) or 0
    output_tokens = usage.get("output_tokens", 0) or 0

    # total_tokens is optional in the schema (some providers omit it); derive it when missing.
    total_tokens = usage.get("total_tokens")
    if total_tokens is None:
        total_tokens = input_tokens + output_tokens

    # The cache breakdown is provider-specific and preserved in full inside raw_json.
    # The single cached_tokens column stores a coarse rollup (only one provider's
    # fields are populated per row, so summing is safe).
    cached_tokens = (
        (usage.get("cached_input_tokens") or 0)
        + (usage.get("cache_creation_input_tokens") or 0)
        + (usage.get("cache_read_input_tokens") or 0)
    )

    try:
        run_id = json_record["run_id"]
        created_at = json_record["created_at"]
    except KeyError:
        print_error(
            "Missing required field in record.",
            module="storage_sqlite.py",
            func="insert_log_record",
        )
        raise

    raw_json = json.dumps(json_record, ensure_ascii=False)

    # Save the executed results to table "run", but ignore run_id if it already exists, and convert success and error values into a form that is easy to store in SQLite.
    conn.execute(
        """
        INSERT OR IGNORE INTO runs (
            run_id, created_at, provider, system_prompt, user_prompt,
            success, error, error_type, elapsed_sec, raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            created_at,
            json_record.get("provider"),
            json_record.get("system_prompt", ""),
            json_record.get("user_prompt", ""),
            int(bool(json_record.get("success", False))),
            json.dumps(json_record.get("error"), ensure_ascii=False)
            if json_record.get("error") is not None
            else None,
            json_record.get("error_type"),
            json_record.get("elapsed_sec"),
            raw_json,
        ),
    )

    # A failed call has no result, so there is no model response to store. Skip the insert to avoid a NOT NULL
    # violation on model/response_id, while the run (with its error metadata) above is still preserved.
    if not (result.get("response_id") and result.get("model")):
        return

    conn.execute(
        """
        INSERT OR IGNORE INTO model_responses (
            response_id, run_id,
            provider, model, role, attempt_no,
            response_text, finish_reason, raw_response_id,
            prompt_tokens, completion_tokens, total_tokens, cached_tokens,
            input_usd, cached_input_usd, output_usd, total_usd,
            estimated, pricing_updated_at, pricing_source,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            result.get("response_id"),
            run_id,
            result.get("provider"),
            result.get("model"),
            result.get("role", "answer"),
            result.get("attempt_no", 1),
            result.get("response_text"),
            result.get("finish_reason"),
            result.get("raw_response_id"),
            input_tokens,
            output_tokens,
            total_tokens,
            cached_tokens,
            cost.get("input_usd", 0),
            cost.get("cached_input_usd", 0),
            cost.get("output_usd", 0),
            cost.get("total_usd", 0),
            int(bool(cost.get("estimated", True))),
            cost.get("pricing_updated_at"),
            cost.get("pricing_source"),
            created_at,
        ),
    )  # Save the executed results to table "model_responses" in SQLite.


def import_jsonl_to_sqlite(jsonl_path: str, db_path: str) -> None:
    """
    Import the LLM's log jsonl file to SQLite Database.
    """
    try:
        conn = sqlite3.connect(db_path)

    except sqlite3.OperationalError:
        print_error(
            f"Failed to connect to database '{db_path}'",
            module="storage_sqlite.py",
            func="import_jsonl_to_sqlite",
        )
        raise

    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        json_records = load_jsonl_file(jsonl_path)

        with conn:
            ensure_audit_columns(conn)
            for json_record in json_records:
                insert_log_record(conn, json_record)

    finally:
        conn.close()

    print("Storing model's responses to SQLite DB is now complete.\n")
