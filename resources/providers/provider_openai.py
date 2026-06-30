# This module is responsible for absorbing the unique fields of OpenAI's API and translating them into LLMCallResult.

from pathlib import Path  # noqa: I001
from typing import Protocol
from uuid import uuid4

import openai
from openai import OpenAI

from count_cost import calculate_token_cost, preflight_pricing
from providers.response_error import PaidResponseError
from schemas import CostInfo, LLMCallResult, TokenUsageInfo

PRICE_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "prices"
PRICE_PATH_OPENAI = PRICE_DIR / "prices_openai.json"

SELECTED_MODEL = "gpt-4o-mini"

try:
    client = OpenAI()
except openai.OpenAIError:
    client = None


class OpenAICompatibleTransport(Protocol):
    def chatCompletionsCreate(
        self, system_prompt: str, user_question: str, selected_model: str
    ):
        response = client.chat.completions.create(
            model=selected_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_question},
            ],
        )

        return response


class OpenAIProvider(Protocol):
    def ask(
        self, system_prompt: str, user_question: str, selected_model: str
    ) -> LLMCallResult:
        """
        Usage:
         Call the OpenAI API to get a response from the specified model
         based on the provided system prompt and user question.

         Returns an LLMCallResult object containing the response text and metadata.

        ---
        Args:
          system_prompt: An instruction that predetermines how LLM should respond.

          user_question: A message to LLM for questions or instructions (The more specific and clear, the better.)

          response_id: UUID for identification of individual LLM response units.

          selected_model: OpenAI's model ID(ex. "gpt-4o-mini") used to generate the response.
        """

        if client is None:
            raise RuntimeError(
                "[provider_openai.py] Error Message: OpenAI client is unavailable. Check OPENAI_API_KEY and the environment setup.\n"
            )

        # Preflight: validate the price table and model name BEFORE the paid call so that a missing
        # price file or a mistyped model fails for free instead of after we have already been billed.
        selected_model = SELECTED_MODEL
        price_table_openai = preflight_pricing(PRICE_PATH_OPENAI, selected_model)

        # >>>>> Paid call. Money is spent here. <<<<<
        response_openai = client.chat.completions.create(
            model=selected_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_question},
            ],
        )

        # >>>>> Everything below runs AFTER billing; a failure here must not throw away the paid response. <<<<<
        try:
            choice_openai = response_openai.choices[0]
        except IndexError:
            print(
                "[provider_openai.py] Error Message: There aren't choices in OpenAI's response.\n"
            )
            raise

        # Extract token usage information from the OpenAI response and create a TokenUsage object.
        usage_openai = response_openai.usage

        try:
            cached_tokens = (
                usage_openai.prompt_tokens_details.cached_tokens
                if usage_openai.prompt_tokens_details
                else None
            )

            token_usage_openai = TokenUsageInfo(
                input_tokens=usage_openai.prompt_tokens,
                output_tokens=usage_openai.completion_tokens,
                total_tokens=usage_openai.total_tokens,
                cached_tokens=cached_tokens,
            )
        except AttributeError:
            print(
                "[provider_openai.py] Error Message: There is no usage info in OpenAI's response.\n"
            )
            raise

        # Best-effort cost calculation. If it fails (e.g. a broken price entry), keep the error aside so we can
        # still build the result and preserve the response/tokens we already paid for.
        cost_info_openai = None
        cost_error: Exception | None = None
        try:
            cost_openai = calculate_token_cost(
                price_table=price_table_openai,
                model_name=response_openai.model,
                input_tokens=usage_openai.prompt_tokens,
                output_tokens=usage_openai.completion_tokens,
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
                f"[provider_openai.py] Error Message: Cost calculation failed after billing - {e}\n"
            )

        # Extract the relevant information from the OpenAI response and assemble the result object.
        result = LLMCallResult(
            response_id=str(uuid4),
            provider="OpenAI",
            model=response_openai.model,
            response_text=choice_openai.message.content,
            finish_reason=choice_openai.finish_reason,
            raw_response_id=getattr(response_openai, "id", None),
            usage=token_usage_openai,
            cost=cost_info_openai,
        )

        # If cost calc failed, the run is a failure - but hand the preserved result to the caller for the audit log.
        if cost_error is not None:
            raise PaidResponseError(result, cost_error)

        return result


def main():
    system_prompt = "You are a helpful assistant."
    user_question = "Hello. I'm currently testing if the Google API works well in the terminal CLI environment. If you see this message, could you please create a short English sentence for the current date and time, with the phrase 'API connection successful!'?"

    print(OpenAIProvider.ask(system_prompt, user_question, SELECTED_MODEL))


if __name__ == "__main__":
    main()
