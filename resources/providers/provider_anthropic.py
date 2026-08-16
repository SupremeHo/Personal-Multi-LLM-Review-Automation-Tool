# Anthropic provider: absorbs Anthropic's API specifics and returns an LLMCallResult.
# The shared pipeline lives in runner.run_chat; this module only supplies the two
# Anthropic-specific pieces - the paid call and the response parsing.

from __future__ import annotations

from pathlib import Path
from typing import Any

import anthropic
from anthropic import Anthropic

from resources.call_policy import HTTP_TIMEOUT, MAX_RETRIES
from resources.providers.runner import ParsedResponse, run_chat
from resources.schemas import LLMCallResult, LLMRequest, TokenUsageInfo

PRICE_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "prices"
PRICE_PATH_ANTHROPIC = PRICE_DIR / "prices_claude.json"


def _build_default_client() -> Anthropic | None:
    """
    Build the import-time client, or None when no credential resolved.

    Unlike OpenAI() and genai.Client(), Anthropic() does NOT raise on a missing
    key - it returns a keyless client that sends no auth header and fails only at
    call time with a 401, i.e. after money would have been spent. Catching the
    constructor is therefore not enough here: the credential has to be checked
    explicitly so a missing key disables this provider instead of arriving as a
    401 on the paid path.

    The check asks the client what it *resolved* rather than reading an
    environment variable directly, because the SDK honours ANTHROPIC_API_KEY and
    ANTHROPIC_AUTH_TOKEN both - duplicating that list here is how the two drift
    apart.

    Timeout and retry budget are stated explicitly (see call_policy) rather than
    left to the SDK's 10-minute default, which would hold a whole comparison
    hostage.
    """
    try:
        client = Anthropic(timeout=HTTP_TIMEOUT, max_retries=MAX_RETRIES)
    except anthropic.AnthropicError:
        return None

    return client if client.api_key or client.auth_token else None


# Decided at import time so a missing key disables this provider instead of
# crashing the whole tool. Kept in a function so the decision is testable without
# reloading the module.
_default_client = _build_default_client()

THINKING: dict[str, Any] | None = None
"""
Whether to ask for extended thinking, and how. None means the parameter is not sent.

Stated here rather than inherited, in the same spirit as call_policy.MAX_RETRIES:
the value equals today's behaviour, but the decision now lives in one named place.
That matters because *omitting* `thinking` does not mean "no thinking" - the
default is decided by the model generation. On the 5-series (claude-sonnet-5,
claude-fable-5) an omitted parameter runs adaptive thinking; on claude-haiku-4-5
the identical request does not think at all. One line of code therefore already
means two different things depending on the model string, invisibly at the call
site, and which one it means will keep changing as models ship.

None is the default because no single value is valid across prices_claude.json.
Verified against the Models API (GET /v1/models/{id}, free - see capabilities.thinking):

    {"type": "adaptive"}                     rejected on opus-4-5, sonnet-4-5, haiku-4-5
    {"type": "enabled", "budget_tokens": N}  rejected on fable-5, opus-4-8, opus-4-7, sonnet-5
    {"type": "disabled"}                     rejected on fable-5
    output_config={"effort": ...}            unsupported on sonnet-4-5, haiku-4-5

Omitting is the only setting the whole table accepts, so pinning a value here
would trade a silent behaviour difference for a hard 400 on part of it.

Set this when the models actually targeted agree - e.g. {"type": "adaptive"} for a
5-series-only workflow. Two costs to weigh first:

  * Thinking tokens bill at output rates and Anthropic reports no separate count,
    so they are folded indistinguishably into TokenUsageInfo.output_tokens: the
    ledger cannot say how much of a bill was reasoning. On the 5-series
    `thinking.display` also defaults to "omitted", so that is reasoning we pay for
    and never receive.
  * request.max_tokens caps thinking AND the answer together. Long enough reasoning
    exhausts the ceiling and the response arrives with no text block at all -
    billed, and unusable to compare() (see _answer_text). Raise max_tokens in the
    same change, not after.
"""


def _answer_text(content: Any) -> str:
    """
    Join the answer out of Anthropic's content-block list.

    The blocks are a heterogeneous sequence, and the answer is NOT always the
    first of them: with extended thinking on (the default on claude-sonnet-5 and
    the other 5-series models, where a request that omits the `thinking` parameter
    runs adaptive thinking) content[0] is a `thinking` block, which carries the
    reasoning on `.thinking` and has no `.text` at all. Indexing content[0].text
    therefore raised AttributeError on exactly the questions the model chose to
    think about - after the call had already been billed.

    So blocks are selected by `type` and concatenated rather than indexed by
    position: skipping the non-text blocks also covers `redacted_thinking` and
    tool-use blocks, and joining covers the several-text-blocks case (citations
    split the answer into one block per cited span, which must be rejoined in
    order). The separator is empty because the blocks are contiguous pieces of
    one message, not separate messages.

    Returns an empty string when the response carries no text block at all - a
    real outcome when max_tokens is exhausted during thinking. That is left to
    the service layer, which already treats an empty body as an unusable answer;
    raising here would discard a response that was paid for.
    """
    return "".join(
        block.text for block in content if getattr(block, "type", None) == "text"
    )


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
        # `thinking` is sent only when the policy sets one: the shapes the parameter
        # accepts differ per model generation, so an unconditional kwarg would 400 on
        # part of the price table (see THINKING). Read at call time, not captured at
        # import, so the policy stays patchable.
        thinking_kwargs: dict[str, Any] = {}
        if THINKING is not None:
            thinking_kwargs["thinking"] = THINKING

        # >>>>> Paid call. Money is spent here. <<<<<
        # Anthropic requires max_tokens and takes the system prompt as a top-level arg.
        return self._client.messages.create(
            model=request.selected_model,
            max_tokens=request.max_tokens,
            system=request.system_prompt,
            messages=[{"role": "user", "content": request.user_question}],
            **thinking_kwargs,
        )

    def _parse_response(self, response: Any) -> ParsedResponse:
        text = _answer_text(response.content)
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
