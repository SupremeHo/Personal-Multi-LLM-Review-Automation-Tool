# Service-layer orchestration tests (single ask + multi compare).

from __future__ import annotations

import inspect
import json
import sqlite3
import threading
from datetime import timedelta

import pytest

from resources.call_policy import (
    CONNECT_TIMEOUT_SEC,
    MAX_PARALLEL_CALLS,
    MAX_RETRIES,
    READ_TIMEOUT_SEC,
)
from resources.log_repository import JsonlLogWriter, LogRepository
from resources.providers import registry
from resources.providers.provider_anthropic import AnthropicProvider
from resources.schemas import DEFAULT_MAX_TOKENS, LLMRequest
from resources.services import service_ask as svc
from tests.fakes import (
    AmbiguousBillingProvider,
    BadResultProvider,
    BadSalvageProvider,
    BarrierProvider,
    ConcurrencyProbeProvider,
    EmptyAnswerProvider,
    FailProvider,
    GoodProvider,
    PaidFailProvider,
    ParseFailProvider,
    RejectedCallProvider,
    SlowProvider,
    TruncatedProvider,
    make_result,
)


class _UnavailableSqlite:
    """Stands in for the SQLite sink when the database cannot be written to."""

    sink_name = "sqlite"

    def write(self, log) -> None:
        raise sqlite3.OperationalError("database is locked")

    def write_group(self, manifest) -> None:
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
    assert "nope" in log.error  # the reason, not the string "None"


def test_unavailable_client_is_logged_with_its_reason(monkeypatch):
    # Regression: run_chat's pre-billing guard raises RuntimeError(print_error(...)),
    # and print_error returned None - so a run that failed for the single most
    # common reason (no API key) recorded error_type="RuntimeError" and the
    # literal string "None" as its explanation. A failed run's only record of
    # why it failed was blank.
    #
    # Driven through a real provider with client=None rather than a fake, because
    # the value being checked is produced by runner.run_chat, not by the service.
    monkeypatch.setattr(
        registry, "PROVIDERS", {"anthropic": AnthropicProvider(client=None)}
    )

    log = svc.ask("s", "q", "anthropic", "claude-haiku-4-5", persist=False)

    assert log.success is False
    assert log.error_type == "RuntimeError"
    assert log.error != "None"
    assert "anthropic" in log.error
    assert "API key" in log.error


def test_log_records_the_requested_model_even_when_the_call_fails(fake_providers):
    # A failed run has no result, so without this the audit row cannot say which
    # model was attempted - only which provider.
    ok = svc.ask("s", "q", "good", "m-good", persist=False)
    failed = svc.ask("s", "q", "fail", "m-bad", persist=False)

    assert ok.model == "m-good"
    assert failed.model == "m-bad"


def test_timestamps_are_timezone_aware_utc(fake_providers):
    # Naive local stamps cannot be ordered across a DST change; the CLI converts
    # back to local time for display.
    log = svc.ask("s", "q", "good", "m", persist=False)

    assert log.created_at.utcoffset() == timedelta(0)


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
    # ...whose billing nobody can vouch for - the worker died outside accounting
    assert result.logs[0].billing_status == "unknown"
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
    # (the batch manifest's own write failed too, reported under its own sink)
    assert [e.sink for e in result.persist_errors] == [
        "sqlite",
        "sqlite",
        "sqlite:manifest",
    ]
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


def test_every_max_tokens_default_comes_from_one_constant():
    # The ceiling used to be written as a bare 4096 in four places, and the CLI has
    # no --max-tokens flag, so these service defaults - not the schema's - are what
    # actually reach the provider. Raising only the schema silently changed nothing.
    signatures = [svc.make_request, svc.ask, svc.compare]
    defaults = {
        f.__name__: inspect.signature(f).parameters["max_tokens"].default
        for f in signatures
    }

    assert set(defaults.values()) == {DEFAULT_MAX_TOKENS}, defaults
    assert svc.make_request("s", "q", "m").max_tokens == DEFAULT_MAX_TOKENS


def test_usable_responses_exclude_an_answer_cut_off_mid_sentence(monkeypatch):
    # Measured live on gemini-2.5-flash at the then-default 4096: thinking spent 3928
    # tokens, left 164 for the answer, and it came back finish_reason=MAX_TOKENS
    # truncated. The body is non-empty, so it used to count as a whole answer and
    # carry a vote - a half-formed conclusion presented as cross-checked.
    monkeypatch.setattr(
        registry,
        "PROVIDERS",
        {"good": GoodProvider(), "truncated": TruncatedProvider()},
    )

    result = svc.compare("s", "q", [("good", "m1"), ("truncated", "m2")], persist=False)

    assert len(result.successes) == 2  # both calls worked and were billed...
    assert [r.provider for r in result.usable_responses] == ["good"]
    assert result.collection_status == "insufficient"  # ...but only one can be compared


