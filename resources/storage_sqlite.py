# Module for SQLite database management.
# Store them in a SQLite database for later retrieval and analysis.

import json
import sqlite3
import uuid


def load_json(jsonl_path) -> dict:
    """
    Load the jsonl file about LLM's log and convert it into a dict.
    """
    with open(jsonl_path, encoding="utf-8") as file:
        record = json.load(file)
        return record


def insert_log_record(conn: sqlite3.Connection, record: dict) -> None:
    """
    Insert the LLM's log record to the SQLite Database.
    """
    json_record = json.loads(record)  # Convert dict into python object

    result = json_record.get("result") or {}
    usage = result.get("usage") or {}
    cost = result.get("cost") or {}

    run_id = json_record["run_id"]
    created_at = json_record["created_at"]
    raw_json = json.dumps(json_record, ensure_ascii=False)

    response_id = result.get("response_id") or str(uuid.uuid4())

    conn.execute(
        """
        INSERT OR IGNORE INTO runs (
            run_id, created_at, system_prompt, user_prompt, success, error, elapsed_sec, raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            created_at,
            json_record.get("system_prompt", ""),
            json_record.get("user_prompt", ""),
            int(bool(json_record.get("success", False))),
            json.dumps(json_record.get("error"), ensure_ascii=False) if json_record.get("error") is not None else None,
            json_record.get("elapsed_sec"),
            raw_json,
        ),
    )  # Save the executed results to table "run", but ignore run_id if it already exists, and convert success and error values into a form that is easy to store in SQLite.

    conn.execute(
        """
        INSERT INTO model_responses (
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
            response_id,
            run_id,
            result.get("provider"),
            result.get("model"),
            result.get("role", "answer"),
            result.get("attempt_no", 1),
            result.get("response_text"),
            result.get("finish_reason"),
            result.get("raw_response_id"),
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
            usage.get("total_tokens", 0),
            usage.get("cached_tokens", 0),
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
    conn = sqlite3.connect(db_path)

    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        json_record = load_json(jsonl_path)

        with conn:
            record = json.dumps(json_record)
            insert_log_record(conn, record)

    finally:
        conn.close()

    print("\nStoring model's responses to SQLite DB is now complete.\n")


# if __name__ == "__main__":
#     import_jsonl_to_sqlite(JSONL_PATH, DB_PATH)
#     print("Database creation is now complete.")
