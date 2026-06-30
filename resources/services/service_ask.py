# Service layer: turns a high-level request into provider calls and audit logs.
#
# Responsibilities:
#   * Own identity generation (run_id, response_id) in one place, then inject it
#     into the provider request (the provider never mints ids).
#   * Resolve providers through the registry only (never import a concrete one).
#   * Turn each call's outcome into data: an LLMCallLog always, plus an ErrorInfo
#     for failures in the multi-compare flow so one failure never stops the rest.
#   * Archive each log to JSONL + SQLite via persist_log().

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from resources.providers.registry import get_provider
from resources.providers.response_error import PaidResponseError
from resources.schemas import ErrorInfo, LLMCallLog, LLMCallResult, LLMRequest
from resources.storage_json import append_jsonl
from resources.storage_sqlite import import_jsonl_to_sqlite

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "db" / "llm_responses.db"

# Per-provider on-disk log layout: provider key -> (subdirectory, filename prefix).
LOG_LAYOUT = {
    "openai": ("OpenAI", "gpt"),
    "anthropic": ("Anthropic", "claude"),
    "google": ("Google", "gemini"),
}


def make_request(
    system_prompt: str,
    user_question: str,
    selected_model: str,
    *,
    max_tokens: int = 4096,
) -> LLMRequest:
    """Build an LLMRequest with a freshly minted response_id (service owns identity)."""
    return LLMRequest(
        response_id=str(uuid4()),
        system_prompt=system_prompt,
        user_question=user_question,
        selected_model=selected_model,
        max_tokens=max_tokens,
    )


def run_request(
    run_id: str,
    request: LLMRequest,
    provider_name: str,
    created_at: datetime | None = None,
) -> LLMCallLog:
    """
    Execute one provider call and assemble its audit log.

    The log is built once up front and filled in place, so it is always returned
    - on success, on a salvaged partial failure (PaidResponseError), or on any
    other failure - with elapsed_sec recorded either way.
    """
    created_at = created_at or datetime.now()

    log_data = {
        "run_id": run_id,
        "created_at": created_at,
        "provider": provider_name,
        "system_prompt": request.system_prompt,
        "user_prompt": request.user_question,
        "success": False,
        "error": None,
        "error_type": None,
        "elapsed_sec": None,
        "result": None,
    }

    start_time = time.perf_counter()
    try:
        provider = get_provider(provider_name)
        result = provider.ask(request)
        log_data["success"] = True
        log_data["result"] = result

    except PaidResponseError as e:
        # The paid call succeeded but a later step failed. Judge the run a failure,
        # yet preserve the response/tokens already paid for so no billed call goes unlogged.
        log_data["result"] = e.result
        log_data["error"] = str(e.original)
        log_data["error_type"] = type(e.original).__name__

    except Exception as e:  # noqa: BLE001 - any failure must still produce an audit log.
        log_data["error"] = str(e)
        log_data["error_type"] = type(e).__name__

    finally:
        log_data["elapsed_sec"] = round(time.perf_counter() - start_time, 3)

    return LLMCallLog(**log_data)


def persist_log(log: LLMCallLog) -> None:
    """
    Archive one audit log to a per-provider JSONL file and into SQLite.

    The log is always written - success or failure - so every run, including
    billed-but-failed ones, leaves an auditable record.
    """
    dir_name, prefix = LOG_LAYOUT.get(
        log.provider or "", (log.provider or "unknown", log.provider or "log")
    )
    filename = f"{prefix}_response_log_{log.created_at.strftime('%Y%m%d_%H%M%S')}.jsonl"
    path = BASE_DIR / "logs" / dir_name / filename

    append_jsonl(str(path), log)
    import_jsonl_to_sqlite(str(path), str(DB_PATH))


def ask(
    system_prompt: str,
    user_question: str,
    provider_name: str,
    selected_model: str,
    *,
    max_tokens: int = 4096,
    persist: bool = True,
) -> LLMCallLog:
    """
    Single-provider ask: mint ids, build the request, call the provider, log it.

    Archives the log by default; pass persist=False to skip all I/O (e.g. tests).
    """
    run_id = str(uuid4())
    created_at = datetime.now()
    request = make_request(
        system_prompt, user_question, selected_model, max_tokens=max_tokens
    )
    log = run_request(run_id, request, provider_name, created_at)
    if persist:
        persist_log(log)
    return log


@dataclass
class CompareResult:
    """
    Aggregated outcome of one multi-provider comparison (shared run_id).

    `logs` holds every outcome for persistence; `successes`/`failures` split them
    for quorum / cross-validation logic, with failures captured as ErrorInfo values.
    """

    run_id: str
    logs: list[LLMCallLog] = field(default_factory=list)
    successes: list[LLMCallResult] = field(default_factory=list)
    failures: list[ErrorInfo] = field(default_factory=list)


def compare(
    system_prompt: str,
    user_question: str,
    targets: list[tuple[str, str]],
    *,
    max_tokens: int = 4096,
    persist: bool = True,
) -> CompareResult:
    """
    Ask several (provider, model) targets the same question under one run_id.

    A failing provider does not stop the others: each failure is collected as an
    ErrorInfo value (with any salvaged partial result attached) so a partial /
    quorum result can still be formed. This is the only place failures become data.

    Args:
      targets: list of (provider_name, selected_model) pairs.
    """
    run_id = str(uuid4())
    created_at = datetime.now()
    outcome = CompareResult(run_id=run_id)

    for provider_name, selected_model in targets:
        request = make_request(
            system_prompt, user_question, selected_model, max_tokens=max_tokens
        )
        log = run_request(run_id, request, provider_name, created_at)
        if persist:
            persist_log(log)
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
                    created_at=created_at,
                )
            )

    return outcome
