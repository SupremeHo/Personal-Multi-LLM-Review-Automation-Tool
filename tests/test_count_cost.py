# Cost calculation and price-table resolution tests.

from __future__ import annotations

import pytest

from resources.count_cost import (
    calculate_token_cost,
    preflight_pricing,
    resolve_model_entry,
    to_decimal,
)

PRICE_TABLE = {
    "updated_at": "2099-01-01",
    "source": "test",
    "models": {
        "base": {"input": 1.0, "cached_input": 0.5, "output": 2.0},
        "alias": {"alias_of": "base"},
    },
}

# Anthropic-shaped entry: no `cached_input`, but split cache tiers instead.
ANTHROPIC_PRICE = {
    "updated_at": "2099-01-01",
    "source": "test",
    "models": {
        "claude": {
            "input": 1.0,
            "cache_read": 0.1,
            "cache_write_5m": 1.25,
            "output": 2.0,
        },
    },
}


def test_cost_without_cache():
    cost = calculate_token_cost(
        PRICE_TABLE,
        "base",
        uncached_input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    assert cost["input_usd"] == pytest.approx(1.0)
    assert cost["output_usd"] == pytest.approx(2.0)
    assert cost["total_usd"] == pytest.approx(3.0)
    assert cost["estimated"] is True


def test_cost_with_cache_read_discount():
    # OpenAI/Gemini shape: cache is a subset of input, so the caller passes the
    # already-subtracted uncached portion plus the cache-read count.
    cost = calculate_token_cost(
        PRICE_TABLE,
        "base",
        uncached_input_tokens=800_000,
        output_tokens=0,
        cache_read_tokens=200_000,
    )
    # 800k normal @1.0 + 200k cache-read @0.5 = 0.8 + 0.1
    assert cost["input_usd"] == pytest.approx(0.8)
    assert cost["cached_input_usd"] == pytest.approx(0.1)
    assert cost["total_usd"] == pytest.approx(0.9)


def test_cost_anthropic_cache_tiers():
    # Anthropic shape: read (discount) and write (premium) are separate, additive
    # tiers, and no `cached_input` key exists. Both must be billed, not ignored.
    cost = calculate_token_cost(
        ANTHROPIC_PRICE,
        "claude",
        uncached_input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_read_tokens=1_000_000,
        cache_write_tokens=1_000_000,
    )
    assert cost["input_usd"] == pytest.approx(1.0)
    # cache-read @0.1 + cache-write @1.25, folded into one field
    assert cost["cached_input_usd"] == pytest.approx(0.1 + 1.25)
    assert cost["output_usd"] == pytest.approx(2.0)
    assert cost["total_usd"] == pytest.approx(1.0 + 0.1 + 1.25 + 2.0)


def test_resolve_model_entry_follows_alias():
    assert resolve_model_entry(PRICE_TABLE, "alias") == PRICE_TABLE["models"]["base"]


def test_resolve_unknown_model_raises():
    with pytest.raises(KeyError):
        resolve_model_entry(PRICE_TABLE, "nope")


def test_preflight_returns_table_and_validates_model(tmp_path):
    import json

    p = tmp_path / "prices.json"
    p.write_text(json.dumps(PRICE_TABLE), encoding="utf-8")
    table = preflight_pricing(p, "base")
    assert table["models"]["base"]["input"] == 1.0

    with pytest.raises(KeyError):
        preflight_pricing(p, "unknown")


def test_to_decimal_none_passthrough():
    assert to_decimal(None) is None
    assert to_decimal("1.5") is not None
