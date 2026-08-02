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
        # >>>>> Paid call. Money is spent here. <<<<<
        return self._client.chat.completions.create(
            model=request.selected_model,
            messages=[
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_question},
            ],
        )

    def _parse_response(self, response: Any) -> ParsedResponse:
        choice = response.choices[0]  # IndexError here propagates as a failure
        usage = response.usage

        cached_tokens = (
            usage.prompt_tokens_details.cached_tokens
            if usage.prompt_tokens_details
            else None
        )

        token_usage = TokenUsageInfo(
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
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
