# Anthropic provider: absorbs Anthropic's API specifics and returns an LLMCallResult.
# The shared pipeline lives in runner.run_chat; this module only supplies the two
# Anthropic-specific pieces - the paid call and the response parsing.

from __future__ import annotations

from pathlib import Path
from typing import Any

import anthropic
from anthropic import Anthropic

from resources.providers.runner import ParsedResponse, run_chat
from resources.schemas import LLMCallResult, LLMRequest, TokenUsageInfo

PRICE_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "prices"
PRICE_PATH_ANTHROPIC = PRICE_DIR / "prices_claude.json"

# Constructed at import time; set to None if the key/init fails so a missing key
# disables this provider instead of crashing the whole tool.
try:
    _default_client = Anthropic()
except anthropic.AnthropicError:
    _default_client = None


class AnthropicProvider:
    """Anthropic implementation of the ChatProvider contract (see base_provider)."""

    provider_name = "anthropic"

    def __init__(
        self,
        client: Any | None = _default_client,
        price_path: str | Path = PRICE_PATH_ANTHROPIC,
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
        # Anthropic requires max_tokens and takes the system prompt as a top-level arg.
        return self._client.messages.create(
            model=request.selected_model,
            max_tokens=request.max_tokens,
            system=request.system_prompt,
            messages=[{"role": "user", "content": request.user_question}],
        )

    def _parse_response(self, response: Any) -> ParsedResponse:
        # Anthropic returns a list of content blocks; the text lives on the first block.
        text = response.content[0].text
        usage = response.usage

        # Anthropic splits cache accounting into creation (write) and read counts.
        cache_creation = getattr(usage, "cache_creation_input_tokens", None)
        cache_read = getattr(usage, "cache_read_input_tokens", None)

        token_usage = TokenUsageInfo(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=None,  # Anthropic does not report a total; derived downstream.
            cache_creation_input_tokens=cache_creation,
            cache_read_input_tokens=cache_read,
        )

        # Anthropic reports cache read/write separately from input_tokens (no overlap),
        # each billed at its own tier: read is discounted, write is a premium.
        return ParsedResponse(
            model=response.model,
            response_text=text,
            finish_reason=response.stop_reason,  # Anthropic's equivalent of finish_reason
            raw_response_id=getattr(response, "id", None),
            usage=token_usage,
            uncached_input_tokens=usage.input_tokens,
            cache_read_tokens=cache_read or 0,
            cache_write_tokens=cache_creation or 0,
        )
