# Google (Gemini) provider: absorbs Gemini's API specifics and returns an LLMCallResult.
# The shared pipeline lives in runner.run_chat; this module only supplies the two
# Gemini-specific pieces - the paid call and the response parsing.

from __future__ import annotations

from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from resources.call_policy import MAX_RETRIES, TOTAL_TIMEOUT_MS
from resources.providers.runner import ParsedResponse, run_chat
from resources.schemas import LLMCallResult, LLMRequest, TokenUsageInfo

PRICE_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "prices"
PRICE_PATH_GOOGLE = PRICE_DIR / "prices_gemini.json"

# Constructed at import time; set to None if the key/init fails so a missing key
# disables this provider instead of crashing the whole tool. Timeout and retry
# budget are stated explicitly (see call_policy). Two Gemini-specific quirks: the
# timeout is a single millisecond value (no connect/read split), and `attempts`
# counts the FIRST call too, so it is the retry budget plus one.
try:
    _default_client = genai.Client(
        http_options=types.HttpOptions(
            timeout=TOTAL_TIMEOUT_MS,
            retry_options=types.HttpRetryOptions(attempts=MAX_RETRIES + 1),
        )
    )
except ValueError:
    _default_client = None


class GoogleProvider:
    """Google Gemini implementation of the ChatProvider contract (see base_provider)."""

    provider_name = "google"

    def __init__(
        self,
        client: Any | None = _default_client,
        price_path: str | Path = PRICE_PATH_GOOGLE,
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
        # Gemini takes the system prompt inside GenerateContentConfig, not as a message.
        return self._client.models.generate_content(
            model=request.selected_model,
            contents=request.user_question,
            config=types.GenerateContentConfig(
                system_instruction=request.system_prompt,
                max_output_tokens=request.max_tokens,
            ),
        )

    def _parse_response(self, response: Any) -> ParsedResponse:
        candidate = response.candidates[0]  # IndexError here propagates as a failure
        usage = response.usage_metadata

        cached_tokens = usage.cached_content_token_count

        # Thinking tokens are billed at the output rate but live OUTSIDE
        # candidates_token_count: the API defines total_token_count as the sum of
        # prompt + candidates + tool_use_prompt + thoughts, and Google's pricing
        # docs say "response pricing is the sum of output tokens and thinking
        # tokens". Reading candidates_token_count alone therefore billed for the
        # answer and nothing for the reasoning that produced it - measured at
        # ~23x under on gemini-2.5-flash, which thinks by default. Adding them
        # here is what keeps TokenUsageInfo.output_tokens meaning the same thing
        # on every provider, and fixes cost by construction (runner.run_chat
        # bills from output_tokens).
        thoughts = usage.thoughts_token_count or 0
        billable_output = (usage.candidates_token_count or 0) + thoughts

        token_usage = TokenUsageInfo(
            input_tokens=usage.prompt_token_count,
            output_tokens=billable_output,
            total_tokens=usage.total_token_count,  # already counts thoughts
            reasoning_tokens=thoughts,
            cached_input_tokens=cached_tokens,
        )

        # Gemini's prompt_token_count includes the cached portion, so subtract it out.
        cache_read = cached_tokens or 0
        finish_reason = candidate.finish_reason
        return ParsedResponse(
            model=response.model_version,
            # `.text` is None when no text part survives - the thinking-exhausted
            # case, where max_tokens ran out before the answer began. That is a
            # billed response, so it must not fail LLMCallResult's `str` validation
            # and lose its cost record; an empty body is left to the service layer,
            # which already treats it as unusable (mirrors _answer_text on Anthropic).
            response_text=response.text or "",
            finish_reason=finish_reason.value if finish_reason else None,
            raw_response_id=getattr(response, "response_id", None),
            usage=token_usage,
            uncached_input_tokens=max(usage.prompt_token_count - cache_read, 0),
            cache_read_tokens=cache_read,
        )
