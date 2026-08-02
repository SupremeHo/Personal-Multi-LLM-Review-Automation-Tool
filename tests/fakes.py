# Fake API clients/responses and providers for tests (no paid calls).

from __future__ import annotations

import json
import threading
import time
import types
from pathlib import Path

from resources.providers.response_error import PaidResponseError
from resources.schemas import LLMCallResult, LLMRequest, SalvageInfo, TokenUsageInfo


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


# --- OpenAI-shaped fakes ----------------------------------------------------
def make_openai_response(model: str = "gpt-4o-mini", cached: int = 20):
    details = types.SimpleNamespace(cached_tokens=cached)
    usage = types.SimpleNamespace(
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        prompt_tokens_details=details,
    )
    msg = types.SimpleNamespace(content="hi from openai")
    choice = types.SimpleNamespace(message=msg, finish_reason="stop")
    return types.SimpleNamespace(
        choices=[choice], usage=usage, model=model, id="raw-openai"
    )


def fake_openai_client(response=None):
    response = response or make_openai_response()
    completions = types.SimpleNamespace(create=lambda **kwargs: response)
    chat = types.SimpleNamespace(completions=completions)
    return types.SimpleNamespace(chat=chat)


# --- Anthropic-shaped fakes -------------------------------------------------
def make_anthropic_response(
    model: str = "claude-test", cache_creation: int = 30, cache_read: int = 10
):
    usage = types.SimpleNamespace(
        input_tokens=200,
        output_tokens=80,
        cache_creation_input_tokens=cache_creation,
        cache_read_input_tokens=cache_read,
    )
    block = types.SimpleNamespace(text="bonjour from claude")
    return types.SimpleNamespace(
        content=[block],
        usage=usage,
        model=model,
        id="raw-anthropic",
        stop_reason="end_turn",
    )


def fake_anthropic_client(response=None):
    response = response or make_anthropic_response()
    messages = types.SimpleNamespace(create=lambda **kwargs: response)
    return types.SimpleNamespace(messages=messages)


# --- Google (Gemini)-shaped fakes -------------------------------------------
def make_google_response(model: str = "gemini-test", cached: int = 15):
    usage = types.SimpleNamespace(
        prompt_token_count=120,
        candidates_token_count=60,
        total_token_count=180,
        cached_content_token_count=cached,
    )
    candidate = types.SimpleNamespace(finish_reason=types.SimpleNamespace(value="STOP"))
    return types.SimpleNamespace(
        candidates=[candidate],
        usage_metadata=usage,
        model_version=model,
        response_id="raw-google",
        text="hi from gemini",
    )


def fake_google_client(response=None):
    response = response or make_google_response()
    models = types.SimpleNamespace(generate_content=lambda **kwargs: response)
    return types.SimpleNamespace(models=models)


# --- fake ChatProviders (for registry/service tests) ------------------------
def make_result(request: LLMRequest, provider: str = "fake", text: str = "ok"):
    return LLMCallResult(
        response_id=request.response_id,
        provider=provider,
        model=request.selected_model,
        response_text=text,
        usage=TokenUsageInfo(input_tokens=1, output_tokens=1, total_tokens=2),
    )


class GoodProvider:
    provider_name = "good"

    def ask(self, request: LLMRequest) -> LLMCallResult:
        return make_result(request, "good")


class FailProvider:
    provider_name = "fail"

    def ask(self, request: LLMRequest) -> LLMCallResult:
        raise RuntimeError("boom")


class PaidFailProvider:
    """Billed, then cost calculation broke: the response itself is still intact."""

    provider_name = "paidfail"

    def ask(self, request: LLMRequest) -> LLMCallResult:
        raise PaidResponseError(
            ValueError("cost broke"),
            result=make_result(request, "paidfail"),
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


class SlowProvider:
    """Answers after a delay, to check result order does not follow latency."""

    provider_name = "slow"

    def __init__(self, delay: float):
        self._delay = delay

    def ask(self, request: LLMRequest) -> LLMCallResult:
        time.sleep(self._delay)
        return make_result(request, self.provider_name)
