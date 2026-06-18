# Module for calling LLMs API(GPT/Claude/Gemini/etc)
# Extract the required value from the response object.
# Returns objects such as LLMCallResult, which contains the LLM response content and metadata such as tokens used, model name, and finish_reason.

import anthropic  # noqa: I001
import openai
from anthropic import Anthropic
from google import genai
from google.genai import errors
from openai import OpenAI

from count_cost import calculate_token_cost, load_price_table
from schemas import CostInfo, LLMCallResult, TokenUsage

# 1) Create an instance of the clients in OpenAI, Anthropic and Goolge, which will be used to interact with the OpenAI, Anthropic and Google API.
try:
    client_openai = OpenAI()
except openai.OpenAIError as e:
    print(f"[llm_client.py] Error Message: {e}. Error while using OpenAI API.")
    client_openai = None

try:
    client_anthropic = Anthropic()
except anthropic.AnthropicError as e:
    print(f"[llm_client.py] Error Message: {e}. Error while using Anthropic API.")
    client_anthropic = None

try:
    client_google = genai.Client()
except errors.APIError as e:
    print(f"[llm_client.py] Error Message: {e}. Error while using Google API.")
    client_google = None


# 2) Make a call to the OpenAI API to create a chat completion using the LLM model (ex. "gpt-4o-mini").
def ask_openai(system_prompt: str, user_question: str, selected_model: str = "gpt-4o-mini") -> LLMCallResult:
    """
    Call the OpenAI API to get a response from the specified model based on the provided system prompt and user question.

    Returns an LLMCallResult object containing the response text and metadata.
    """
    # You can adjust the response style of the model by providing detailed parameters.
    openai_response = client_openai.chat.completions.create(
        model=selected_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_question},
        ],
    )

    try:
        openai_choice = openai_response.choices[0]
    except IndexError:
        print("[llm_client.py] Error Message: There aren't choices in OpenAI's response.\n")
        raise

    # Extract token usage information from the OpenAI response and create a TokenUsage object.
    openai_usage = openai_response.usage

    try:
        token_usage_openai = TokenUsage(
            prompt_tokens=openai_usage.prompt_tokens,
            completion_tokens=openai_usage.completion_tokens,
            total_tokens=openai_usage.total_tokens,
            cached_tokens=openai_usage.prompt_tokens_details.cached_tokens if openai_usage.prompt_tokens_details else None,
        )
    except AttributeError:
        print("[llm_client.py] Error Message: There is no usage info in OpenAI's response.\n")
        raise

    # Calculate the cost of the API call based on the token usage and the model's pricing, and create a CostInfo object.
    price_table_openai = load_price_table("resources/config/prices/prices_openai.json")

    if not price_table_openai:
        print()
        cost_info_openai = None
    else:
        cost_openai = calculate_token_cost(
            price_table=price_table_openai,
            model_name=openai_response.model,
            input_tokens=openai_usage.prompt_tokens,
            output_tokens=openai_usage.completion_tokens,
            cached_input_tokens=openai_usage.prompt_tokens_details.cached_tokens
            if openai_usage.prompt_tokens_details
            else None,
        )
        cost_info_openai = CostInfo(
            input_usd=cost_openai.get("input_usd"),
            cached_input_usd=cost_openai.get("cached_input_usd"),
            output_usd=cost_openai.get("output_usd"),
            total_usd=cost_openai.get("total_usd"),
            estimated=cost_openai.get("estimated"),
            pricing_updated_at=cost_openai.get("pricing_updated_at"),
            pricing_source=cost_openai.get("pricing_source"),
        )

    # 3) Extract the relevant information from the OpenAI response and return it as an LLMCallResult object.
    return LLMCallResult(
        provider="OpenAI",
        model=openai_response.model,
        response_text=openai_choice.message.content,
        finish_reason=openai_choice.finish_reason,
        raw_response_id=getattr(openai_response, "id", None),
        usage=token_usage_openai,
        cost=cost_info_openai,
    )


def ask_anthropic(system_prompt: str, user_question: str, selected_model: str = "") -> LLMCallResult:
    print("temp")


def ask_google(system_prompt: str, user_question: str, selected_model: str = "") -> LLMCallResult:
    print("temp")
