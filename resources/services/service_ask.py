# Service layer: turns a high-level request into provider calls and audit logs.
#
# Responsibilities:
#   * Own identity generation (run_id, group_id, response_id) in one place, then
#     inject it into the provider request (the provider never mints ids).
#   * Resolve providers through the registry only (never import a concrete one).
#   * Turn each call's outcome into data: an LLMCallLog always, plus an ErrorInfo
#     for failures in the multi-compare flow so one failure never stops the rest.
#   * Archive each log to JSONL + SQLite via persist_log().

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from resources.call_policy import (
    CONNECT_TIMEOUT_SEC,
    MAX_PARALLEL_CALLS,
    MAX_RETRIES,
    READ_TIMEOUT_SEC,
)
from resources.count_cost import canonical_model_name, load_price_table
from resources.diagnostics import print_error
from resources.log_repository import default_repository
from resources.providers.registry import PRICE_PATHS, get_provider
from resources.providers.response_error import PaidResponseError, ProviderCallError
from resources.schemas import (
    DEFAULT_MAX_TOKENS,
    AuditStatus,
    CallPolicyInfo,
    CollectionStatus,
    ErrorInfo,
    LLMCallLog,
    LLMCallResult,
    LLMRequest,
    PersistenceErrorInfo,
    PersistenceStatus,
    SalvageInfo,
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "_db" / "llm_responses.db"

TRUNCATED_FINISH_REASONS = frozenset({"length", "max_tokens"})
"""
The finish reasons that mean "the model was cut off mid-answer".

One entry per provider's spelling, compared lowercased because Gemini shouts its
enum: OpenAI says `length`, Anthropic `max_tokens`, Gemini `MAX_TOKENS`.

This matters because reasoning shares the max_tokens ceiling with the answer, so
truncation stopped being an edge case: measured on gemini-2.5-flash at the
then-default 4096, a puzzle question spent 3928 tokens thinking and had the answer
cut off with 164 left. The body is non-empty, so without this the cut-off text
counted as a whole answer. The ceiling is now DEFAULT_MAX_TOKENS (16,384), which
buys room but does not remove the coupling - the CLI's default model reasons too.
"""


def is_truncated(result: LLMCallResult) -> bool:
    """Whether the model ran out of room before it finished answering."""
    reason = result.finish_reason
    return reason is not None and reason.lower() in TRUNCATED_FINISH_REASONS


def _canonical_target(provider_name: str, model: str) -> tuple[str, str]:
    """
    Resolve a target's model to its canonical price-table name, for the
    duplicate check only.

    Best-effort and free by design: an unknown provider, a missing/broken price
    file, or a model the table does not know all resolve to the target itself.
    Failing those cases is preflight_pricing's job (after this check, still
    before billing) - and the actual request keeps the user's spelling either
    way, so the audit log records what was asked for.
    """
    price_path = PRICE_PATHS.get(provider_name)
    if price_path is None:
        return (provider_name, model)

    try:
        price_table = load_price_table(price_path)
    except Exception:  # noqa: BLE001 - the duplicate check must stay free; preflight owns this failure.
        return (provider_name, model)

    return (provider_name, canonical_model_name(price_table, model))


def _current_policy() -> CallPolicyInfo:
    """Snapshot the configured resource policy for the audit log."""
    return CallPolicyInfo(
        max_parallel_calls=MAX_PARALLEL_CALLS,
        connect_timeout_sec=CONNECT_TIMEOUT_SEC,
        read_timeout_sec=READ_TIMEOUT_SEC,
        max_retries=MAX_RETRIES,
    )


def make_request(
    system_prompt: str,
    user_question: str,
    selected_model: str,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> LLMRequest:
    """Build an LLMRequest with a freshly minted response_id (service owns identity)."""
    return LLMRequest(
        response_id=str(uuid4()),
        system_prompt=system_prompt,
        user_question=user_question,
        selected_model=selected_model,
        max_tokens=max_tokens,
    )


def _assemble_log(log_data: dict) -> LLMCallLog:
    """
    Turn the collected log fields into an LLMCallLog without ever raising.

    Building the log is itself a failure point - 1.5단계 lost a whole run when the
    error branch assembled an invalid dict - and LLMCallLog forbids extras, so one
    badly typed field is a ValidationError. Letting that escape would break
    run_request's "never raises" contract and, inside compare, abandon the other
    targets' already-billed results.

    Every entry in log_data except `result` and `salvage` is written by this layer
    from already-validated values; those two are the only ones that come from a
    provider. So the fallback drops whichever of them is not the object it claims
    to be - keeping a genuinely billed result - and records why the log degraded.
    """
    try:
        return LLMCallLog(**log_data)

    except Exception as e:  # noqa: BLE001 - a broken log must still be a log.
        print_error(
            f"Audit log assembly failed - {e}",
            module="service_ask.py",
            func="_assemble_log",
        )
        result = log_data.get("result")
        salvage = log_data.get("salvage")
        return LLMCallLog(
            **{
                **log_data,
                "success": False,
                "error": f"Audit log assembly failed: {e}",
                "error_type": "LogAssemblyError",
                "result": result if isinstance(result, LLMCallResult) else None,
                "salvage": salvage if isinstance(salvage, SalvageInfo) else None,
            }
        )


def run_request(
    run_id: str,
    request: LLMRequest,
    provider_name: str,
    created_at: datetime | None = None,
    group_id: str | None = None,
) -> LLMCallLog:
    """
    Execute one provider call and assemble its audit log.

    The log is built once up front and filled in place, so it is always returned
    - on success, on a salvaged partial failure (PaidResponseError), or on any
    other failure - with elapsed_sec recorded either way. Assembling it is routed
    through _assemble_log so this function never raises, which is what lets
    compare() run it in a worker thread.

    `group_id` ties this call to a comparison batch; None for a single ask.
    """
    # Stamped in UTC: an audit trail that outlives a DST change or a trip abroad
    # cannot be ordered by naive local times. The CLI converts back for display.
    created_at = created_at or datetime.now(UTC)

    log_data = {
        "run_id": run_id,
        "group_id": group_id,
        "created_at": created_at,
        "provider": provider_name,
        "model": request.selected_model,
        "system_prompt": request.system_prompt,
        "user_prompt": request.user_question,
        "success": False,
        "error": None,
        "error_type": None,
        "elapsed_sec": None,
        "result": None,
        "salvage": None,
        "policy": _current_policy(),
        # Anything that fails without reaching (or inside the safe part of) the
        # paid call keeps this default; the branches below overwrite it the
        # moment the call boundary reports otherwise.
        "billing_status": "not_billed",
    }

    start_time = time.perf_counter()
    try:
        provider = get_provider(provider_name)
        result = provider.ask(request)
        log_data["success"] = True
        log_data["result"] = result
        log_data["billing_status"] = "billed"

    except PaidResponseError as e:
        # The paid call succeeded but a later step failed. Judge the run a failure,
        # yet preserve whatever survived so no billed call goes unlogged: the full
        # response when only cost calculation broke, otherwise the salvage
        # diagnostics proving the money was spent.
        log_data["result"] = e.result
        log_data["salvage"] = e.salvage
        log_data["error"] = str(e.original)
        log_data["error_type"] = type(e.original).__name__
        log_data["billing_status"] = "billed"

    except ProviderCallError as e:
        # The paid call itself failed. Only the call boundary can judge whether a
        # response may still have been generated (and billed); record its verdict
        # instead of letting "the call failed" read as "nothing was spent".
        log_data["error"] = str(e.original)
        log_data["error_type"] = type(e.original).__name__
        log_data["billing_status"] = "unknown" if e.billing_possible else "not_billed"

    except Exception as e:  # noqa: BLE001 - any failure must still produce an audit log.
        log_data["error"] = str(e)
        log_data["error_type"] = type(e).__name__

    finally:
        log_data["elapsed_sec"] = round(time.perf_counter() - start_time, 3)

    return _assemble_log(log_data)


def persist_log(log: LLMCallLog) -> list[PersistenceErrorInfo]:
    """
    Archive one audit log through the default repository (JSONL + SQLite).

    The log is always written - success or failure - so every run, including
    billed-but-failed ones, leaves an auditable record. The repository is built
    from the current module paths on each call so tests can redirect BASE_DIR /
    DB_PATH before persisting.

    Storage faults are returned as data rather than raised (see LogRepository.save),
    and each one is printed the moment it happens so a failed archive can never pass
    unnoticed - the caller is holding a response that may already have been paid for.
    """
    errors = default_repository(BASE_DIR, DB_PATH).save(log)

    for error in errors:
        stored_elsewhere = (
            f" (already stored in: {', '.join(error.written_sinks)})"
            if error.written_sinks
            else ""
        )
        print_error(
            f"Archiving run {error.run_id} to {error.sink} failed{stored_elsewhere} - {error.message}",
            module="service_ask.py",
            func="persist_log",
        )

    return errors


def read_history(limit: int = 10, group_id: str | None = None) -> list[LLMCallLog]:
    """
    Read the most recent audit logs (newest first) via the default repository.

    Pass group_id to see only the calls of one comparison. Built from the module
    paths on each call, mirroring persist_log so tests can redirect DB_PATH.
    """
    return default_repository(BASE_DIR, DB_PATH).recent(limit, group_id)


def ask(
    system_prompt: str,
    user_question: str,
    provider_name: str,
    selected_model: str,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    persist: bool = True,
) -> LLMCallLog:
    """
    Single-provider ask: mint ids, build the request, call the provider, and log it.

    Archives the log by default; pass persist=False to skip all I/O (e.g. tests).
    A storage fault does not raise - persist_log reports it on the console and the
    log is returned regardless, so the response survives a failed archive.
    """
    run_id = str(uuid4())
    created_at = datetime.now(UTC)
    request = make_request(
        system_prompt, user_question, selected_model, max_tokens=max_tokens
    )
    log = run_request(run_id, request, provider_name, created_at)

    if persist:
        persist_log(log)

    return log


QUORUM = 2
"""
Usable answers a batch needs before it is a comparison at all.

One answer has nothing to be compared against, so a lone success is not a weak
comparison - it is not one. Deliberately a fixed constant: varying the quorum by
question risk requires someone to judge that risk first, and who does the judging
is still an open design question, not something to default.
"""


@dataclass
class CompareResult:
    """
    Aggregated outcome of one multi-provider comparison (shared group_id).

    Each call keeps its own run_id; `group_id` ties them together as one batch.
    `logs` holds every outcome for persistence; `successes`/`failures` split them
    by whether the *call* worked, with failures captured as ErrorInfo values.
    `persist_errors` keeps archiving faults apart from provider faults: a locked
    database says nothing about the quality of the answers, so it must not be
    counted as a failed call.

    State is reported on three independent axes, because one label cannot carry
    them: whether enough answers came back (`collection_status`), whether the
    spend behind them is fully accounted for (`audit_status`), and whether the
    record of it reached disk (`persistence_status`). A batch can easily be
    complete on one and not the others.
    """

    group_id: str
    logs: list[LLMCallLog] = field(default_factory=list)
    successes: list[LLMCallResult] = field(default_factory=list)
    failures: list[ErrorInfo] = field(default_factory=list)
    persist_errors: list[PersistenceErrorInfo] = field(default_factory=list)
    persist_attempted: bool = True
    """False when the caller passed persist=False, so 'nothing failed' is not read as 'stored'."""

    @property
    def usable_responses(self) -> list[LLMCallResult]:
        """
        The answers that can actually go into a cross-check, in target order.

        Not the same as `successes`, in both directions:

        * A response billed and then lost at cost calculation (PaidResponseError)
          is counted here. Its body and token usage are intact - only the price tag
          is missing - so leaving it out would silently drop an answer we paid for
          and shrink the quorum for a bookkeeping reason.
        * A response with nothing to read - parsing failed, or the model returned
          an empty body - is not counted, however the call itself was judged. An
          empty answer padding the quorum is exactly the false confidence this tool
          exists to prevent.
        * A response the model was cut off mid-way through (see is_truncated) is
          not counted either, for the same reason one step further on: it reads as
          a whole answer and is not one. Its conclusion may be missing or, worse,
          half-formed. This is a vote, not the answer itself - the result stays in
          `logs`, keeps its cost, is persisted, and is still printed; it just does
          not get to claim the batch was cross-checked.
        """
        return [
            log.result
            for log in self.logs
            if log.result is not None
            and log.result.response_text.strip()
            and not is_truncated(log.result)
        ]

    @property
    def collection_status(self) -> CollectionStatus:
        """complete = every target usable; partial = quorum met; insufficient = below quorum."""
        usable = len(self.usable_responses)
        if usable < QUORUM:
            return "insufficient"
        return "complete" if usable == len(self.logs) else "partial"

    @property
    def audit_status(self) -> AuditStatus:
        """
        Whether everything billed in this batch is fully accounted for.

        Degraded when money was spent without a complete record of it: a usable
        answer whose cost could not be computed, or a billed response that never
        parsed and left only salvage diagnostics. Unknown when no such gap is
        recorded but some call failed in a way that cannot rule out billing
        (log.billing_status == "unknown") - `clean` would then claim a settled
        ledger nobody can actually settle. Known-incomplete outranks
        undeterminable, so degraded wins when both apply.
        """
        if any(result.cost is None for result in self.usable_responses):
            return "degraded"
        if any(failure.salvage is not None for failure in self.failures):
            return "degraded"
        if any(log.billing_status == "unknown" for log in self.logs):
            return "unknown"
        return "clean"

    @property
    def persistence_status(self) -> PersistenceStatus | None:
        """
        Whether this batch's audit trail reached storage.

        None when persistence was never attempted (persist=False) - reporting
        "complete" for an archive nobody wrote would be the kind of quiet false
        claim this three-axis split exists to remove.
        """
        if not self.persist_attempted or not self.logs:
            return None
        if not self.persist_errors:
            return "complete"

        # An error carrying no written_sinks means that run landed nowhere at all.
        stored_nowhere = {e.run_id for e in self.persist_errors if not e.written_sinks}
        return "failed" if len(stored_nowhere) == len(self.logs) else "partial"


def compare(
    system_prompt: str,
    user_question: str,
    targets: list[tuple[str, str]],
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    persist: bool = True,
) -> CompareResult:
    """
    Ask several (provider, model) targets the same question under one group_id.

    Each call gets its own run_id (so every attempt is an independent audit row);
    a shared group_id ties them together as one comparison batch.

    A failing provider does not stop the others: each failure is collected as an
    ErrorInfo value (with any salvaged partial result attached) so a partial /
    quorum result can still be formed. This is the only place failures become data.
    Archiving faults are collected the same way, into `persist_errors`, so a full
    disk cannot destroy answers that were already paid for.

    The targets' API calls run in parallel (they are pure I/O waits), but only the
    calls: persistence stays on this thread - see the loop comment below.

    Args:
      targets: list of (provider_name, selected_model) pairs. Must be distinct.

    Raises:
      ValueError: The same provider:model appears twice. This is checked before any
        paid call, so it costs nothing.
    """
    group_id = str(uuid4())
    created_at = datetime.now(UTC)
    outcome = CompareResult(group_id=group_id, persist_attempted=persist)

    if not targets:
        return outcome

    # Asking one model the same question twice is not cross-validation: it buys a
    # second billed answer that inflates the quorum with a correlated opinion. Reject
    # it here, while it is still free. Compared on canonical price-table names, not
    # the raw strings: the tables carry aliases (gpt-4o-mini-2024-07-18 →
    # gpt-4o-mini), so two spellings of one model are still one model.
    by_canonical: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for t in targets:
        by_canonical.setdefault(_canonical_target(*t), []).append(t)

    duplicated = {c: ts for c, ts in by_canonical.items() if len(ts) > 1}
    if duplicated:
        listed = "; ".join(
            " + ".join(f"{provider}:{model}" for provider, model in ts)
            + (
                f" (all price as {c_provider}:{c_model})"
                if any(
                    (provider, model) != (c_provider, c_model) for provider, model in ts
                )
                else ""
            )
            for (c_provider, c_model), ts in duplicated.items()
        )
        message = (
            f"Duplicate compare targets are rejected: {listed}. "
            "Each model may appear only once, under any of its price-table "
            "aliases - a repeated model would be billed twice and counted twice "
            "toward the quorum."
        )
        print_error(message, module="service_ask.py", func="compare")
        raise ValueError(message)

    # Ids and requests are minted here, on the calling thread, exactly as before,
    # so a malformed target still fails right here instead of inside a worker.
    jobs = [
        (
            provider_name,
            selected_model,
            str(uuid4()),
            make_request(
                system_prompt, user_question, selected_model, max_tokens=max_tokens
            ),
        )
        for provider_name, selected_model in targets
    ]

    # Only the blocking API calls run in parallel; run_request() turns every
    # outcome into an LLMCallLog and never raises (see _assemble_log), so a worker
    # cannot break the pool. Collection guards each future anyway - see below.
    #
    # The pool is capped (call_policy.MAX_PARALLEL_CALLS): --target is repeatable
    # with no limit, and one worker per target turns a typo into a burst of
    # concurrent requests. Sharing one provider instance across these threads is
    # safe - see the ChatProvider contract.
    with ThreadPoolExecutor(max_workers=min(len(jobs), MAX_PARALLEL_CALLS)) as pool:
        futures = [
            pool.submit(
                run_request, run_id, request, provider_name, created_at, group_id
            )
            for provider_name, _, run_id, request in jobs
        ]

        # Iterate in SUBMISSION order, not completion order. Two things depend on
        # this: every write happens on this one thread (no concurrent SQLite or
        # JSONL writers - same-provider targets share one JSONL file), and the
        # stored row order plus successes/failures stay in target order however
        # the latencies fall. Persisting inside the pool still overlaps that local
        # I/O with the calls still in flight.
        for (provider_name, selected_model, run_id, request), future in zip(
            jobs, futures, strict=True
        ):
            try:
                log = future.result()

            except Exception as e:  # noqa: BLE001 - one dead worker must not abandon the rest.
                # run_request() is built never to raise, so reaching this means an
                # unforeseen failure inside the worker. Re-raising it here would
                # stop the loop and throw away every target still unread - including
                # calls already billed. Degrade this one target to a failed log and
                # keep collecting instead.
                print_error(
                    f"Worker for '{provider_name}' raised unexpectedly - {e}",
                    module="service_ask.py",
                    func="compare",
                )
                log = _assemble_log(
                    {
                        "run_id": run_id,
                        "group_id": group_id,
                        "created_at": created_at,
                        "provider": provider_name,
                        "model": selected_model,
                        "system_prompt": request.system_prompt,
                        "user_prompt": request.user_question,
                        "success": False,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "elapsed_sec": None,  # the worker died before reporting one
                        "result": None,
                        "salvage": None,
                        "policy": _current_policy(),
                        # The worker died outside run_request's accounting, so
                        # whether its call was ever made - let alone billed - is
                        # exactly the case "unknown" exists for.
                        "billing_status": "unknown",
                    }
                )

            # Collect first, archive second. Persistence is a side effect of calls
            # that were already billed, so this target's result is in hand before
            # any disk is touched, and a storage fault is recorded as data rather
            # than ending the loop and abandoning the targets still unread.
            outcome.logs.append(log)

            if log.success and log.result is not None:
                outcome.successes.append(log.result)
            else:
                outcome.failures.append(
                    ErrorInfo(
                        provider=provider_name,
                        model=selected_model,
                        error_type=log.error_type or "UnknownError",
                        message=log.error or "",
                        elapsed_sec=log.elapsed_sec,
                        partial_result=log.result,  # salvaged PaidResponseError result, if any
                        salvage=log.salvage,  # diagnostics when even parsing failed
                        created_at=created_at,
                    )
                )

            if persist:
                outcome.persist_errors.extend(persist_log(log))

    return outcome
