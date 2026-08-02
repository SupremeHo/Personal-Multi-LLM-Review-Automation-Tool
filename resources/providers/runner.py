# Shared, provider-neutral pipeline for a single chat call.
#
# Every provider's ask() runs the SAME steps: client guard -> preflight pricing
# -> paid call -> parse response -> best-effort cost -> assemble LLMCallResult
# -> PaidResponseError on a post-billing failure. Only the two provider-specific
# parts (the paid API call and the response parsing) are injected as callbacks,
# so this flow is written once instead of being copied per provider.
#
# EVERY step after the paid call sits inside a post-billing boundary: whatever
# breaks there is re-raised as PaidResponseError carrying either the assembled
# result or SalvageInfo, so a billed response is never logged as if it had never
# reached the API.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from resources.count_cost import calculate_token_cost, preflight_pricing
from resources.diagnostics import print_error
from resources.providers.response_error import PaidResponseError
from resources.schemas import (
    CostInfo,
    LLMCallResult,
    LLMRequest,
    SalvageInfo,
    TokenUsageInfo,
)


@dataclass
class ParsedResponse:
    """
    Provider-specific fields extracted from a raw API response, normalized into
    the shape run_chat needs to build an LLMCallResult and compute cost.
    """

    model: str
    response_text: str
    finish_reason: str | None
    raw_response_id: str | None
    usage: TokenUsageInfo

    uncached_input_tokens: int
    """Full-price prompt tokens (cache tokens excluded), for the cost calculator."""

    cache_read_tokens: int = 0
    """Tokens served from cache (discounted). Providers normalize their own count here."""

    cache_write_tokens: int = 0
    """Tokens written to cache (Anthropic-only premium); zero for other providers."""


def _scalar_fields(obj: Any) -> dict[str, Any]:
    """
    Read an object's scalar attributes into a JSON-safe dict.

    Nested objects (e.g. OpenAI's prompt_tokens_details) are dropped rather than
    walked: this feeds an audit log that must always serialize, and the failure
    being diagnosed is precisely that the response shape was not what we expected.
    """
    dump = getattr(obj, "model_dump", None)
    fields = dump() if callable(dump) else vars(obj)
    return {
        key: value
        for key, value in fields.items()
        if value is None or isinstance(value, (bool, int, float, str))
    }


def _raw_details(raw_response: Any) -> dict[str, Any]:
    """
    Best-effort, provider-neutral read of a billed response we could not parse.

    Only names shared across the OpenAI-compatible response shapes are tried, so
    this stays out of the per-provider parsers' territory. The response body is
    intentionally left out - its path is provider-specific and it can carry
    sensitive prompt content.
    """
    details: dict[str, Any] = {"raw_type": type(raw_response).__name__}

    for attr in ("id", "response_id"):
        value = getattr(raw_response, attr, None)
        if isinstance(value, str):
            details["raw_response_id"] = value
            break

    for attr in ("model", "model_version"):
        value = getattr(raw_response, attr, None)
        if isinstance(value, str):
            details["raw_model"] = value
            break

    for attr in ("usage", "usage_metadata"):
        usage = getattr(raw_response, attr, None)
        if usage is not None:
            details["raw_usage"] = _scalar_fields(usage)
            break

    return details


def _parsed_details(parsed: ParsedResponse) -> dict[str, Any]:
    """Salvage fields taken from an already-parsed response (parsing itself succeeded)."""
    return {
        "raw_response_id": parsed.raw_response_id,
        "raw_model": parsed.model,
        "raw_usage": parsed.usage.model_dump(),
    }


def _salvage(
    *,
    stage: str,
    provider_name: str,
    requested_model: str,
    raw_response: Any,
    parsed: ParsedResponse | None = None,
) -> SalvageInfo:
    """
    Describe a billed response that failed after the paid call.

    Reading a broken response can itself blow up, so the optional details are
    best-effort: on any problem this falls back to the three facts we always
    know (where it broke, which provider, which model was asked for). Salvage
    must never mask the real post-billing failure.
    """
    known = {
        "failed_stage": stage,
        "provider": provider_name,
        "requested_model": requested_model,
    }
    try:
        details = (
            _parsed_details(parsed)
            if parsed is not None
            else _raw_details(raw_response)
        )
        return SalvageInfo(**known, **details)
    except Exception:  # noqa: BLE001 - diagnostics are optional; the billed failure is not.
        return SalvageInfo(**known)