def test_a_truncated_answer_is_still_logged_and_costed(monkeypatch):
    # Not voting is not the same as being discarded: the paid response keeps its
    # body, its cost and its place in the audit trail, so nothing regresses against
    # the billing invariant. Only the quorum claim is withheld.
    monkeypatch.setattr(
        registry,
        "PROVIDERS",
        {"good": GoodProvider(), "truncated": TruncatedProvider()},
    )

    result = svc.compare("s", "q", [("good", "m1"), ("truncated", "m2")], persist=False)
    truncated = next(log for log in result.logs if log.provider == "truncated")

    assert truncated.success is True
    assert truncated.result.response_text  # the partial answer is still readable
    assert truncated.result.cost is not None
    assert result.audit_status == "clean"  # the money ledger is complete


@pytest.mark.parametrize("reason", ["MAX_TOKENS", "max_tokens", "length"])
def test_every_provider_spelling_of_truncation_is_recognised(reason):
    # Gemini shouts its enum, Anthropic says max_tokens, OpenAI says length.
    result = make_result(
        LLMRequest(
            response_id="rid", system_prompt="s", user_question="q", selected_model="m"
        ),
        finish_reason=reason,
    )

    assert svc.is_truncated(result) is True


def test_a_normally_finished_answer_is_not_truncated():
    result = make_result(
        LLMRequest(
            response_id="rid", system_prompt="s", user_question="q", selected_model="m"
        ),
        finish_reason="stop",
    )

    assert svc.is_truncated(result) is False


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


def _alias_price_table(tmp_path):
    """A price table where m-dated is an alias_of m-canon, like the real ones."""
    price = tmp_path / "prices.json"
    price.write_text(
        json.dumps(
            {
                "updated_at": "2099-01-01",
                "source": "test",
                "models": {
                    "m-canon": {"input": 1.0, "output": 2.0},
                    "m-dated": {"alias_of": "m-canon"},
                },
            }
        ),
        encoding="utf-8",
    )
    return price


def test_compare_rejects_a_duplicate_hidden_behind_a_model_alias(
    fake_providers, monkeypatch, tmp_path
):
    # The price tables alias dated snapshots to their canonical model
    # (gpt-4o-mini-2024-07-18 → gpt-4o-mini), so an exact-string check let the
    # same model in twice under two spellings - two billed calls, one opinion,
    # reported as a quorum. The rejection must name both spellings.
    monkeypatch.setitem(registry.PRICE_PATHS, "good", _alias_price_table(tmp_path))

    with pytest.raises(ValueError, match=r"good:m-canon \+ good:m-dated"):
        svc.compare("s", "q", [("good", "m-canon"), ("good", "m-dated")], persist=False)


def test_compare_alias_check_leaves_distinct_and_unknown_models_alone(
    fake_providers, monkeypatch, tmp_path
):
    # Models the table does not know resolve to themselves: the duplicate check
    # must not reject (or crash on) targets that only preflight can judge.
    monkeypatch.setitem(registry.PRICE_PATHS, "good", _alias_price_table(tmp_path))

    result = svc.compare(
        "s", "q", [("good", "m-dated"), ("good", "m-unknown")], persist=False
    )

    assert len(result.successes) == 2
    # The manifest freezes the resolution, so a later reader can judge
    # independence without the price tables as they were that day.
    assert [t.canonical_model for t in result.manifest.targets] == [
        "m-canon",
        "m-unknown",
    ]
    assert [t.model for t in result.manifest.targets] == ["m-dated", "m-unknown"]


def test_billing_status_is_billed_for_successes_and_paid_failures(fake_providers):
    # A PaidResponseError means the response was received - money moved, however
    # the run was judged.
    assert svc.ask("s", "q", "good", "m", persist=False).billing_status == "billed"
    assert svc.ask("s", "q", "paidfail", "m", persist=False).billing_status == "billed"


def test_billing_status_is_not_billed_when_the_failure_precedes_the_call(
    fake_providers,
):
    # An unknown provider never reaches the API; a provider that raises outside
    # the call boundary (anything but ProviderCallError) is pre-billing too.
    assert svc.ask("s", "q", "nope", "m", persist=False).billing_status == "not_billed"
    assert svc.ask("s", "q", "fail", "m", persist=False).billing_status == "not_billed"


def test_billing_status_is_unknown_when_the_call_died_mid_flight(monkeypatch):
    monkeypatch.setattr(
        registry, "PROVIDERS", {"ambiguous": AmbiguousBillingProvider()}
    )

    log = svc.ask("s", "q", "ambiguous", "m", persist=False)

    assert log.success is False
    assert log.billing_status == "unknown"
    assert log.error_type == "TimeoutError"  # the original failure, not the wrapper


