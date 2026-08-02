# Persistence abstraction for audit logs (task A: storage abstraction).
#
# Today the service layer hard-codes the storage pipeline in persist_log():
# it appends the log to a per-provider JSONL file and then calls
# import_jsonl_to_sqlite(), which RE-READS that file from disk to insert it into
# SQLite. The log object is already in memory, so that round-trip is wasted work.
#
# This module introduces a small Repository/Writer seam:
#   * LogWriter     - one destination that knows how to persist a single log.
#   * LogRepository - fans one log out to every configured writer.
#
# The service depends only on LogRepository.save(log); it no longer knows about
# JSONL layout, SQLite connections, or the order of the two. SqliteLogWriter
# inserts straight from the in-memory log, dropping the JSONL round-trip.
#
# NOTE: Query/read support (the `history` command) is deliberately NOT here -
# that is task B. This module covers only the write path (task A).

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Protocol

from resources.schemas import LLMCallLog, PersistenceErrorInfo
from resources.storage_json import append_jsonl
from resources.storage_sqlite import ensure_audit_columns, insert_log_record

# Per-provider on-disk log layout: provider key -> (subdirectory, filename prefix).
# Moved here from service_ask: choosing where a JSONL log lives is the JSONL
# writer's concern, not the orchestration layer's.
LOG_LAYOUT = {
    "openai": ("OpenAI", "gpt"),
    "anthropic": ("Anthropic", "claude"),
    "google": ("Google", "gemini"),
}


class LogWriter(Protocol):
    """
    Structural contract for one persistence destination.

    A writer takes a fully-formed audit log and stores it somewhere. It never
    returns a value; failures propagate as exceptions to the repository, which is
    where they become data.
    """

    sink_name: str
    """Short id of this destination ("jsonl", "sqlite"), used to report failures."""

    def write(self, log: LLMCallLog) -> None: ...


class LogReader(Protocol):
    """
    Structural contract for reading audit logs back.

    Reads come from a single structured store (SQLite), not from every sink, so
    the reader is separate from the writers.
    """

    def recent(
        self, limit: int = 10, group_id: str | None = None
    ) -> list[LLMCallLog]: ...


class JsonlLogWriter:
    """Append each log to a per-provider JSONL file under ``<base_dir>/_logs/``."""

    sink_name = "jsonl"

    def __init__(self, base_dir: Path):
        self._base_dir = base_dir

    def write(self, log: LLMCallLog) -> None:
        dir_name, prefix = LOG_LAYOUT.get(
            log.provider or "", (log.provider or "unknown", log.provider or "log")
        )
        filename = (
            f"{prefix}_response_log_{log.created_at.strftime('%Y%m%d_%H%M%S')}.jsonl"
        )
        path = self._base_dir / "_logs" / dir_name / filename
        append_jsonl(str(path), log)


class SqliteLogWriter:
    """
    Insert each log into SQLite directly from the in-memory object.

    Reuses ensure_audit_columns/insert_log_record, but feeds them
    ``log.model_dump(mode="json")`` instead of re-reading a JSONL file - the
    round-trip that import_jsonl_to_sqlite() incurs on the live path. The dict
    shape is identical to what load_jsonl_file() used to hand insert_log_record,
    so the mapping logic is untouched.
    """

    sink_name = "sqlite"

    def __init__(self, db_path: str | Path):
        self._db_path = str(db_path)

    def write(self, log: LLMCallLog) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("PRAGMA foreign_keys = ON;")
            with conn:  # one transaction; commits on success, rolls back on error
                ensure_audit_columns(conn)
                insert_log_record(conn, log.model_dump(mode="json"))
        finally:
            conn.close()


class SqliteLogReader:
    """
    Read recent audit logs back from SQLite, newest first.

    Each ``runs`` row stores the full log record in ``raw_json``, so a log is
    reconstructed straight into an LLMCallLog - no per-column re-mapping, and
    failed calls (which have a runs row but no model_responses) come back too.
    """

    def __init__(self, db_path: str | Path):
        self._db_path = str(db_path)

    def recent(self, limit: int = 10, group_id: str | None = None) -> list[LLMCallLog]:
        # Order by the autoincrement id (insertion order) so ties within the same
        # created_at second - e.g. calls of one compare - stay deterministic.
        if group_id is None:
            sql = "SELECT raw_json FROM runs ORDER BY id DESC LIMIT ?"
            params: tuple = (limit,)
        else:
            sql = (
                "SELECT raw_json FROM runs WHERE group_id = ? ORDER BY id DESC LIMIT ?"
            )
            params = (group_id, limit)

        conn = sqlite3.connect(self._db_path)
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()

        return [LLMCallLog.model_validate_json(row[0]) for row in rows]


class LogRepository:
    """
    Persistence facade: fan writes out to every writer, and delegate reads to
    the reader. Reads require a reader (built by default_repository); a
    writers-only repository raises if queried.
    """

    def __init__(self, writers: list[LogWriter], reader: LogReader | None = None):
        self._writers = writers
        self._reader = reader

    def save(self, log: LLMCallLog) -> list[PersistenceErrorInfo]:
        """
        Write the log to every destination and report the ones that refused it.

        Two rules, both there because archiving is a side effect of a call that may
        already have been billed:

        * No writer may abort the fan-out. One sink failing says nothing about the
          others, so every one of them is still attempted.
        * A storage fault never raises past the caller's in-memory result. Losing a
          paid response because a disk was full would trade the expensive artifact
          for the cheap one, so failures come back as data instead.

        Each failure carries the sinks that DID accept the log, so the
        JSONL-written-then-SQLite-failed split is recorded as such.
        """
        written: list[str] = []
        failures: list[tuple[str, Exception]] = []

        for writer in self._writers:
            try:
                writer.write(log)
            except Exception as e:  # noqa: BLE001 - a storage fault is data, not a stop signal.
                failures.append((writer.sink_name, e))
            else:
                written.append(writer.sink_name)

        return [
            PersistenceErrorInfo(
                run_id=log.run_id,
                sink=sink,
                error_type=type(error).__name__,
                message=str(error),
                written_sinks=written,
                created_at=datetime.now(),
            )
            for sink, error in failures
        ]

    def recent(self, limit: int = 10, group_id: str | None = None) -> list[LLMCallLog]:
        if self._reader is None:
            raise RuntimeError("[log_repository.py] This repository has no reader.")
        return self._reader.recent(limit, group_id)


def default_repository(base_dir: Path, db_path: str | Path) -> LogRepository:
    """Production wiring: JSONL archive first, then SQLite, with a SQLite reader."""
    return LogRepository(
        [JsonlLogWriter(base_dir), SqliteLogWriter(db_path)],
        reader=SqliteLogReader(db_path),
    )
