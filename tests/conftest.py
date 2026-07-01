"""Shared pytest fixtures."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_SQL = (ROOT / "db" / "_create_table.sql").read_text(encoding="utf-8")


@pytest.fixture
def db_conn():
    """An in-memory SQLite DB initialized from the project schema."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def temp_db(tmp_path):
    """A file-backed SQLite DB (initialized) for code that connects by path."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    return db_path
