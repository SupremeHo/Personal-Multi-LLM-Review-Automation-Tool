# Module that calculates the cost of API calls based on the number of tokens used and the model's pricing.
# Read the API models' list stored in /config/prices/prices_openai.json and calculate the cost.
from __future__ import annotations

import datetime
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path


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
        print(
            f"[count_cost.py][def load_price_table] Error Message: No such file or directory: {path}\n"
        )
        raise

    except json.JSONDecodeError as e:
        print(f"[count_cost.py][def load_price_table] Error Message: {e.msg}")
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
        print(
            f"[count_cost.py][def resolve_model_entry] Error Message: Price table for model '{model_name}' was not found.\n"
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
        print(
            "[count_cost.py][def to_decimal] Error Message: Invalid operation or conversion.\n"
        )
        raise


def calculate_token_cost(
    price_table: dict,
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int = 0,
) -> dict:
    """
    Calculate the cost of an API call based on the model's pricing and the number of tokens used.
    Handle both normal input tokens and cached input tokens, applying the appropriate rates for each.
    """
    price = resolve_model_entry(price_table, model_name)

    input_rate = to_decimal(price["input"])
    cached_input_rate = to_decimal(price.get("cached_input"))
    output_rate = to_decimal(price["output"])

    normal_input_tokens = max(input_tokens - cached_input_tokens, 0)

    input_cost = Decimal(normal_input_tokens) / Decimal(1_000_000) * input_rate

    cached_input_cost = Decimal("0")

    if cached_input_tokens > 0 and cached_input_rate is not None:
        cached_input_cost = (
            Decimal(cached_input_tokens) / Decimal(1_000_000) * cached_input_rate
        )

    output_cost = Decimal(output_tokens) / Decimal(1_000_000) * output_rate

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
        print(
            f"\n[count_cost.py][notice_price_tag_update] Error Message: There is no update date or the date format is different - {e}\n"
        )
        return None


# def main():
#     price_table = load_price_table("resources/config/prices/prices_openai.json")
#     model_name = "gpt-4o-mini"
#     calculation_result = calculate_token_cost(
#         price_table=price_table, model_name=model_name, input_tokens=1000, output_tokens=2000, cached_input_tokens=0
#     )
#     print(calculation_result)


# if __name__ == "__main__":
#     main()
