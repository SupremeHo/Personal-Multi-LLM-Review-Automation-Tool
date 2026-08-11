"""Per-provider parsing/mapping tests (no paid calls; price tables are temp files)."""

from __future__ import annotations

import pytest

from resources.providers.base_provider import ChatProvider
from resources.providers.provider_anthropic import (
    AnthropicProvider,
    _build_default_client,
)
from resources.providers.provider_google import GoogleProvider
from resources.providers.provider_openai import OpenAIProvider
from resources.schemas import LLMRequest
from tests.fakes import (
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


def test_providers_satisfy_contract():
    assert isinstance(OpenAIProvider(client=object()), ChatProvider)
    assert isinstance(AnthropicProvider(client=object()), ChatProvider)
    assert isinstance(GoogleProvider(client=object()), ChatProvider)


def _no_anthropic_credentials(monkeypatch):
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(name, raising=False)


def test_anthropic_client_is_none_without_credentials(monkeypatch):
    # Regression: Anthropic() does not raise on a missing key the way OpenAI()
    # and genai.Client() do - it hands back a keyless client. `except
    # AnthropicError` alone therefore left _default_client non-None, so a missing
    # key skipped runner's pre-billing guard and surfaced as a 401 instead.
    _no_anthropic_credentials(monkeypatch)
    assert _build_default_client() is None


def test_anthropic_client_is_none_for_a_blank_key(monkeypatch):
    # A .env copied from .env.example supplies "" rather than nothing at all.
    _no_anthropic_credentials(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    assert _build_default_client() is None


def test_anthropic_client_is_built_when_a_key_is_present(monkeypatch):
    _no_anthropic_credentials(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    assert _build_default_client() is not None


def test_anthropic_client_accepts_an_auth_token(monkeypatch):
    # The SDK resolves ANTHROPIC_AUTH_TOKEN too, which is why the check asks the
    # client what it resolved rather than reading one variable name here.
    _no_anthropic_credentials(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "not-a-real-token")
    assert _build_default_client() is not None


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
