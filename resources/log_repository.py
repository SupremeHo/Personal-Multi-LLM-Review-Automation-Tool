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
from pathlib import Path
from typing import Protocol

from resources.schemas import LLMCallLog
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
    returns a value; failures propagate as exceptions to the caller.
    """

    def write(self, log: LLMCallLog) -> None: ...


class JsonlLogWriter:
    """Append each log to a per-provider JSONL file under ``<base_dir>/_logs/``."""

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


class LogRepository:
    """Fan one audit log out to every configured writer, in order."""

    def __init__(self, writers: list[LogWriter]):
        self._writers = writers

    def save(self, log: LLMCallLog) -> None:
        for writer in self._writers:
            writer.write(log)


def default_repository(base_dir: Path, db_path: str | Path) -> LogRepository:
    """Production wiring: JSONL archive first, then SQLite."""
    return LogRepository([JsonlLogWriter(base_dir), SqliteLogWriter(db_path)])
