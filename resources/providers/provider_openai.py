# OpenAI provider: absorbs OpenAI's API specifics and returns an LLMCallResult.
# The shared pipeline lives in runner.run_chat; this module only supplies the two
# OpenAI-specific pieces - the paid call and the response parsing.

from __future__ import annotations

from pathlib import Path
from typing import Any

import openai
from openai import OpenAI

from resources.call_policy import HTTP_TIMEOUT, MAX_RETRIES
from resources.providers.runner import ParsedResponse, run_chat
from resources.schemas import LLMCallResult, LLMRequest, TokenUsageInfo

PRICE_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "prices"
PRICE_PATH_OPENAI = PRICE_DIR / "prices_openai.json"

# Constructed at import time; set to None if the key/init fails so a missing key
# disables this provider instead of crashing the whole tool. Timeout and retry
# budget are stated explicitly (see call_policy) rather than left to the SDK's
# 10-minute default, which would hold a whole comparison hostage.
try:
    _default_client = OpenAI(timeout=HTTP_TIMEOUT, max_retries=MAX_RETRIES)
except openai.OpenAIError:
    _default_client = None

REASONING_EFFORT: str | None = None
"""
How much reasoning to ask for. None means the parameter is not sent.

Stated here rather than inherited, for the same reason as
provider_anthropic.THINKING: omitting it means "whatever this model does by
default", and that differs per model - the GPT-5 family reasons out of the box
(gpt-5.5 defaults to medium effort), while the gpt-4o family does not reason at
all and REJECTS the parameter.

None is the default because the accepted values are model-dependent too
(`none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, with each model
supporting only a subset), and the price table spans both families. Pinning one
value here would make the CLI's own default model - gpt-4o-mini - fail.

Unlike Gemini, nothing needs correcting downstream: OpenAI counts reasoning
tokens INSIDE completion_tokens, so the cost was always right. What was missing
is only the breakdown, now reported as TokenUsageInfo.reasoning_tokens.
"""


class OpenAIProvider:
    """OpenAI implementation of the ChatProvider contract (see base_provider)."""

    provider_name = "openai"

    def __init__(
        self,
        client: Any | None = _default_client,
        price_path: str | Path = PRICE_PATH_OPENAI,
    ):
        self._client = client
        self._price_path = price_path

    def ask(self, request: LLMRequest) -> LLMCallResult:
        return run_chat(
            request=request,
            provider_name=self.provider_name,
            client=self._client,
            price_path=self._price_path,
            call_api=self._call_api,
            parse_response=self._parse_response,
        )

    def _call_api(self, request: LLMRequest) -> Any:
        # `reasoning_effort` is sent only when the policy sets one: the gpt-4o family
        # rejects the parameter and the accepted values differ per model, so an
        # unconditional kwarg would break part of the price table (see
        # REASONING_EFFORT). Read at call time, not captured at import, so the policy
        # stays patchable.
        reasoning_kwargs: dict[str, Any] = {}
        if REASONING_EFFORT is not None:
            reasoning_kwargs["reasoning_effort"] = REASONING_EFFORT

        # >>>>> Paid call. Money is spent here. <<<<<
        # max_completion_tokens, not the deprecated max_tokens: newer models reject
        # the old name outright. Without it the request's ceiling silently did not
        # apply here, unlike Anthropic and Gemini.
        return self._client.chat.completions.create(
            model=request.selected_model,
            max_completion_tokens=request.max_tokens,
            messages=[
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_question},
            ],
            **reasoning_kwargs,
        )

    def _parse_response(self, response: Any) -> ParsedResponse:
        choice = response.choices[0]  # IndexError here propagates as a failure
        usage = response.usage

        cached_tokens = (
            usage.prompt_tokens_details.cached_tokens
            if usage.prompt_tokens_details
            else None
        )

        # Reported for visibility only: OpenAI counts these inside completion_tokens
        # (unlike Gemini, where thoughts sit outside candidates_token_count), so they
        # must NOT be added to output_tokens - that would bill the reasoning twice.
        reasoning_tokens = (
            usage.completion_tokens_details.reasoning_tokens
            if usage.completion_tokens_details
            else None
        )

        token_usage = TokenUsageInfo(
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,  # already includes reasoning
            total_tokens=usage.total_tokens,
            reasoning_tokens=reasoning_tokens,
            cached_input_tokens=cached_tokens,
        )

        # OpenAI's prompt_tokens includes the cached portion, so subtract it out.
        cache_read = cached_tokens or 0
        return ParsedResponse(
            model=response.model,
            response_text=choice.message.content,
            finish_reason=choice.finish_reason,
            raw_response_id=getattr(response, "id", None),
            usage=token_usage,
            uncached_input_tokens=max(usage.prompt_tokens - cache_read, 0),
            cache_read_tokens=cache_read,
        )
