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
from resources.schemas import (
    ComparisonManifest,
    ComparisonTarget,
    LLMCallLog,
    LLMCallResult,
    TokenUsageInfo,
)


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


def _manifest(
    group_id: str = "g1", run_ids: tuple[str, ...] = ("run-1",)
) -> ComparisonManifest:
    return ComparisonManifest(
        group_id=group_id,
        created_at=datetime(2026, 7, 21, 10, 30, 0),
        targets=[
            ComparisonTarget(
                provider="openai", model="m", canonical_model="m", run_id=r
            )
            for r in run_ids
        ],
        target_count=len(run_ids),
        collected_count=len(run_ids),
        usable_count=len(run_ids),
        quorum=2,
        collection_status="insufficient",
        audit_status="clean",
        persistence_status="complete",
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


class _Recorder:
    """A writer that just notes it was called."""

    def __init__(self, sink_name: str, seen: list[tuple[str, str]]):
        self.sink_name = sink_name
        self._seen = seen

    def write(self, log: LLMCallLog) -> None:
        self._seen.append((self.sink_name, log.run_id))


class _BoomWriter:
    """A writer whose destination is unavailable (full disk, locked db, ...)."""

    def __init__(self, sink_name: str):
        self.sink_name = sink_name

    def write(self, log: LLMCallLog) -> None:
        raise OSError(f"{self.sink_name} is unavailable")


def test_repository_fans_out_to_all_writers_in_order():
    seen: list[tuple[str, str]] = []

    errors = LogRepository([_Recorder("a", seen), _Recorder("b", seen)]).save(_log())

    assert seen == [("a", "run-1"), ("b", "run-1")]
    assert errors == []


def test_repository_records_a_split_between_sinks_instead_of_raising():
    # The JSONL-written-then-SQLite-failed case: the archive is now inconsistent,
    # and that fact has to be recorded rather than discovered later. Raising here
    # would also destroy a response the caller may already have paid for.
    seen: list[tuple[str, str]] = []

    errors = LogRepository([_Recorder("jsonl", seen), _BoomWriter("sqlite")]).save(
        _log()
    )

    (error,) = errors
    assert error.run_id == "run-1"
    assert error.sink == "sqlite"
    assert error.error_type == "OSError"
    assert error.written_sinks == ["jsonl"]  # the log is split across stores


def test_repository_attempts_every_sink_even_after_one_fails():
    # One destination failing says nothing about the others, so the fan-out must
    # not stop at the first error.
    seen: list[tuple[str, str]] = []

    errors = LogRepository([_BoomWriter("jsonl"), _Recorder("sqlite", seen)]).save(
        _log()
    )

    assert seen == [("sqlite", "run-1")]  # the second writer still ran
    assert [e.sink for e in errors] == ["jsonl"]
    assert errors[0].written_sinks == ["sqlite"]


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


def test_sqlite_writer_round_trips_a_group_manifest(temp_db):
    writer = SqliteLogWriter(temp_db)
    writer.write(_log(run_id="r1", response_id="a1", group_id="g1"))
    writer.write_group(_manifest(group_id="g1", run_ids=("r1",)))

    manifest, logs = SqliteLogReader(temp_db).read_group("g1")

    assert manifest is not None
    assert manifest.target_count == 1
    assert manifest.targets[0].run_id == "r1"
    assert [log.run_id for log in logs] == ["r1"]


def test_read_group_returns_every_row_in_target_order(temp_db):
    # The trap this exists to close: recent()'s LIMIT (default 10) silently
    # truncated any larger batch into a complete-looking subset, newest first.
    # A group read must be the whole batch, in the order the targets ran.
    writer = SqliteLogWriter(temp_db)
    for i in range(12):
        writer.write(_log(run_id=f"r{i}", response_id=f"a{i}", group_id="g"))

    truncated = SqliteLogReader(temp_db).recent(group_id="g")
    _, whole = SqliteLogReader(temp_db).read_group("g")

    assert len(truncated) == 10  # the old read really does drop rows
    assert [log.run_id for log in whole] == [f"r{i}" for i in range(12)]


def test_read_group_of_an_unknown_group_is_empty_not_an_error(temp_db):
    manifest, logs = SqliteLogReader(temp_db).read_group("missing")

    assert manifest is None
    assert logs == []


def test_read_group_survives_a_pre_manifest_database(temp_db):
    # Databases from before comparison_groups existed have no such table at all;
    # the group's runs must still come back, with the manifest simply absent.
    conn = sqlite3.connect(temp_db)
    conn.execute("DROP TABLE comparison_groups")
    conn.commit()
    conn.close()
    SqliteLogWriter(temp_db).write(_log(run_id="r1", response_id="a1", group_id="g1"))

    manifest, logs = SqliteLogReader(temp_db).read_group("g1")

    assert manifest is None
    assert [log.run_id for log in logs] == ["r1"]


def test_reader_skips_an_unreadable_row_instead_of_dying(temp_db):
    # Regression: one row an older schema wrote (or a corrupted one) used to take
    # the whole query down - history died as soon as it entered the LIMIT window.
    writer = SqliteLogWriter(temp_db)
    for i in range(3):
        writer.write(_log(run_id=f"r{i}", response_id=f"a{i}", group_id="g"))
    conn = sqlite3.connect(temp_db)
    conn.execute(
        "UPDATE runs SET raw_json = '{\"run_id\": \"r1\"}' WHERE run_id = 'r1'"
    )
    conn.commit()
    conn.close()

    recent = SqliteLogReader(temp_db).recent(limit=10)
    _, whole = SqliteLogReader(temp_db).read_group("g")

    assert [log.run_id for log in recent] == ["r2", "r0"]  # r1 skipped, not fatal
    assert [log.run_id for log in whole] == ["r0", "r2"]


class _BoomGroupWriter:
    """A sqlite-shaped writer whose manifest write fails."""

    sink_name = "sqlite"

    def write(self, log: LLMCallLog) -> None:  # pragma: no cover - unused here
        pass

    def write_group(self, manifest: ComparisonManifest) -> None:
        raise OSError("sqlite is unavailable")


def test_save_group_skips_incapable_writers_and_reports_faults():
    # JSONL has no place for a batch-level manifest, so a writer without
    # write_group is skipped - not failed. A capable writer that breaks reports
    # a sink tagged ":manifest" so a lost manifest is not read as a lost run.
    errors = LogRepository([_Recorder("jsonl", []), _BoomGroupWriter()]).save_group(
        _manifest(group_id="g1")
    )

    (error,) = errors
    assert error.sink == "sqlite:manifest"
    assert error.run_id == "g1"  # the only id a manifest has
    assert error.error_type == "OSError"


def test_repository_recent_reads_back_a_saved_log(tmp_path, temp_db):
    repo = default_repository(tmp_path, temp_db)
    repo.save(_log(run_id="r1", response_id="a1"))

    logs = repo.recent(limit=5)
    assert [log.run_id for log in logs] == ["r1"]


def test_repository_without_reader_rejects_recent():
    repo = LogRepository([])  # writers-only, no reader
    with pytest.raises(RuntimeError):
        repo.recent()