def test_billing_status_is_not_billed_on_a_pre_generation_rejection(monkeypatch):
    monkeypatch.setattr(registry, "PROVIDERS", {"rejected": RejectedCallProvider()})

    log = svc.ask("s", "q", "rejected", "m", persist=False)

    assert log.billing_status == "not_billed"
    assert log.error_type == "ValueError"


def test_audit_status_is_unknown_when_billing_cannot_be_ruled_out(monkeypatch):
    # Before billing_status existed this batch reported "clean": the mid-flight
    # failure left no salvage and no uncosted result, so the ledger claimed to be
    # settled when nobody could actually settle it.
    monkeypatch.setattr(
        registry,
        "PROVIDERS",
        {"good": GoodProvider(), "ambiguous": AmbiguousBillingProvider()},
    )

    result = svc.compare(
        "s",
        "q",
        [("good", "m1"), ("good", "m2"), ("ambiguous", "m3")],
        persist=False,
    )

    assert result.collection_status == "partial"  # the quorum is unaffected
    assert result.audit_status == "unknown"


def test_audit_status_degraded_outranks_unknown(monkeypatch):
    # Known-incomplete is the stronger warning: money verifiably went unaccounted
    # for, and that must not be diluted to "maybe" by a second failure.
    monkeypatch.setattr(
        registry,
        "PROVIDERS",
        {
            "good": GoodProvider(),
            "paidfail": PaidFailProvider(),
            "ambiguous": AmbiguousBillingProvider(),
        },
    )

    result = svc.compare(
        "s",
        "q",
        [("good", "m1"), ("paidfail", "m2"), ("ambiguous", "m3")],
        persist=False,
    )

    assert result.audit_status == "degraded"


def test_audit_status_stays_clean_when_a_failure_verifiably_did_not_bill(monkeypatch):
    # A 4xx rejection is proven free, so it must not drag the ledger to "unknown".
    monkeypatch.setattr(
        registry,
        "PROVIDERS",
        {"good": GoodProvider(), "rejected": RejectedCallProvider()},
    )

    result = svc.compare(
        "s",
        "q",
        [("good", "m1"), ("good", "m2"), ("rejected", "m3")],
        persist=False,
    )

    assert result.audit_status == "clean"


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


def test_compare_persists_a_manifest_describing_the_whole_batch(
    monkeypatch, tmp_path, temp_db
):
    # The runs table records what made it to disk; only the manifest records what
    # SHOULD have. Without it a reader cannot tell a complete group from a
    # truncated or half-archived one.
    monkeypatch.setattr(
        registry, "PROVIDERS", {"good": GoodProvider(), "fail": FailProvider()}
    )
    monkeypatch.setattr(svc, "BASE_DIR", tmp_path)
    monkeypatch.setattr(svc, "DB_PATH", temp_db)

    result = svc.compare("s", "q", [("good", "m1"), ("fail", "m2"), ("good", "m3")])

    manifest, logs = svc.read_group(result.group_id)

    assert manifest is not None
    assert manifest.target_count == 3
    assert manifest.collected_count == 3
    assert manifest.usable_count == 2
    assert manifest.quorum == svc.QUORUM
    assert manifest.collection_status == "partial"
    assert manifest.audit_status == "clean"
    assert manifest.persistence_status == "complete"
    assert manifest.persist_errors == []
    # target order is frozen, and each target points at its runs row
    assert [t.run_id for t in manifest.targets] == [log.run_id for log in logs]
    assert [log.run_id for log in logs] == [log.run_id for log in result.logs]


def test_compare_builds_a_manifest_even_without_persistence(fake_providers):
    # The manifest is the batch's expected shape, not a storage artifact - but it
    # must not claim an archive status nobody attempted.
    result = svc.compare("s", "q", [("good", "m1"), ("good", "m2")], persist=False)

    assert result.manifest is not None
    assert result.manifest.target_count == 2
    assert result.manifest.persistence_status is None


def test_a_lost_manifest_does_not_change_the_runs_verdict(monkeypatch, tmp_path):
    # persistence_status is about the RUN rows; a manifest-only fault must not
    # turn "every run archived" into a failed batch.
    monkeypatch.setattr(registry, "PROVIDERS", {"good": GoodProvider()})

    class _ManifestOnlyFault:
        sink_name = "sqlite"

        def write(self, log) -> None:
            pass  # every run row lands fine

        def write_group(self, manifest) -> None:
            raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(
        svc,
        "default_repository",
        lambda base_dir, db_path: LogRepository([_ManifestOnlyFault()]),
    )

    result = svc.compare("s", "q", [("good", "m1"), ("good", "m2")])

    assert result.persistence_status == "partial"  # the archive IS incomplete...
    assert [e.sink for e in result.persist_errors] == ["sqlite:manifest"]
    # ...but the manifest itself recorded the runs' status from before its own
    # write was attempted - it cannot know its own fate.
    assert result.manifest.persistence_status == "complete"


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
