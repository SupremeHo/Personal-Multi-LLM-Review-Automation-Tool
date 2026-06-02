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
            #print(f"Price table loaded from {path}")
            return json.load(f)

    except FileNotFoundError:
        print(f"No such file or directory: {path}")


def resolve_model_price(price_table: dict, model: str) -> dict:
    """
    Resolve the price for a given model from the price table.
    If the model is an alias of another model, resolve the price of the original model.
    If the model is not found in the price table, raise a ValueError.
    """
    models = price_table.get("models", {})
    try:
        price = models[model]

        if "alias_of" in price:
            return models[price["alias_of"]]    # Recursively resolve the price of the original model if this model is an alias

        return price

    except Exception as e:
        if model not in models:
            raise ValueError(f"Price for API's model '{model}' is not defined.")
        else:
            raise e


def calculate_text_cost(price_table: dict, model: str, input_tokens: int, output_tokens: int, cached_input_tokens: int = 0, ) -> dict:
    """
    Calculate the cost of an API call based on the number of input tokens, output tokens, and cached input tokens, as well as the model's pricing.
    Returns a dictionary containing the input cost, cached input cost, output cost, total cost, and metadata about the pricing.
    """
    price = resolve_model_price(price_table, model)

    if input_tokens + output_tokens < 272_000:
        price["Short context"]
    
    # input_rate = Decimal(str(price["input"]))
    # cached_input_rate = Decimal(str(price.get("cached_input", price["input"])))
    # output_rate = Decimal(str(price["output"]))

    # normal_input_tokens = max(input_tokens - cached_input_tokens, 0)

    # input_cost = Decimal(normal_input_tokens) / Decimal(1_000_000) * input_rate
    # cached_input_cost = Decimal(cached_input_tokens) / Decimal(1_000_000) * cached_input_rate
    # output_cost = Decimal(output_tokens) / Decimal(1_000_000) * output_rate

    # total_cost = input_cost + cached_input_cost + output_cost

    # Debugging output removed; use logging if needed

    # return {
    #     "input_usd": float(input_cost),
    #     "cached_input_usd": float(cached_input_cost),
    #     "output_usd": float(output_cost),
    #     "total_usd": float(total_cost),
    #     "estimated": True,
    #     "pricing_updated_at": price_table.get("updated_at"),
    #     "pricing_source": price_table.get("source"),
    # }


if __name__ == "__main__":
    # Example usage and print result for testing
    price_table = load_price_table("resources/config/prices/prices_openai.json")
    try:
        model = "gpt-5.5"
        result = resolve_model_price(price_table, model)
        print(f"Price for model '{model}' resolved: {result}")
    except Exception as e:
        print("Error:", e)
