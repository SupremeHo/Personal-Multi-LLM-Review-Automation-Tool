"""
Module that calculates the cost of API calls based on the number of tokens used and the model's pricing.
Read the API models' list stored in /config/prices/prices_openai.json and calculate the cost.
"""

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
        raise KeyError(f"Price info for model '{model_name}' was not found.")

    current_model = model_name
    current_entry = models[current_model]

    while "alias_of" in current_entry:
        current_model = current_entry["alias_of"]

        if current_model not in models:
            raise KeyError(f"Alias model {current_model} was not found in price table.")

        current_entry = models[current_model]

    return current_model, current_entry


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
