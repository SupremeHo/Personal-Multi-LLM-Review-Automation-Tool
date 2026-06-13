# Module that calculates the cost of API calls based on the number of tokens used and the model's pricing.
# Read the API models' list stored in /config/prices/prices_openai.json and calculate the cost.

import json
from decimal import Decimal
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
        print(f"No such file or directory: {path}")


def resolve_model_entry(
    price_table: dict,
    model_name: str,
) -> dict:
    """
    Resolve the price for a given model from the price table.
    If the model is an alias of another model, resolve the price of the original model.
    ex) gpt-4o-mini-2024-07-18 ===> gpt-4o-mini.
    If the model is not found in the price table, raise a ValueError.
    """
    models = price_table.get("models", {})

    if model_name not in models:
        raise KeyError(f"Price table for model '{model_name}' was not found.")

    price = models[model_name]

    if "alias_of" in price:
        return models[price["alias_of"]]

    return price


def to_decimal(value: int | float | str | None) -> Decimal | None:
    if value is None:
        return None

    return Decimal(str(value))


def calculate_openai_cost(
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

    if cached_input_tokens > 0:
        cached_input_cost = Decimal(cached_input_tokens) / Decimal(1_000_000) * cached_input_rate

    output_cost = Decimal(output_tokens) / Decimal(1_000_000) * output_rate

    total_cost = input_cost + cached_input_cost + output_cost

    return {
        "input_usd": float(input_cost),
        "cached_input_usd": float(cached_input_cost),
        "output_usd": float(output_cost),
        "total_usd": float(total_cost),
        "estimated": True,
        "pricing_updated_at": price_table.get("updated_at"),
        "pricing_source": price_table.get("source"),
    }


# if __name__ == "__main__":
#     # Example usage and print result for testing
#     price_table = load_price_table("resources/config/prices/prices_openai.json")
#     model_name = "gpt-5.5"
#     calculation_result = calculate_openai_cost(
#         price_table = price_table,
#         model_name = model_name,
#         input_tokens = 1000,
#         output_tokens = 2000,
#         cached_input_tokens = 0
#     )
#     print(calculation_result)
