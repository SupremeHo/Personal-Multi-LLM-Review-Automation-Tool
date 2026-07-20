# Shared run_chat pipeline tests.

from __future__ import annotations

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
