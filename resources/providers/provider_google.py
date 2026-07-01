# Google (Gemini) provider: stub implementation of the ChatProvider contract.
#
# Not yet wired up. Once implemented it will follow the same shape as the OpenAI
# and Anthropic providers: supply a _call_api and a _parse_response to
# runner.run_chat. Kept as a concrete class (not a Protocol) so the registry can
# treat all providers uniformly.

from __future__ import annotations

from resources.schemas import LLMCallResult, LLMRequest


class GoogleProvider:
    """Google Gemini implementation of the ChatProvider contract (not yet implemented)."""

    provider_name = "google"

    def ask(self, request: LLMRequest) -> LLMCallResult:
        raise NotImplementedError("GoogleProvider.ask is not yet implemented.")
