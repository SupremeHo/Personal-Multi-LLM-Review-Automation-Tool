# Service-layer orchestration tests (single ask + multi compare).

from __future__ import annotations

import sqlite3
import threading

import pytest

from resources.providers import registry
from resources.services import service_ask as svc
from tests.fakes import (
    BarrierProvider,
    FailProvider,
    GoodProvider,
    PaidFailProvider,
    SlowProvider,
)


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


def test_compare_runs_targets_concurrently(monkeypatch):
    # Every target must be in flight at the same time. The barrier only releases
    # once all three calls have arrived, so a sequential compare() would leave the
    # first one waiting alone, time out, and turn all three into failed logs.
    barrier = threading.Barrier(3, timeout=5)
    monkeypatch.setattr(registry, "PROVIDERS", {"barrier": BarrierProvider(barrier)})

    result = svc.compare(
        "s",
        "q",
        [("barrier", "m1"), ("barrier", "m2"), ("barrier", "m3")],
        persist=False,
    )

    assert len(result.successes) == 3
    assert result.failures == []


def test_compare_keeps_target_order_regardless_of_latency(monkeypatch):
    # Results are collected in submission order, not completion order, so the slow
    # target stays first even though the fast one answers well before it.
    monkeypatch.setattr(
        registry,
        "PROVIDERS",
        {"slow": SlowProvider(0.2), "good": GoodProvider()},
    )

    result = svc.compare("s", "q", [("slow", "m1"), ("good", "m2")], persist=False)

    assert [log.provider for log in result.logs] == ["slow", "good"]
    assert [r.provider for r in result.successes] == ["slow", "good"]


def test_compare_persists_every_call_under_one_group(monkeypatch, tmp_path, temp_db):
    # Regression: a shared run_id used to collapse compare into a single runs row
    # (INSERT OR IGNORE on the UNIQUE run_id), losing the other providers - failed
    # ones vanished entirely. Each call must now leave its own auditable runs row.
    monkeypatch.setattr(
        registry,
        "PROVIDERS",
        {
            "good": GoodProvider(),
            "fail": FailProvider(),
            "paidfail": PaidFailProvider(),
        },
    )
    monkeypatch.setattr(svc, "BASE_DIR", tmp_path)
    monkeypatch.setattr(svc, "DB_PATH", temp_db)

    result = svc.compare("s", "q", [("good", "m1"), ("fail", "m2"), ("paidfail", "m3")])

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


def test_read_history_returns_persisted_calls(monkeypatch, tmp_path, temp_db):
    monkeypatch.setattr(registry, "PROVIDERS", {"good": GoodProvider()})
    monkeypatch.setattr(svc, "BASE_DIR", tmp_path)
    monkeypatch.setattr(svc, "DB_PATH", temp_db)

    svc.ask("s", "q", "good", "m")  # persisted via the default repository

    logs = svc.read_history(limit=5)
    assert len(logs) == 1
    assert logs[0].provider == "good"
    assert logs[0].result.response_text == "ok"
