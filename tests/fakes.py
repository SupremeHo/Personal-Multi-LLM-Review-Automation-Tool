# Fake API clients/responses and providers for tests (no paid calls).

from __future__ import annotations

import json
import threading
import time
import types
from pathlib import Path

from resources.providers.response_error import PaidResponseError, ProviderCallError
from resources.schemas import (
    CostInfo,
    LLMCallResult,
    LLMRequest,
    SalvageInfo,
    TokenUsageInfo,
)


# --- price tables -----------------------------------------------------------
def write_price_table(
    path: Path,
    model: str,
    *,
    input_rate: float = 1.0,
    output_rate: float = 2.0,
    cached_rate: float = 0.5,
    extra_rates: dict | None = None,
) -> Path:
    """
    Write a minimal price table JSON for one model and return its path.

    Pass ``extra_rates`` to add provider-specific keys (e.g. Anthropic's
    ``cache_read`` / ``cache_write_5m``) to the model entry.
    """
    entry = {
        "input": input_rate,
        "cached_input": cached_rate,
        "output": output_rate,
    }
    if extra_rates:
        entry.update(extra_rates)

    data = {
        "updated_at": "2099-01-01",  # far future so the >30-day notice never fires
        "source": "test",
        "models": {model: entry},
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _recording(response, calls: list | None):
    """Return a fake API callable that records the kwargs it was given."""

    def call(**kwargs):
        if calls is not None:
            calls.append(kwargs)
        return response

    return call


# --- OpenAI-shaped fakes ----------------------------------------------------
def make_openai_response(
    model: str = "gpt-4o-mini", cached: int = 20, reasoning: int = 30
):
    """
    ``reasoning`` is part of ``completion_tokens``, not added to it - that is how
    OpenAI reports it, and the fake has to agree or the no-double-billing test
    passes for the wrong reason.
    """
    details = types.SimpleNamespace(cached_tokens=cached)
    completion_details = types.SimpleNamespace(reasoning_tokens=reasoning)
    usage = types.SimpleNamespace(
        prompt_tokens=100,
        completion_tokens=50,  # 30 of these are reasoning
        total_tokens=150,
        prompt_tokens_details=details,
        completion_tokens_details=completion_details,
    )
    msg = types.SimpleNamespace(content="hi from openai")
    choice = types.SimpleNamespace(message=msg, finish_reason="stop")
    return types.SimpleNamespace(
        choices=[choice], usage=usage, model=model, id="raw-openai"
    )


def fake_openai_client(response=None, calls: list | None = None):
    """Pass ``calls`` to capture the kwargs each request was sent with."""
    response = response or make_openai_response()
    completions = types.SimpleNamespace(create=_recording(response, calls))
    chat = types.SimpleNamespace(completions=completions)
    return types.SimpleNamespace(chat=chat)


# --- Anthropic-shaped fakes -------------------------------------------------
# Content blocks carry a `type` discriminator, as the real SDK's do. An earlier
# fake omitted it and only ever produced one text block, which is why parsing
# blindly by position (content[0].text) looked correct in the suite while
# blowing up on any real answer that came with a thinking block in front of it.
def anthropic_text_block(text: str = "bonjour from claude"):
    return types.SimpleNamespace(type="text", text=text)


def anthropic_thinking_block(thinking: str = "let me work through this"):
    """An extended-thinking block: reasoning on `.thinking`, and no `.text`."""
    return types.SimpleNamespace(type="thinking", thinking=thinking, signature="sig")


def make_anthropic_response(
    model: str = "claude-test",
    cache_creation: int = 30,
    cache_read: int = 10,
    content: list | None = None,
):
    """Pass ``content`` to supply the block list; defaults to a single text block."""
    usage = types.SimpleNamespace(
        input_tokens=200,
        output_tokens=80,
        cache_creation_input_tokens=cache_creation,
        cache_read_input_tokens=cache_read,
    )
    return types.SimpleNamespace(
        content=[anthropic_text_block()] if content is None else content,
        usage=usage,
        model=model,
        id="raw-anthropic",
        stop_reason="end_turn",
    )


def fake_anthropic_client(response=None, calls: list | None = None):
    """Pass ``calls`` to capture the kwargs each request was sent with."""
    response = response or make_anthropic_response()
    messages = types.SimpleNamespace(create=_recording(response, calls))
    return types.SimpleNamespace(messages=messages)


# --- Google (Gemini)-shaped fakes -------------------------------------------
# The default response carries thinking tokens because every priced Gemini model
# has thinking on, and because a fake without them hides a live billing bug the
# same way the old Anthropic fake hid the thinking-block one: candidates_token_count
# EXCLUDES thoughts (total = prompt + candidates + thoughts), so a parser that
# reads it alone bills the answer and nothing for the reasoning.
def make_google_response(
    model: str = "gemini-test",
    cached: int = 15,
    thoughts: int = 40,
    finish_reason: str | None = "STOP",
    text: str | None = "hi from gemini",
):
    usage = types.SimpleNamespace(
        prompt_token_count=120,
        candidates_token_count=60,  # the answer only
        thoughts_token_count=thoughts,  # billed at the output rate, counted separately
        total_token_count=120 + 60 + thoughts,
        cached_content_token_count=cached,
    )
    candidate = types.SimpleNamespace(
        finish_reason=(
            types.SimpleNamespace(value=finish_reason) if finish_reason else None
        )
    )
    return types.SimpleNamespace(
        candidates=[candidate],
        usage_metadata=usage,
        model_version=model,
        response_id="raw-google",
        text=text,
    )


def fake_google_client(response=None, calls: list | None = None):
    """Pass ``calls`` to capture the kwargs each request was sent with."""
    response = response or make_google_response()
    models = types.SimpleNamespace(generate_content=_recording(response, calls))
    return types.SimpleNamespace(models=models)


# --- fake ChatProviders (for registry/service tests) ------------------------
def make_result(
    request: LLMRequest,
    provider: str = "fake",
    text: str = "ok",
    *,
    costed: bool = True,
    finish_reason: str | None = None,
):
    """
    Build a result for a fake provider.

    Costed by default, so a batch of healthy fakes reports a clean audit status.
    Pass costed=False for the billed-but-uncosted case (PaidResponseError), and
    finish_reason to exercise the truncation path.
    """
    cost = (
        CostInfo(input_usd=0.0001, output_usd=0.0002, total_usd=0.0003, estimated=True)
        if costed
        else None
    )
    return LLMCallResult(
        response_id=request.response_id,
        provider=provider,
        model=request.selected_model,
        response_text=text,
        finish_reason=finish_reason,
        usage=TokenUsageInfo(input_tokens=1, output_tokens=1, total_tokens=2),
        cost=cost,
    )


class GoodProvider:
    provider_name = "good"

    def ask(self, request: LLMRequest) -> LLMCallResult:
        return make_result(request, "good")


class FailProvider:
    provider_name = "fail"

    def ask(self, request: LLMRequest) -> LLMCallResult:
        raise RuntimeError("boom")


class EmptyAnswerProvider:
    """A call that succeeds and bills, but returns nothing to compare."""

    provider_name = "empty"

    def ask(self, request: LLMRequest) -> LLMCallResult:
        return make_result(request, "empty", text="   ")


class TruncatedProvider:
    """
    A call that succeeded and bills, but ran out of tokens mid-answer.

    The body is non-empty and looks like a whole answer, which is exactly why it
    must not vote: reasoning shares the max_tokens ceiling, so this is the common
    shape of a wasted comparison, not a rare one.
    """

    provider_name = "truncated"

    def ask(self, request: LLMRequest) -> LLMCallResult:
        return make_result(
            request,
            "truncated",
            text="The three candidate causes are: first, the",
            finish_reason="MAX_TOKENS",  # Gemini's spelling; matching is case-insensitive
        )


class PaidFailProvider:
    """Billed, then cost calculation broke: the response itself is still intact."""

    provider_name = "paidfail"

    def ask(self, request: LLMRequest) -> LLMCallResult:
        raise PaidResponseError(
            ValueError("cost broke"),
            result=make_result(request, "paidfail", costed=False),
            salvage=SalvageInfo(
                failed_stage="cost",
                provider="paidfail",
                requested_model=request.selected_model,
            ),
        )


class ParseFailProvider:
    """Billed, then parsing broke: nothing but the salvage diagnostics survives."""

    provider_name = "parsefail"

    def ask(self, request: LLMRequest) -> LLMCallResult:
        raise PaidResponseError(
            AttributeError("response shape changed"),
            salvage=SalvageInfo(
                failed_stage="parse",
                provider="parsefail",
                requested_model=request.selected_model,
                raw_response_id="raw-parsefail",
                raw_usage={"input_tokens": 7},
            ),
        )


class AmbiguousBillingProvider:
    """
    The paid call died mid-flight (e.g. a read timeout while the provider was
    generating), so whether it was billed is unknowable - the boundary says so.
    """

    provider_name = "ambiguous"

    def ask(self, request: LLMRequest) -> LLMCallResult:
        raise ProviderCallError(
            TimeoutError("read timed out mid-response"), billing_possible=True
        )


class RejectedCallProvider:
    """The provider rejected the request before generating (HTTP 4xx): not billed."""

    provider_name = "rejected"

    def ask(self, request: LLMRequest) -> LLMCallResult:
        raise ProviderCallError(ValueError("400 bad request"), billing_possible=False)


class BadResultProvider:
    """
    Returns something that is not an LLMCallResult, breaking log assembly.

    The ChatProvider contract is structural, so nothing stops a provider from
    returning the wrong type; the failure only surfaces when the audit log is
    built - after the call was already paid for.
    """

    provider_name = "badresult"

    def ask(self, request: LLMRequest):
        return "not a result object"


class BadSalvageProvider:
    """Billed response preserved, but the salvage attached to it is malformed."""

    provider_name = "badsalvage"

    def ask(self, request: LLMRequest) -> LLMCallResult:
        raise PaidResponseError(
            ValueError("cost broke"),
            result=make_result(request, "badsalvage", costed=False),
            salvage="not a salvage object",
        )


class BarrierProvider:
    """
    Answers only once `barrier.parties` calls are in flight at the same time.

    Give the barrier a timeout: if compare() ran its targets sequentially the
    first call would wait alone until that timeout and raise BrokenBarrierError,
    so concurrency is asserted deterministically instead of by measuring sleeps.
    """

    provider_name = "barrier"

    def __init__(self, barrier: threading.Barrier):
        self._barrier = barrier

    def ask(self, request: LLMRequest) -> LLMCallResult:
        self._barrier.wait()
        return make_result(request, self.provider_name)


class ConcurrencyProbeProvider:
    """Records how many calls were ever in flight at the same time."""

    provider_name = "probe"

    def __init__(self, delay: float = 0.05):
        self._delay = delay
        self._lock = threading.Lock()
        self._in_flight = 0
        self.peak = 0

    def ask(self, request: LLMRequest) -> LLMCallResult:
        with self._lock:
            self._in_flight += 1
            self.peak = max(self.peak, self._in_flight)
        try:
            time.sleep(self._delay)  # hold the slot so overlap is observable
        finally:
            with self._lock:
                self._in_flight -= 1
        return make_result(request, self.provider_name)


class SlowProvider:
    """Answers after a delay, to check result order does not follow latency."""

    provider_name = "slow"

    def __init__(self, delay: float):
        self._delay = delay

    def ask(self, request: LLMRequest) -> LLMCallResult:
        time.sleep(self._delay)
        return make_result(request, self.provider_name)
