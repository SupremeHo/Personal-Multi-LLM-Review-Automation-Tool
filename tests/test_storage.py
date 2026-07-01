"""Storage tests: schema-to-DB token mapping and idempotency."""

from __future__ import annotations

from datetime import datetime

from resources.schemas import LLMCallLog, LLMCallResult, TokenUsageInfo
from resources.storage_sqlite import ensure_audit_columns, insert_log_record


def _log_record(usage: TokenUsageInfo, provider="openai", response_id="resp1"):
    log = LLMCallLog(
        run_id="run1",
        created_at=datetime.now(),
        provider=provider,
        system_prompt="s",
        user_prompt="q",
        success=True,
        result=LLMCallResult(
            response_id=response_id,
            provider=provider,
            model="m",
            response_text="t",
            usage=usage,
        ),
    )
    return log.model_dump(mode="json")


def test_openai_token_mapping(db_conn):
    usage = TokenUsageInfo(
        input_tokens=100, output_tokens=50, total_tokens=150, cached_input_tokens=20
    )
    insert_log_record(db_conn, _log_record(usage))

    row = db_conn.execute(
        "SELECT prompt_tokens, completion_tokens, total_tokens, cached_tokens "
        "FROM model_responses"
    ).fetchone()
    assert row == (100, 50, 150, 20)


def test_anthropic_total_derived_and_cache_summed(db_conn):
    usage = TokenUsageInfo(
        input_tokens=200,
        output_tokens=80,
        cache_creation_input_tokens=30,
        cache_read_input_tokens=10,
    )
    insert_log_record(db_conn, _log_record(usage, provider="anthropic"))

    row = db_conn.execute(
        "SELECT prompt_tokens, completion_tokens, total_tokens, cached_tokens "
        "FROM model_responses"
    ).fetchone()
    # total derived (200+80) and the split cache fields summed (30+10)
    assert row == (200, 80, 280, 40)


def test_failed_run_writes_only_runs_row(db_conn):
    log = LLMCallLog(
        run_id="run-failed",
        created_at=datetime.now(),
        provider="openai",
        system_prompt="s",
        user_prompt="q",
        success=False,
        error="boom",
        error_type="RuntimeError",
    )
    insert_log_record(db_conn, log.model_dump(mode="json"))

    assert db_conn.execute("SELECT count(*) FROM runs").fetchone()[0] == 1
    assert db_conn.execute("SELECT count(*) FROM model_responses").fetchone()[0] == 0


def test_reimport_is_idempotent(db_conn):
    usage = TokenUsageInfo(input_tokens=1, output_tokens=1, total_tokens=2)
    record = _log_record(usage)
    insert_log_record(db_conn, record)
    insert_log_record(db_conn, record)  # same UUIDs -> INSERT OR IGNORE

    assert db_conn.execute("SELECT count(*) FROM runs").fetchone()[0] == 1
    assert db_conn.execute("SELECT count(*) FROM model_responses").fetchone()[0] == 1


def test_ensure_audit_columns_is_idempotent(db_conn):
    ensure_audit_columns(db_conn)
    ensure_audit_columns(db_conn)  # second call must not error
    columns = {row[1] for row in db_conn.execute("PRAGMA table_info(runs)")}
    assert {"provider", "error_type"} <= columns
