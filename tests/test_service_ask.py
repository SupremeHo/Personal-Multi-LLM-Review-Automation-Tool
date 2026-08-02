# Service-layer orchestration tests (single ask + multi compare).

from __future__ import annotations

import sqlite3
import threading

import pytest

from resources.call_policy import (
    CONNECT_TIMEOUT_SEC,
    MAX_PARALLEL_CALLS,
    MAX_RETRIES,
    READ_TIMEOUT_SEC,
)
from resources.log_repository import JsonlLogWriter, LogRepository
from resources.providers import registry
from resources.services import service_ask as svc
from tests.fakes import (
    BadResultProvider,
    BadSalvageProvider,
    BarrierProvider,
    ConcurrencyProbeProvider,
    EmptyAnswerProvider,
    FailProvider,
    GoodProvider,
    PaidFailProvider,
    ParseFailProvider,
    SlowProvider,
)


class _UnavailableSqlite:
    """Stands in for the SQLite sink when the database cannot be written to."""

    sink_name = "sqlite"

    def write(self, log) -> None:
        raise sqlite3.OperationalError("database is locked")


@pytest.fixture
def fake_providers(monkeypatch):
    providers = {
        "good": GoodProvider(),
        "fail": FailProvider(),
        "paidfail": PaidFailProvider(),
        "parsefail": ParseFailProvider(),
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


def test_ask_billed_parse_failure_is_logged_with_salvage(fake_providers):
    # A post-billing parse failure has no result to keep, so without salvage the
    # log would be indistinguishable from a call that never reached the API.
    log = svc.ask("s", "q", "parsefail", "m", persist=False)

    assert log.success is False
    assert log.result is None
    assert log.error_type == "AttributeError"
    assert log.salvage is not None
    assert log.salvage.failed_stage == "parse"
    assert log.salvage.raw_response_id == "raw-parsefail"


def test_billed_parse_failure_survives_persistence_round_trip(
    monkeypatch, tmp_path, temp_db
):
    monkeypatch.setattr(registry, "PROVIDERS", {"parsefail": ParseFailProvider()})
    monkeypatch.setattr(svc, "BASE_DIR", tmp_path)
    monkeypatch.setattr(svc, "DB_PATH", temp_db)

    svc.ask("s", "q", "parsefail", "m")

    conn = sqlite3.connect(temp_db)
    try:
        # A failed run keeps its runs row and skips model_responses (no result).
        assert conn.execute("SELECT count(*) FROM runs").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM model_responses").fetchone()[0] == 0
    finally:
        conn.close()

    (stored,) = svc.read_history(limit=5)
    assert stored.salvage.failed_stage == "parse"
    assert stored.salvage.raw_usage == {"input_tokens": 7}


def test_run_request_never_raises_when_log_assembly_fails(monkeypatch):
    # Regression: LLMCallLog(**log_data) used to sit outside the try, so an invalid
    # field made run_request raise - the 1.5단계 "the failure log itself crashes" bug,
    # and in compare it would take every other target's result down with it.
    monkeypatch.setattr(registry, "PROVIDERS", {"badresult": BadResultProvider()})

    log = svc.run_request("rid", svc.make_request("s", "q", "m"), "badresult")

    assert log.success is False
    assert log.error_type == "LogAssemblyError"
    assert log.result is None
    assert log.run_id == "rid"  # the run stays auditable


def test_log_assembly_fallback_keeps_the_billed_result(monkeypatch):
    # Only the poisoned field may be dropped: a response we already paid for must
    # survive even when the log around it fails to validate.
    monkeypatch.setattr(registry, "PROVIDERS", {"badsalvage": BadSalvageProvider()})

    log = svc.run_request("rid", svc.make_request("s", "q", "m"), "badsalvage")

    assert log.error_type == "LogAssemblyError"
    assert log.salvage is None  # the malformed field is the one that goes
    assert log.result is not None
    assert log.result.response_text == "ok"


def test_compare_isolates_a_worker_that_raises(monkeypatch):
    # Belt and braces: even if run_request somehow raises, future.result() must not
    # abandon the targets after it - their calls were paid for too.
    monkeypatch.setattr(
        registry, "PROVIDERS", {"good": GoodProvider(), "boom": GoodProvider()}
    )
    real_run_request = svc.run_request

    def exploding_run_request(run_id, request, provider_name, *args, **kwargs):
        if provider_name == "boom":
            raise MemoryError("worker died")
        return real_run_request(run_id, request, provider_name, *args, **kwargs)

    monkeypatch.setattr(svc, "run_request", exploding_run_request)

    result = svc.compare("s", "q", [("boom", "m1"), ("good", "m2")], persist=False)

    # the dead worker degrades to a failed log instead of killing the batch...
    assert [log.provider for log in result.logs] == ["boom", "good"]
    assert result.failures[0].error_type == "MemoryError"
    # ...and the target queued behind it still comes back
    assert [r.provider for r in result.successes] == ["good"]


def test_compare_survives_a_storage_fault_and_records_it(monkeypatch, tmp_path):
    # A locked database used to end compare() on the first persist_log() call,
    # dropping every target still unread - responses that were already billed.
    monkeypatch.setattr(
        registry, "PROVIDERS", {"good": GoodProvider(), "slow": SlowProvider(0.05)}
    )
    monkeypatch.setattr(
        svc,
        "default_repository",
        lambda base_dir, db_path: LogRepository(
            [JsonlLogWriter(tmp_path), _UnavailableSqlite()]
        ),
    )

    result = svc.compare("s", "q", [("good", "m1"), ("slow", "m2")])

    # every target still comes back...
    assert [r.provider for r in result.successes] == ["good", "slow"]
    assert result.failures == []  # a storage fault is not a failed call
    # ...and the archive fault is data, including which sink did accept the log
    assert [e.sink for e in result.persist_errors] == ["sqlite", "sqlite"]
    assert result.persist_errors[0].written_sinks == ["jsonl"]
    # the sink that did work still archived both logs (one file per provider)
    assert len(list((tmp_path / "_logs").rglob("*.jsonl"))) == 2


def test_ask_returns_its_log_even_when_archiving_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(registry, "PROVIDERS", {"good": GoodProvider()})
    monkeypatch.setattr(
        svc,
        "default_repository",
        lambda base_dir, db_path: LogRepository([_UnavailableSqlite()]),
    )

    log = svc.ask("s", "q", "good", "m")

    assert log.success is True
    assert log.result.response_text == "ok"


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


def test_compare_keeps_salvage_of_an_unparsable_billed_response(fake_providers):
    # Aggregation must not drop what the paid call left behind when there is no
    # partial_result to carry - otherwise compare() discards a billed response.
    result = svc.compare("s", "q", [("good", "m1"), ("parsefail", "m2")], persist=False)

    (failure,) = result.failures
    assert failure.provider == "parsefail"
    assert failure.partial_result is None
    assert failure.salvage.failed_stage == "parse"


def test_usable_responses_include_a_billed_but_uncosted_answer(fake_providers):
    # A PaidResponseError partial has an intact body - only its price tag is
    # missing - so excluding it would shrink the quorum for a bookkeeping reason.
    result = svc.compare("s", "q", [("good", "m1"), ("paidfail", "m2")], persist=False)

    assert len(result.successes) == 1  # the call is still judged a failure...
    assert [r.provider for r in result.usable_responses] == ["good", "paidfail"]
    assert result.collection_status == "complete"  # ...but the batch is comparable
    assert result.audit_status == "degraded"  # spend that could not be costed


def test_usable_responses_exclude_a_body_that_cannot_be_read(fake_providers):
    # Parsing failed: money was spent but there is no answer to compare.
    result = svc.compare("s", "q", [("good", "m1"), ("parsefail", "m2")], persist=False)

    assert [r.provider for r in result.usable_responses] == ["good"]
    assert result.collection_status == "insufficient"
    assert result.audit_status == "degraded"  # billed, never accounted for


def test_usable_responses_exclude_an_empty_answer(monkeypatch):
    # An empty body padding the quorum is exactly the false confidence this tool
    # exists to prevent, however successful the call was judged.
    monkeypatch.setattr(
        registry, "PROVIDERS", {"good": GoodProvider(), "empty": EmptyAnswerProvider()}
    )

    result = svc.compare("s", "q", [("good", "m1"), ("empty", "m2")], persist=False)

    assert len(result.successes) == 2  # both calls worked...
    assert [r.provider for r in result.usable_responses] == ["good"]
    assert result.collection_status == "insufficient"  # ...but there is no comparison


def test_a_lone_success_is_insufficient_not_complete(fake_providers):
    # One answer has nothing to be compared against.
    result = svc.compare("s", "q", [("good", "m1")], persist=False)

    assert result.successes  # the call was fine
    assert result.collection_status == "insufficient"


def test_collection_status_is_partial_when_the_quorum_survives_a_failure(
    fake_providers,
):
    result = svc.compare(
        "s", "q", [("good", "m1"), ("good", "m2"), ("fail", "m3")], persist=False
    )

    assert len(result.usable_responses) == 2
    assert result.collection_status == "partial"
    assert result.audit_status == "clean"  # a call that never billed is not a gap


def test_persistence_status_is_none_when_archiving_was_not_attempted(fake_providers):
    # "complete" would be a false claim about an archive nobody wrote.
    result = svc.compare("s", "q", [("good", "m1"), ("good", "m2")], persist=False)

    assert result.persistence_status is None


def test_persistence_status_reports_a_partial_archive(monkeypatch, tmp_path):
    monkeypatch.setattr(registry, "PROVIDERS", {"good": GoodProvider()})
    monkeypatch.setattr(
        svc,
        "default_repository",
        lambda base_dir, db_path: LogRepository(
            [JsonlLogWriter(tmp_path), _UnavailableSqlite()]
        ),
    )

    result = svc.compare("s", "q", [("good", "m1"), ("good", "m2")])

    assert result.persistence_status == "partial"  # JSONL landed, SQLite did not
    assert result.collection_status == "complete"  # and the answers are unaffected


def test_persistence_status_is_failed_when_nothing_landed(monkeypatch):
    monkeypatch.setattr(registry, "PROVIDERS", {"good": GoodProvider()})
    monkeypatch.setattr(
        svc,
        "default_repository",
        lambda base_dir, db_path: LogRepository([_UnavailableSqlite()]),
    )

    result = svc.compare("s", "q", [("good", "m1"), ("good", "m2")])

    assert result.persistence_status == "failed"


def test_compare_rejects_duplicate_targets(fake_providers):
    # Asking the same model twice buys a second billed answer that would inflate
    # the quorum with a correlated opinion. Refused before anything is paid for.
    with pytest.raises(ValueError, match="Duplicate compare targets"):
        svc.compare(
            "s", "q", [("good", "m1"), ("good", "m1"), ("fail", "m2")], persist=False
        )


def test_compare_caps_the_number_of_parallel_calls(monkeypatch):
    # --target is repeatable with no limit, so an uncapped pool turns a typo into a
    # burst of concurrent requests. Every target still runs, just not all at once.
    probe = ConcurrencyProbeProvider()
    monkeypatch.setattr(registry, "PROVIDERS", {"probe": probe})
    targets = [("probe", f"m{i}") for i in range(MAX_PARALLEL_CALLS + 3)]

    result = svc.compare("s", "q", targets, persist=False)

    assert len(result.successes) == len(targets)  # nothing is dropped by the cap
    assert probe.peak <= MAX_PARALLEL_CALLS
    assert probe.peak > 1  # ...and the calls are still parallel


def test_log_records_the_policy_a_call_was_made_under(fake_providers):
    # "Timed out" means something different under a 10s budget than a 300s one, so
    # the budget in effect travels with the log.
    log = svc.ask("s", "q", "good", "m", persist=False)

    assert log.policy.connect_timeout_sec == CONNECT_TIMEOUT_SEC
    assert log.policy.read_timeout_sec == READ_TIMEOUT_SEC
    assert log.policy.max_retries == MAX_RETRIES


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
