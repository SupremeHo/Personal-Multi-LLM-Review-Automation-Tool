# Shared, provider-neutral pipeline for a single chat call.
#
# Every provider's ask() runs the SAME steps: client guard -> preflight pricing
# -> paid call -> parse response -> best-effort cost -> assemble LLMCallResult
# -> PaidResponseError on a post-billing failure. Only the two provider-specific
# parts (the paid API call and the response parsing) are injected as callbacks,
# so this flow is written once instead of being copied per provider.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from resources.count_cost import calculate_token_cost, preflight_pricing
from resources.providers.response_error import PaidResponseError
from resources.schemas import CostInfo, LLMCallResult, LLMRequest, TokenUsageInfo


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
    cached_input_tokens_for_cost: int = 0
    """
    The cached-input token count to feed the (single-rate) cost calculator.
    Providers map their own cache accounting onto this: OpenAI uses its cached
    prompt tokens; Anthropic uses cache-read tokens (the discounted ones).
    """


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
      PaidResponseError: A response was billed but cost calculation failed; the
        salvaged result is attached so the paid response is never discarded.
      Exception: Any other pre-billing failure (e.g. preflight pricing).
    """
    if client is None:
        raise RuntimeError(
            f"[runner.py] Error Message: '{provider_name}' client is unavailable. "
            f"Check the API key and the environment setup.\n"
        )

    # Preflight: validate the price table and model name BEFORE the paid call so a
    # missing price file or a mistyped model fails for free instead of after billing.
    price_table = preflight_pricing(price_path, request.selected_model)

    # >>>>> Paid call. Money is spent here. <<<<<
    raw_response = call_api(request)

    # >>>>> Everything below runs AFTER billing; a failure here must not throw away the paid response. <<<<<
    parsed = parse_response(raw_response)

    # Best-effort cost calculation. If it fails (e.g. a broken price entry), keep the error
    # aside so we can still build the result and preserve the response/tokens we already paid for.
    cost_info: CostInfo | None = None
    cost_error: Exception | None = None
    try:
        cost = calculate_token_cost(
            price_table=price_table,
            model_name=parsed.model,
            input_tokens=parsed.usage.input_tokens,
            output_tokens=parsed.usage.output_tokens,
            cached_input_tokens=parsed.cached_input_tokens_for_cost,
        )
        # The cost dict keys are kept 1:1 with CostInfo fields, so this maps directly.
        cost_info = CostInfo(**cost)
    except Exception as e:  # noqa: BLE001 - any cost failure must not discard the paid response.
        cost_error = e
        print(
            f"[runner.py] Error Message: Cost calculation failed after billing "
            f"({provider_name}) - {e}\n"
        )

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

    # If cost calc failed, the run is a failure - but hand the preserved result to the caller for the audit log.
    if cost_error is not None:
        raise PaidResponseError(result, cost_error)

    return result
