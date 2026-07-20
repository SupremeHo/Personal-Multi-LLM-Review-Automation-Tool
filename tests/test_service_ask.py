# Service-layer orchestration tests (single ask + multi compare).

from __future__ import annotations

import sqlite3

import pytest

from resources.providers import registry
from resources.services import service_ask as svc
from tests.fakes import FailProvider, GoodProvider, PaidFailProvider


@pytest.fixture
def fake_providers(monkeypatch):
    providers = {
        "good": GoodProvider(),
        "fail": FailProvider(),
        "paidfail": PaidFailProvider(),
    }
    monkeypatch.setattr(registry, "PROVIDERS", providers)
    return providers


def test_ask_success(fake_providers):
    log = svc.ask("s", "q", "good", "m", persist=False)
    assert log.success is True
    assert log.result.response_text == "ok"
    assert log.provider == "good"
    assert log.elapsed_sec is not None


def test_ask_unknown_provider_is_logged_failure(fake_providers):
    log = svc.ask("s", "q", "nope", "m", persist=False)
    assert log.success is False
    assert log.error_type == "KeyError"
    assert log.result is None


def test_compare_collects_successes_and_failures(fake_providers):
    result = svc.compare(
        "s",
        "q",
        [("good", "m1"), ("fail", "m2"), ("paidfail", "m3")],
        persist=False,
    )
    # each call has its own run_id, but all share one group_id
    assert len({log.run_id for log in result.logs}) == 3
    assert {log.group_id for log in result.logs} == {result.group_id}
    assert len(result.logs) == 3
    assert len(result.successes) == 1
    assert len(result.failures) == 2

    by_provider = {f.provider: f for f in result.failures}
    assert by_provider["fail"].error_type == "RuntimeError"
    # PaidResponseError keeps the billed response as data.
    assert by_provider["paidfail"].partial_result is not None
    assert by_provider["paidfail"].partial_result.response_text == "ok"


def test_compare_persists_every_call_under_one_group(monkeypatch, tmp_path, temp_db):
    # Regression: a shared run_id used to collapse compare into a single runs row
    # (INSERT OR IGNORE on the UNIQUE run_id), losing the other providers - failed
    # ones vanished entirely. Each call must now leave its own auditable runs row.
    monkeypatch.setattr(
        registry,
        "PROVIDERS",
        {"good": GoodProvider(), "fail": FailProvider(), "paidfail": PaidFailProvider()},
    )
    monkeypatch.setattr(svc, "BASE_DIR", tmp_path)
    monkeypatch.setattr(svc, "DB_PATH", temp_db)

    result = svc.compare(
        "s", "q", [("good", "m1"), ("fail", "m2"), ("paidfail", "m3")]
    )

    conn = sqlite3.connect(temp_db)
    try:
        rows = conn.execute("SELECT run_id, group_id FROM runs").fetchall()
    finally:
        conn.close()

    # every provider (including the failed one) left a distinct runs row...
    assert len(rows) == 3
    assert len({run_id for run_id, _ in rows}) == 3
    # ...all tied together by the single shared group_id
    assert {group_id for _, group_id in rows} == {result.group_id}


def test_ask_persists_to_db_and_jsonl(monkeypatch, tmp_path, temp_db):
    monkeypatch.setattr(registry, "PROVIDERS", {"good": GoodProvider()})
    monkeypatch.setattr(svc, "BASE_DIR", tmp_path)
    monkeypatch.setattr(svc, "DB_PATH", temp_db)

    svc.ask("s", "q", "good", "m")  # persist=True by default

    conn = sqlite3.connect(temp_db)
    try:
        assert conn.execute("SELECT count(*) FROM runs").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM model_responses").fetchone()[0] == 1
    finally:
        conn.close()

    jsonl_files = list((tmp_path / "_logs").rglob("*.jsonl"))
    assert len(jsonl_files) == 1
