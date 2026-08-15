"""Per-provider parsing/mapping tests (no paid calls; price tables are temp files)."""

from __future__ import annotations

import pytest

from resources.providers import provider_anthropic
from resources.providers.base_provider import ChatProvider
from resources.providers.provider_anthropic import AnthropicProvider
from resources.providers.provider_google import GoogleProvider
from resources.providers.provider_openai import OpenAIProvider
from resources.schemas import LLMRequest
from tests.fakes import (
    anthropic_text_block,
    anthropic_thinking_block,
    fake_anthropic_client,
    fake_google_client,
    fake_openai_client,
    make_anthropic_response,
    make_google_response,
    make_openai_response,
    write_price_table,
)


def _request(model, **kwargs):
    return LLMRequest(
        response_id="rid",
        system_prompt="s",
        user_question="q",
        selected_model=model,
        **kwargs,
    )


def test_every_provider_applies_the_requested_output_ceiling(tmp_path):
    # Regression: OpenAI dropped LLMRequest.max_tokens on the floor, so the ceiling
    # meant to cap output cost applied to two providers out of three. Each SDK
    # spells it differently, which is exactly how that went unnoticed.
    price = write_price_table(tmp_path / "p.json", "m")
    request = _request("m", max_tokens=123)
    openai_calls, anthropic_calls, google_calls = [], [], []

    OpenAIProvider(
        client=fake_openai_client(make_openai_response(model="m"), calls=openai_calls),
        price_path=price,
    ).ask(request)
    AnthropicProvider(
        client=fake_anthropic_client(
            make_anthropic_response(model="m"), calls=anthropic_calls
        ),
        price_path=price,
    ).ask(request)
    GoogleProvider(
        client=fake_google_client(make_google_response(model="m"), calls=google_calls),
        price_path=price,
    ).ask(request)

    assert openai_calls[0]["max_completion_tokens"] == 123  # not the deprecated name
    assert anthropic_calls[0]["max_tokens"] == 123
    assert google_calls[0]["config"].max_output_tokens == 123


def test_anthropic_omits_the_thinking_parameter_by_default(tmp_path):
    # The parameter's accepted shapes differ per model generation, so there is no
    # value that works for every model in prices_claude.json: `adaptive` is refused
    # by opus-4-5/sonnet-4-5/haiku-4-5, `enabled`+budget_tokens by the 5-series and
    # opus-4-7/4-8, `disabled` by fable-5. Sending one unconditionally would turn a
    # silent default into a 400 on part of the table, so the default sends nothing.
    price = write_price_table(tmp_path / "a.json", "m")
    calls = []
    AnthropicProvider(
        client=fake_anthropic_client(make_anthropic_response(model="m"), calls=calls),
        price_path=price,
    ).ask(_request("m"))

    assert "thinking" not in calls[0]


def test_anthropic_sends_the_configured_thinking_policy(tmp_path, monkeypatch):
    # ...and when the policy IS set, it reaches the paid call verbatim - the point
    # of naming it is that flipping the constant actually changes the request.
    monkeypatch.setattr(provider_anthropic, "THINKING", {"type": "adaptive"})
    price = write_price_table(tmp_path / "a.json", "m")
    calls = []
    AnthropicProvider(
        client=fake_anthropic_client(make_anthropic_response(model="m"), calls=calls),
        price_path=price,
    ).ask(_request("m"))

    assert calls[0]["thinking"] == {"type": "adaptive"}


def test_providers_satisfy_contract():
    assert isinstance(OpenAIProvider(client=object()), ChatProvider)
    assert isinstance(AnthropicProvider(client=object()), ChatProvider)
    assert isinstance(GoogleProvider(client=object()), ChatProvider)


def test_openai_provider_maps_response(tmp_path):
    price = write_price_table(tmp_path / "o.json", "m")
    provider = OpenAIProvider(
        client=fake_openai_client(make_openai_response(model="m")), price_path=price
    )
    result = provider.ask(_request("m"))

    assert result.provider == "openai"
    assert result.response_id == "rid"
    assert result.response_text == "hi from openai"
    assert result.finish_reason == "stop"
    assert result.usage.input_tokens == 100
    assert result.usage.output_tokens == 50
    assert result.usage.total_tokens == 150
    assert result.usage.cached_input_tokens == 20
    assert result.cost is not None


