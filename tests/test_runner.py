# Shared run_chat pipeline tests.

from __future__ import annotations

import types

import pytest

from resources.providers.response_error import PaidResponseError
from resources.providers.runner import ParsedResponse, run_chat
from resources.schemas import LLMRequest, TokenUsageInfo
from tests.fakes import write_price_table


def _request(model="test-model"):
    return LLMRequest(
        response_id="rid",
        system_prompt="s",
        user_question="q",
        selected_model=model,
    )


def _parsed(model="test-model"):
    return ParsedResponse(
        model=model,
        response_text="txt",
        finish_reason="stop",
        raw_response_id="raw",
        usage=TokenUsageInfo(input_tokens=10, output_tokens=5, total_tokens=15),
        uncached_input_tokens=10,
    )


def _raise_parse_error(_raw):
    raise AttributeError("response shape changed")


def test_run_chat_success(tmp_path):
    price = write_price_table(tmp_path / "p.json", "test-model")
    calls = {}

    def call_api(request):
        calls["called"] = True
        return "RAW"

    def parse(raw):
        assert raw == "RAW"
        return _parsed()

    result = run_chat(
        request=_request(),
        provider_name="x",
        client=object(),
        price_path=price,
        call_api=call_api,
        parse_response=parse,
    )
    assert calls["called"] is True
    assert result.response_id == "rid"  # service-injected id is used
    assert result.response_text == "txt"
    # 10 input @1.0 + 5 output @2.0 per 1M tokens
    assert result.cost.total_usd == pytest.approx(10 / 1_000_000 + 5 * 2 / 1_000_000)


def test_run_chat_client_none_raises_before_billing(tmp_path):
    price = write_price_table(tmp_path / "p.json", "test-model")

    def call_api(request):
        raise AssertionError("paid call must not happen when client is None")

    with pytest.raises(RuntimeError):
        run_chat(
            request=_request(),
            provider_name="x",
            client=None,
            price_path=price,
            call_api=call_api,
            parse_response=lambda raw: _parsed(),
        )


def test_run_chat_cost_failure_preserves_billed_response(tmp_path):
    # Price table knows "test-model" (preflight passes) but the parsed response
    # reports an unknown model, so cost calc fails AFTER billing.
    price = write_price_table(tmp_path / "p.json", "test-model")

    with pytest.raises(PaidResponseError) as exc:
        run_chat(
            request=_request("test-model"),
            provider_name="x",
            client=object(),
            price_path=price,
            call_api=lambda request: "RAW",
            parse_response=lambda raw: _parsed(model="unknown-model"),
        )
    assert exc.value.result.response_text == "txt"
    assert exc.value.result.cost is None
    assert exc.value.salvage.failed_stage == "cost"


def test_run_chat_parse_failure_preserves_billed_response(tmp_path):
    # Regression: a post-billing parse failure used to escape as a plain exception,
    # so the run was logged as if the API had never been reached - losing the fact
    # that the call was already charged.
    price = write_price_table(tmp_path / "p.json", "test-model")
    raw = types.SimpleNamespace(
        id="raw-1",
        model="test-model-2024",
        usage=types.SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )

    def parse(_):
        raise AttributeError("response shape changed")

    with pytest.raises(PaidResponseError) as exc:
        run_chat(
            request=_request(),
            provider_name="x",
            client=object(),
            price_path=price,
            call_api=lambda request: raw,
            parse_response=parse,
        )

    # No result can exist (parsing is what failed), but the billed call is not lost.
    assert exc.value.result is None
    assert isinstance(exc.value.original, AttributeError)

    salvage = exc.value.salvage
    assert salvage.failed_stage == "parse"
    assert salvage.provider == "x"
    assert salvage.requested_model == "test-model"
    assert salvage.raw_response_id == "raw-1"  # still traceable on the provider side
    assert salvage.raw_model == "test-model-2024"
    assert salvage.raw_usage == {"prompt_tokens": 10, "completion_tokens": 5}


def test_run_chat_salvage_drops_non_scalar_usage_fields(tmp_path):
    # The audit log must always serialize, so nested usage objects are dropped
    # rather than walked - the unexpected shape is the thing that just failed.
    price = write_price_table(tmp_path / "p.json", "test-model")
    raw = types.SimpleNamespace(
        id="raw-1",
        usage=types.SimpleNamespace(
            prompt_tokens=10,
            prompt_tokens_details=types.SimpleNamespace(cached_tokens=4),
        ),
    )

    with pytest.raises(PaidResponseError) as exc:
        run_chat(
            request=_request(),
            provider_name="x",
            client=object(),
            price_path=price,
            call_api=lambda request: raw,
            parse_response=_raise_parse_error,
        )

    assert exc.value.salvage.raw_usage == {"prompt_tokens": 10}


def test_run_chat_salvage_never_masks_the_billed_failure(tmp_path):
    # Reading a broken response can itself blow up. When it does, the salvage
    # degrades to what we always know instead of replacing the real failure.
    price = write_price_table(tmp_path / "p.json", "test-model")

    class Hostile:
        def __getattr__(self, name):
            raise RuntimeError("attribute access exploded")

    with pytest.raises(PaidResponseError) as exc:
        run_chat(
            request=_request(),
            provider_name="x",
            client=object(),
            price_path=price,
            call_api=lambda request: Hostile(),
            parse_response=_raise_parse_error,
        )

    assert isinstance(exc.value.original, AttributeError)
    assert exc.value.salvage.failed_stage == "parse"
    assert exc.value.salvage.provider == "x"
    assert exc.value.salvage.raw_usage is None


def test_run_chat_result_validation_failure_preserves_billed_response(tmp_path):
    # ParsedResponse is a plain dataclass, so a provider that reads a None body
    # (OpenAI does this for refusals/tool calls) only fails at LLMCallResult -
    # after billing. That must not be logged as an unbilled failure either.
    price = write_price_table(tmp_path / "p.json", "test-model")
    parsed = _parsed()
    parsed.response_text = None

    with pytest.raises(PaidResponseError) as exc:
        run_chat(
            request=_request(),
            provider_name="x",
            client=object(),
            price_path=price,
            call_api=lambda request: "RAW",
            parse_response=lambda raw: parsed,
        )

    assert exc.value.result is None

    salvage = exc.value.salvage
    assert salvage.failed_stage == "result_validation"
    # Parsing succeeded here, so the salvage comes from the normalized response.
    assert salvage.raw_response_id == "raw"
    assert salvage.raw_model == "test-model"
    assert salvage.raw_usage["input_tokens"] == 10
