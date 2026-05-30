# Module that calculates the cost of API calls based on the number of tokens used and the model's pricing.

from schemas import TokenUsage, CostInfo

def calculate_openai_cost(token_usage: TokenUsage, model: str) -> CostInfo:
    """
    Calculate the cost of an OpenAI API call based on the token usage and model pricing.
    This is a placeholder function. You should replace the pricing logic with actual costs based on OpenAI's pricing.
    """
    # Example pricing (these values are placeholders and should be updated with actual pricing):
    model_pricing = {
        "gpt-4o-mini": {"input_cost_per_1m_tokens": 0.015, "output_cost_per_1m_tokens": 0.06},
        # Add other models and their pricing here
    }

    if model not in model_pricing:
        raise ValueError(f"Pricing information for model '{model}' is not available.")

    input_cost = (token_usage.prompt_tokens / 1000000) * model_pricing[model]["input_cost_per_1m_tokens"]
    output_cost = (token_usage.completion_tokens / 1000000) * model_pricing[model]["output_cost_per_1m_tokens"]
    total_cost = input_cost + output_cost

    return CostInfo(
        input_usd = input_cost,
        output_usd = output_cost,
        total_usd = total_cost
        )
