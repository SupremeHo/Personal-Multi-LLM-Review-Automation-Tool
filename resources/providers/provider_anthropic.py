# This module is responsible for absorbing the unique fields of Anthropic's API and translating them into LLMCallResult.

from pathlib import Path
from typing import Protocol
from uuid import uuid4

import anthropic
from anthropic import Anthropic

from resources.count_cost import calculate_token_cost, preflight_pricing
from resources.providers.response_error import PaidResponseError
from resources.schemas import CostInfo, LLMCallResult, TokenUsageInfo

PRICE_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "prices"
PRICE_PATH_ANTHROPIC = PRICE_DIR / "prices_anthropic.json"

SELECTED_MODEL = "claude-haiku-4-5"

try:
    client = Anthropic()
except anthropic.AnthropicError:
    client = None


class AnthropicNativeProvider(Protocol):
    def ask(
        self, system_prompt: str, user_question: str, selected_model: str
    ) -> LLMCallResult:
        """
        Usage:
         Call the Anthropic API to get a response from the specified model
         based on the provided system prompt and user question.

         Returns an LLMCallResult object containing the response text and metadata.

        ---
        Args:
          system_prompt: An instruction that predetermines how LLM should respond.

          user_question: A message to LLM for questions or instructions (The more specific and clear, the better.)

          response_id: UUID for identification of individual LLM response units.

          selected_model: Anthropic's model ID(ex. "claude-haiku-4-5") used to generate the response.
        """

        if client is None:
            raise RuntimeError(
                "[provider_anthropic.py] Error Message: Anthropic client is unavailable. Check ANTHROPIC_API_KEY and the environment setup.\n"
            )

        # Preflight: validate the price table and model name BEFORE the paid call so that a missing
        # price file or a mistyped model fails for free instead of after we have already been billed.
        selected_model = SELECTED_MODEL
        price_table_anthropic = preflight_pricing(PRICE_PATH_ANTHROPIC, selected_model)

        # >>>>> Paid call. Money is spent here. <<<<<
        response_anthropic = client.messages.create(
            model=selected_model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_question}],
        )

        # >>>>> Everything below runs AFTER billing; a failure here must not throw away the paid response. <<<<<
        try:
            choice_anthropic = response_anthropic.content
        except IndexError as e:
            raise print(
                "[provider_anthropic.py] Error Message: There aren't content in Anthropic's response.\n"
            ) from e

        # Extract token usage information from the anthropic response and create a TokenUsage object.
        usage_anthropic = response_anthropic.usage

        try:
            cached_tokens = (
                (
                    usage_anthropic.cache_creation_input_tokens
                    + usage_anthropic.cache_read_input_tokens
                )
                if usage_anthropic
                else None
            )

            token_usage_anthropic = TokenUsageInfo(
                input_tokens=usage_anthropic.input_tokens,
                output_tokens=usage_anthropic.output_tokens,
                total_tokens=usage_anthropic.total_tokens,
                cached_tokens=cached_tokens,
            )
        except AttributeError:
            print(
                "[llm_client.py] Error Message: There is no usage info in anthropic's response.\n"
            )
            raise

        # Best-effort cost calculation. If it fails (e.g. a broken price entry), keep the error aside so we can
        # still build the result and preserve the response/tokens we already paid for.
        cost_info_anthropic = None
        cost_error: Exception | None = None
        try:
            cost_anthropic = calculate_token_cost(
                price_table=price_table_anthropic,
                model_name=response_anthropic.model,
                input_tokens=usage_anthropic.prompt_tokens,
                output_tokens=usage_anthropic.completion_tokens,
                cached_input_tokens=cached_tokens or 0,
            )
            cost_info_anthropic = CostInfo(
                input_usd=cost_anthropic.get("input_usd"),
                cached_input_usd=cost_anthropic.get("cached_input_usd"),
                output_usd=cost_anthropic.get("output_usd"),
                total_usd=cost_anthropic.get("total_usd"),
                estimated=cost_anthropic.get("estimated"),
                pricing_updated_at=cost_anthropic.get("pricing_updated_at"),
                pricing_source=cost_anthropic.get("pricing_source"),
            )
        except Exception as e:  # noqa: BLE001 - any cost failure must not discard the paid response.
            cost_error = e
            print(
                f"[llm_client.py] Error Message: Cost calculation failed after billing - {e}\n"
            )

        # Extract the relevant information from the anthropic response and assemble the result object.
        result = LLMCallResult(
            response_id=str(uuid4),
            provider="anthropic",
            model=response_anthropic.model,
            response_text=choice_anthropic.message.content,
            finish_reason=choice_anthropic.finish_reason,
            raw_response_id=getattr(response_anthropic, "id", None),
            usage=token_usage_anthropic,
            cost=cost_info_anthropic,
        )

        # If cost calc failed, the run is a failure - but hand the preserved result to the caller for the audit log.
        if cost_error is not None:
            raise PaidResponseError(result, cost_error)

        return result
