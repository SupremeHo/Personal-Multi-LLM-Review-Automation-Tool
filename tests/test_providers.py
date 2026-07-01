"""Per-provider parsing/mapping tests (no paid calls; price tables are temp files)."""

from __future__ import annotations

from resources.providers.base_provider import ChatProvider
from resources.providers.provider_anthropic import AnthropicProvider
from resources.providers.provider_google import GoogleProvider
from resources.providers.provider_openai import OpenAIProvider
from resources.schemas import LLMRequest
from tests.fakes import (
    fake_anthropic_client,
    fake_openai_client,
    make_anthropic_response,
    make_openai_response,
    write_price_table,
)


def _request(model):
    return LLMRequest(
        response_id="rid", system_prompt="s", user_question="q", selected_model=model
    )


def test_providers_satisfy_contract():
    assert isinstance(OpenAIProvider(client=object()), ChatProvider)
    assert isinstance(AnthropicProvider(client=object()), ChatProvider)
    assert isinstance(GoogleProvider(), ChatProvider)


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


def test_google_provider_not_implemented():
    import pytest

    with pytest.raises(NotImplementedError):
        GoogleProvider().ask(_request("gemini-x"))