def run_chat(
    *,
    request: LLMRequest,
    provider_name: str,
    client: Any | None,
    price_path: str | Path,
    call_api: Callable[[LLMRequest], Any],
    parse_response: Callable[[Any], ParsedResponse],
) -> LLMCallResult:
    """
    Execute the common chat pipeline and return an LLMCallResult.

    Args:
      request: The provider-agnostic request (already carries response_id).
      provider_name: Canonical registry key, stored on the result and used in messages.
      client: The provider SDK client, or None when its key/init failed.
      price_path: Path to this provider's price table JSON.
      call_api: Performs the paid API call. THIS is where money is spent.
      parse_response: Turns the raw API response into a ParsedResponse.

    Raises:
      RuntimeError: The client is unavailable (pre-billing).
      PaidResponseError: A response was billed but a later step failed - parsing,
        cost calculation, or result validation. It carries the assembled result
        when there is one and SalvageInfo either way, so the paid response is
        never discarded.
      Exception: Any other pre-billing failure (e.g. preflight pricing).
    """
    if client is None:
        raise RuntimeError(
            print_error(
                f"'{provider_name}' client is unavailable. Check the API key and the environment setup",
                module="runner.py",
                func="run_chat",
            )
        )

    # Preflight: validate the price table and model name BEFORE the paid call so a
    # missing price file or a mistyped model fails for free instead of after billing.
    price_table = preflight_pricing(price_path, request.selected_model)

    # >>>>> Paid call. Money is spent here. <<<<<
    raw_response = call_api(request)

    # >>>>> Everything below runs AFTER billing; a failure here must not throw away the paid response. <<<<<
    # Each step is a separate stage of one post-billing boundary. Parsing and result
    # validation leave nothing to return, so they raise with SalvageInfo instead;
    # cost is the one step whose failure still leaves a usable result.
    try:
        parsed = parse_response(raw_response)
    except Exception as e:  # noqa: BLE001 - a billed response must not vanish because its shape changed.
        print_error(
            f"Response parsing failed after billing ({provider_name}) - {e}",
            module="runner.py",
            func="run_chat",
        )
        raise PaidResponseError(
            e,
            salvage=_salvage(
                stage="parse",
                provider_name=provider_name,
                requested_model=request.selected_model,
                raw_response=raw_response,
            ),
        ) from e

    # Best-effort cost calculation. If it fails (e.g. a broken price entry), keep the error
    # aside so we can still build the result and preserve the response/tokens we already paid for.
    cost_info: CostInfo | None = None
    cost_error: Exception | None = None
    try:
        cost = calculate_token_cost(
            price_table=price_table,
            model_name=parsed.model,
            uncached_input_tokens=parsed.uncached_input_tokens,
            output_tokens=parsed.usage.output_tokens,
            cache_read_tokens=parsed.cache_read_tokens,
            cache_write_tokens=parsed.cache_write_tokens,
        )
        # The cost dict keys are kept 1:1 with CostInfo fields, so this maps directly.
        cost_info = CostInfo(**cost)
    except Exception as e:  # noqa: BLE001 - any cost failure must not discard the paid response.
        cost_error = e
        print_error(
            f"Cost calculation failed after billing ({provider_name}) - {e}",
            module="runner.py",
            func="run_chat",
        )

    try:
        result = LLMCallResult(
            response_id=request.response_id,
            provider=provider_name,
            model=parsed.model,
            response_text=parsed.response_text,
            finish_reason=parsed.finish_reason,
            raw_response_id=parsed.raw_response_id,
            usage=parsed.usage,
            cost=cost_info,
        )
    except Exception as e:  # noqa: BLE001 - a parsed-but-invalid response is still a billed one.
        # ParsedResponse is a plain dataclass, so a field the provider read as the
        # wrong type (e.g. a None response_text) only fails validation here.
        print_error(
            f"Result validation failed after billing ({provider_name}) - {e}",
            module="runner.py",
            func="run_chat",
        )
        raise PaidResponseError(
            e,
            salvage=_salvage(
                stage="result_validation",
                provider_name=provider_name,
                requested_model=request.selected_model,
                raw_response=raw_response,
                parsed=parsed,
            ),
        ) from e

    # If cost calc failed, the run is a failure - but hand the preserved result to the caller for the audit log.
    if cost_error is not None:
        raise PaidResponseError(
            cost_error,
            result=result,
            salvage=_salvage(
                stage="cost",
                provider_name=provider_name,
                requested_model=request.selected_model,
                raw_response=raw_response,
                parsed=parsed,
            ),
        )

    return result
