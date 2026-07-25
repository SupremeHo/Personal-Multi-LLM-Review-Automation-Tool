# Storage-abstraction tests: writers persist a log, repository fans out.

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

import pytest

from resources.log_repository import (
    JsonlLogWriter,
    LogRepository,
    SqliteLogReader,
    SqliteLogWriter,
    default_repository,
)
from resources.schemas import LLMCallLog, LLMCallResult, TokenUsageInfo


def _log(
    provider: str = "openai",
    response_id: str = "resp-1",
    run_id: str = "run-1",
    group_id: str | None = None,
) -> LLMCallLog:
    return LLMCallLog(
        run_id=run_id,
        group_id=group_id,
        created_at=datetime(2026, 7, 21, 10, 30, 0),
        provider=provider,
        system_prompt="s",
        user_prompt="q",
        success=True,
        result=LLMCallResult(
            response_id=response_id,
            provider=provider,
            model="m",
            response_text="t",
            usage=TokenUsageInfo(input_tokens=1, output_tokens=1, total_tokens=2),
        ),
    )


def test_sqlite_writer_inserts_straight_from_log(temp_db):
    # The writer takes only the in-memory log + db path (no JSONL path at all),
    # so it cannot re-read a file - it inserts directly from the object.
    SqliteLogWriter(temp_db).write(_log())

    conn = sqlite3.connect(temp_db)
    try:
        assert conn.execute("SELECT count(*) FROM runs").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM model_responses").fetchone()[0] == 1
    finally:
        conn.close()


def test_jsonl_writer_writes_per_provider_file(tmp_path):
    JsonlLogWriter(tmp_path).write(_log(provider="anthropic"))

    files = list((tmp_path / "_logs" / "Anthropic").glob("*.jsonl"))
    assert len(files) == 1
    assert files[0].name.startswith("claude_response_log_")

    record = json.loads(files[0].read_text(encoding="utf-8").strip())
    assert record["run_id"] == "run-1"
    assert record["provider"] == "anthropic"


def test_repository_fans_out_to_all_writers_in_order():
    seen: list[tuple[str, str]] = []

    class Recorder:
        def __init__(self, tag: str):
            self.tag = tag

        def write(self, log: LLMCallLog) -> None:
            seen.append((self.tag, log.run_id))

    LogRepository([Recorder("a"), Recorder("b")]).save(_log())

    assert seen == [("a", "run-1"), ("b", "run-1")]


def test_default_repository_writes_both_sinks(tmp_path, temp_db):
    default_repository(tmp_path, temp_db).save(_log(provider="openai"))

    assert list((tmp_path / "_logs").rglob("*.jsonl"))  # JSONL archived
    conn = sqlite3.connect(temp_db)
    try:
        assert (
            conn.execute("SELECT count(*) FROM runs").fetchone()[0] == 1
        )  # and SQLite
    finally:
        conn.close()


def test_sqlite_reader_returns_recent_newest_first(temp_db):
    writer = SqliteLogWriter(temp_db)
    writer.write(_log(run_id="r1", response_id="a1"))
    writer.write(_log(run_id="r2", response_id="a2"))
    writer.write(_log(run_id="r3", response_id="a3"))

    logs = SqliteLogReader(temp_db).recent(limit=2)

    assert [log.run_id for log in logs] == ["r3", "r2"]  # newest first, limited
    assert all(isinstance(log, LLMCallLog) for log in logs)
    # reconstructed from raw_json, so the nested result round-trips too
    assert logs[0].result.response_text == "t"


def test_sqlite_reader_filters_by_group(temp_db):
    writer = SqliteLogWriter(temp_db)
    writer.write(_log(run_id="r1", response_id="a1", group_id="g1"))
    writer.write(_log(run_id="r2", response_id="a2", group_id="g1"))
    writer.write(_log(run_id="r3", response_id="a3", group_id="g2"))

    logs = SqliteLogReader(temp_db).recent(group_id="g1")

    assert {log.run_id for log in logs} == {"r1", "r2"}
    assert all(log.group_id == "g1" for log in logs)


def test_repository_recent_reads_back_a_saved_log(tmp_path, temp_db):
    repo = default_repository(tmp_path, temp_db)
    repo.save(_log(run_id="r1", response_id="a1"))

    logs = repo.recent(limit=5)
    assert [log.run_id for log in logs] == ["r1"]


def test_repository_without_reader_rejects_recent():
    repo = LogRepository([])  # writers-only, no reader
    with pytest.raises(RuntimeError):
        repo.recent()