def test_anthropic_provider_maps_response(tmp_path):
    price = write_price_table(tmp_path / "a.json", "m")
    provider = AnthropicProvider(
        client=fake_anthropic_client(make_anthropic_response(model="m")),
        price_path=price,
    )
    result = provider.ask(_request("m"))

    assert result.provider == "anthropic"
    assert result.response_id == "rid"
    assert result.response_text == "bonjour from claude"
    assert result.finish_reason == "end_turn"  # mapped from stop_reason
    assert result.usage.input_tokens == 200
    assert result.usage.output_tokens == 80
    assert result.usage.total_tokens is None  # Anthropic omits a total
    assert result.usage.cache_creation_input_tokens == 30
    assert result.usage.cache_read_input_tokens == 10


def test_anthropic_provider_reads_the_answer_past_a_thinking_block(tmp_path):
    # Regression: extended thinking is on by default on the 5-series models, so
    # content[0] is a `thinking` block (no .text) whenever the model decides to
    # think - which is why some questions parsed fine and others died with
    # "'ThinkingBlock' object has no attribute 'text'" AFTER being billed.
    price = write_price_table(tmp_path / "a.json", "m")
    provider = AnthropicProvider(
        client=fake_anthropic_client(
            make_anthropic_response(
                model="m",
                content=[anthropic_thinking_block(), anthropic_text_block()],
            )
        ),
        price_path=price,
    )
    result = provider.ask(_request("m"))

    assert result.response_text == "bonjour from claude"
    assert result.cost is not None  # the whole call still completes normally


def test_anthropic_provider_joins_every_text_block_in_order(tmp_path):
    # Citations split one answer across several contiguous text blocks; taking
    # only the first would silently truncate the answer instead of raising.
    price = write_price_table(tmp_path / "a.json", "m")
    provider = AnthropicProvider(
        client=fake_anthropic_client(
            make_anthropic_response(
                model="m",
                content=[
                    anthropic_text_block("Jason's maternal "),
                    anthropic_thinking_block(),  # interleaved thinking, still skipped
                    anthropic_text_block("great-grandfather was Cretheus."),
                ],
            )
        ),
        price_path=price,
    )
    result = provider.ask(_request("m"))

    assert result.response_text == "Jason's maternal great-grandfather was Cretheus."


def test_anthropic_provider_keeps_a_billed_response_with_no_text_block(tmp_path):
    # max_tokens exhausted during thinking: there is no answer, but the call was
    # paid for. Per the billing invariant it must come back as a result with an
    # empty body (which compare() then judges unusable), never as a parse crash.
    price = write_price_table(tmp_path / "a.json", "m")
    provider = AnthropicProvider(
        client=fake_anthropic_client(
            make_anthropic_response(model="m", content=[anthropic_thinking_block()])
        ),
        price_path=price,
    )
    result = provider.ask(_request("m"))

    assert result.response_text == ""
    assert result.usage.output_tokens == 80  # the tokens we were charged for
    assert result.cost is not None


def test_anthropic_cost_uses_split_cache_tiers(tmp_path):
    # Regression: Anthropic pricing has separate cache_read/cache_write tiers and
    # no `cached_input` key, and its input_tokens already excludes cache tokens.
    # Cost must bill both tiers and must NOT subtract cache from input_tokens.
    price = write_price_table(
        tmp_path / "a.json",
        "m",
        extra_rates={"cache_read": 0.1, "cache_write_5m": 1.25},
    )
    provider = AnthropicProvider(
        client=fake_anthropic_client(make_anthropic_response(model="m")),
        price_path=price,
    )
    result = provider.ask(_request("m"))

    # input_tokens=200 billed in full (no subtraction), output=80
    assert result.cost.input_usd == pytest.approx(200 / 1_000_000 * 1.0)
    assert result.cost.output_usd == pytest.approx(80 / 1_000_000 * 2.0)
    # cache_read=10 @0.1 + cache_write=30 @1.25 (both tiers counted, folded to one field)
    assert result.cost.cached_input_usd == pytest.approx(
        10 / 1_000_000 * 0.1 + 30 / 1_000_000 * 1.25
    )


def test_google_provider_maps_response(tmp_path):
    price = write_price_table(tmp_path / "g.json", "m")
    provider = GoogleProvider(
        client=fake_google_client(make_google_response(model="m")), price_path=price
    )
    result = provider.ask(_request("m"))

    assert result.provider == "google"
    assert result.response_id == "rid"
    assert result.response_text == "hi from gemini"
    assert result.finish_reason == "STOP"
    assert result.usage.input_tokens == 120
    assert result.usage.output_tokens == 60
    assert result.usage.total_tokens == 180
    assert result.usage.cached_input_tokens == 15
    assert result.cost is not None
