# Google (Gemini) provider: absorbs Gemini's API specifics and returns an LLMCallResult.
# The shared pipeline lives in runner.run_chat; this module only supplies the two
# Gemini-specific pieces - the paid call and the response parsing.

from __future__ import annotations

from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from resources.providers.runner import ParsedResponse, run_chat
from resources.schemas import LLMCallResult, LLMRequest, TokenUsageInfo

PRICE_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "prices"
PRICE_PATH_GOOGLE = PRICE_DIR / "prices_gemini.json"

# Constructed at import time; set to None if the key/init fails so a missing key
# disables this provider instead of crashing the whole tool.
try:
    _default_client = genai.Client()
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

        token_usage = TokenUsageInfo(
            input_tokens=usage.prompt_token_count,
            output_tokens=usage.candidates_token_count,
            total_tokens=usage.total_token_count,
            cached_input_tokens=cached_tokens,
        )

        finish_reason = candidate.finish_reason
        return ParsedResponse(
            model=response.model_version,
            response_text=response.text,
            finish_reason=finish_reason.value if finish_reason else None,
            raw_response_id=getattr(response, "response_id", None),
            usage=token_usage,
            cached_input_tokens_for_cost=cached_tokens or 0,
        )
