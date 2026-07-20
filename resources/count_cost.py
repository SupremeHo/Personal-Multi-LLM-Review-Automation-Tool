# Module that calculates the cost of API calls based on the number of tokens used and the model's pricing.
# Read the API models' list stored in /config/prices/prices_openai.json and calculate the cost.
from __future__ import annotations

import datetime
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from resources.diagnostics import print_error


def load_price_table(path: str | Path) -> dict:
    """
    Load the price table from a JSON file and return it as a dictionary.
    If the file does not exist, print an error message.
    """
    try:
        with Path(path).open("r", encoding="utf-8") as f:
            # print(f"Price table loaded from {path}")
            return json.load(f)

    except FileNotFoundError:
        print_error(
            f"No such file or directory: {path}",
            module="count_cost.py",
            func="load_price_table",
        )
        raise

    except json.JSONDecodeError as e:
        print_error(e.msg, module="count_cost.py", func="load_price_table")
        print(f"Error Location (Line: {e.lineno}, Column: {e.colno})")
        print(f"JSON string in error: {e.doc}\n")
        raise


def resolve_model_entry(
    price_table: dict,
    model_name: str,
) -> dict:
    """
    Resolve the price for a given model from the price table.

    If the model is an alias of another model, resolve the price of the original model.
    ex) `gpt-4o-mini-2024-07-18` → `gpt-4o-mini`.

    If the model is not found in the price table, raise a KeyError.
    """
    models = price_table.get("models", {})

    try:
        price = models[model_name]
    except KeyError:
        print_error(
            "Model that alias_of refers to was not found.",
            module="count_cost.py",
            func="resolve_model_entry",
        )
        raise

    try:
        if "alias_of" in price:
            return models[price["alias_of"]]
    except KeyError:
        print(
            "[count_cost.py][def resolve_model_entry] Error Message: Model that alias_of refers to was not found.\n"
        )
        raise

    return price


def preflight_pricing(price_path: str | Path, model_name: str) -> dict:
    """
    Validate everything that can be checked BEFORE a paid API call is made.

    Confirms that the price table file exists and parses, and that the requested
    model is known to the table. Run this before spending money so that a missing
    price file or a mistyped model name fails cheaply instead of after billing.

    Returns the loaded price table so the caller can reuse it (avoids a second load).
    """
    price_table = load_price_table(price_path)  # exists + parses
    resolve_model_entry(price_table, model_name)  # model name is known
    return price_table


def to_decimal(value: int | float | str | None) -> Decimal | None:
    """
    Solve the floating-point errors to perform decimal operations that require high precision,
    such as financial calculations.
    """
    if value is None:
        return None

    try:
        return Decimal(str(value))
    except InvalidOperation:
        print_error(
            "Invalid operation or conversion.",
            module="count_cost.py",
            func="to_decimal",
        )
        raise


def calculate_token_cost(
    price_table: dict,
    model_name: str,
    *,
    uncached_input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> dict:
    """
    Calculate the cost of an API call from three non-overlapping input token
    buckets, each billed at its own rate, plus output tokens.

    Callers (providers) normalize their own cache accounting into these buckets,
    so this function needs no per-provider branching:

      * ``uncached_input_tokens`` - full-price prompt tokens (``input`` rate).
      * ``cache_read_tokens``     - tokens served from cache, discounted. The rate
        is named ``cache_read`` (Anthropic) or ``cached_input`` (OpenAI/Gemini).
      * ``cache_write_tokens``    - tokens written to cache, an Anthropic-only
        premium (``cache_write_5m`` rate); zero/absent for other providers.

    The cache tiers are folded into a single ``cached_input_usd`` in the result
    so the cost schema stays flat; ``total_usd`` is always the sum of all tiers.
    """
    price = resolve_model_entry(price_table, model_name)

    input_rate = to_decimal(price["input"])
    output_rate = to_decimal(price["output"])
    # Cache-read rate: `cache_read` (Anthropic) or `cached_input` (OpenAI/Gemini).
    read_rate_raw = price.get("cache_read")
    if read_rate_raw is None:
        read_rate_raw = price.get("cached_input")
    cache_read_rate = to_decimal(read_rate_raw)
    # Cache-write (prompt-cache creation) is an Anthropic-only premium; default 5m TTL.
    cache_write_rate = to_decimal(price.get("cache_write_5m"))

    million = Decimal(1_000_000)
    input_cost = Decimal(uncached_input_tokens) / million * input_rate
    output_cost = Decimal(output_tokens) / million * output_rate

    cached_input_cost = Decimal("0")
    if cache_read_tokens > 0 and cache_read_rate is not None:
        cached_input_cost += Decimal(cache_read_tokens) / million * cache_read_rate
    if cache_write_tokens > 0 and cache_write_rate is not None:
        cached_input_cost += Decimal(cache_write_tokens) / million * cache_write_rate

    total_cost = input_cost + cached_input_cost + output_cost

    notice_price_tag_update(price_table.get("updated_at"))

    return {
        "input_usd": float(input_cost),
        "cached_input_usd": float(cached_input_cost),
        "output_usd": float(output_cost),
        "total_usd": float(total_cost),
        "estimated": True,
        "pricing_updated_at": price_table.get("updated_at"),
        "pricing_source": price_table.get("source"),
    }


def notice_price_tag_update(updated_at: str = ""):
    """
    Notice an alert for renewal if it's been 30 days
    since the update about price information
    """
    try:
        today_obj = datetime.datetime.now()
        updated_at_obj = datetime.datetime.strptime(updated_at, "%Y-%m-%d")

        days_delta = today_obj - updated_at_obj

        if days_delta.days > 30:
            print(
                "\nToken unit price information is over 30 days old. Check the price_****.json.\n"
            )
    except ValueError as e:
        print_error(
            f"There is no update date or the date format is different - {e}",
            module="count_cost.py",
            func="notice_price_tag_update",
        )
        return None
