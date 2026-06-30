# This module abstracts and defines only the common protocols of providers offering APIs that allow LLM to be called, such as OpenAI, Anthropic, and Google.
# API differences for each provider are not defined here; instead, each 'provider_*name*.py' absorbs API differences and returns them to LLMCallResult.

from typing import Protocol

from provider_anthropic import AnthropicNativeProvider
from provider_google import GoogleProvider
from provider_openai import OpenAIProvider

from resources.schemas import LLMCallResult, LLMRequest

# providers/registry.py (Conceptual Sketch)
PROVIDERS = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicNativeProvider,
    "google": GoogleProvider,
}


class ChatProvider(Protocol):
    provider_name: str

    async def generateRequest(self, request: LLMRequest) -> LLMCallResult:
        raise NotImplementedError
