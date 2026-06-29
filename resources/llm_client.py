# Module for calling LLMs API(GPT/Claude/Gemini/etc)
# Extract the required value from the response object.
# Returns objects such as LLMCallResult, which contains the LLM response content and metadata such as tokens used, model name, and finish_reason.

from pathlib import Path  # noqa: I001

import anthropic
import openai
from anthropic import Anthropic
from google import genai
from google.genai import errors
from openai import OpenAI

from count_cost import calculate_token_cost, preflight_pricing
from schemas import CostInfo, LLMCallResult, TokenUsageInfo


# Resolve price tables relative to this file so the lookup does not depend on the current working directory.
PRICE_DIR = Path(__file__).resolve().parent.parent / "config" / "prices"
PRICE_PATH_OPENAI = PRICE_DIR / "prices_openai.json"


# Create an instance of the clients in OpenAI, Anthropic and Goolge, which will be used to interact with the OpenAI, Anthropic and Google API.
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


class PaidResponseError(Exception):
    """
    Raised when a paid API call already succeeded (a response was billed and received)
    but a later, non-billing step failed - for example cost calculation.

    The run should be judged a failure, yet the response and token usage we already
    paid for must not be discarded. This exception carries that partial result so the
    caller can persist it as an audit log instead of losing it.
    """

    def __init__(self, result: LLMCallResult, original: Exception):
        self.result = result  # The response/tokens that were already paid for.
        self.original = original  # The underlying failure that happened after billing.
        super().__init__(str(original))


SELECTED_MODEL = "gpt-4o-mini"


def ask_openai(
    system_prompt: str,
    user_question: str,
    response_id: str,
    selected_model: str = SELECTED_MODEL,
) -> LLMCallResult:
    """
    Usage:
     Call the OpenAI API to get a response from the specified model
     based on the provided system prompt and user question.

     Returns an LLMCallResult object containing the response text and metadata.

    ---

    Arguments:
      system_prompt: An instruction that predetermines how LLM should respond.

      user_question: A message to LLM for questions or instructions (The more specific and clear, the better.)

      response_id: UUID for identification of individual LLM response units.

      selected_model: OpenAI's model ID(ex. "gpt-4o-mini") used to generate the response.
    """
    if client_openai is None:
        raise RuntimeError(
            "[llm_client.py] Error Message: OpenAI client is unavailable. Check OPENAI_API_KEY and the environment setup.\n"
        )

    # Preflight: validate the price table and model name BEFORE the paid call so that a missing
    # price file or a mistyped model fails for free instead of after we have already been billed.
    price_table_openai = preflight_pricing(PRICE_PATH_OPENAI, selected_model)

    # >>>>> Paid call. Money is spent here. <<<<<
    openai_response = client_openai.chat.completions.create(
        model=selected_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_question},
        ],
    )

    # >>>>> Everything below runs AFTER billing; a failure here must not throw away the paid response. <<<<<
    try:
        openai_choice = openai_response.choices[0]
    except IndexError:
        print(
            "[llm_client.py] Error Message: There aren't choices in OpenAI's response.\n"
        )
        raise

    # Extract token usage information from the OpenAI response and create a TokenUsageInfo object.
    openai_usage = openai_response.usage

    try:
        cached_tokens = (
            openai_usage.prompt_tokens_details.cached_tokens
            if openai_usage.prompt_tokens_details
            else None
        )

        token_usage_openai = TokenUsageInfo(
            prompt_tokens=openai_usage.prompt_tokens,
            completion_tokens=openai_usage.completion_tokens,
            total_tokens=openai_usage.total_tokens,
            cached_tokens=cached_tokens,
        )
    except AttributeError:
        print(
            "[llm_client.py] Error Message: There is no usage info in OpenAI's response.\n"
        )
        raise

    # Best-effort cost calculation. If it fails (e.g. a broken price entry), keep the error aside so we can
    # still build the result and preserve the response/tokens we already paid for.
    cost_info_openai = None
    cost_error: Exception | None = None
    try:
        cost_openai = calculate_token_cost(
            price_table=price_table_openai,
            model_name=openai_response.model,
            input_tokens=openai_usage.prompt_tokens,
            output_tokens=openai_usage.completion_tokens,
            cached_input_tokens=cached_tokens or 0,
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
    except Exception as e:  # noqa: BLE001 - any cost failure must not discard the paid response.
        cost_error = e
        print(
            f"[llm_client.py] Error Message: Cost calculation failed after billing - {e}\n"
        )

    # Extract the relevant information from the OpenAI response and assemble the result object.
    result = LLMCallResult(
        response_id=response_id,
        provider="OpenAI",
        model=openai_response.model,
        response_text=openai_choice.message.content,
        finish_reason=openai_choice.finish_reason,
        raw_response_id=getattr(openai_response, "id", None),
        usage=token_usage_openai,
        cost=cost_info_openai,
    )

    # If cost calc failed, the run is a failure - but hand the preserved result to the caller for the audit log.
    if cost_error is not None:
        raise PaidResponseError(result, cost_error)

    return result


def ask_anthropic(
    system_prompt: str, user_question: str, selected_model: str = ""
) -> LLMCallResult:
    raise NotImplementedError("Anthropic integration not yet implemented")


def ask_google(
    system_prompt: str, user_question: str, selected_model: str = ""
) -> LLMCallResult:
    raise NotImplementedError("Google Gemini integration not yet implemented")
