# Provider registry: maps a canonical provider key to a ready-to-use ChatProvider.
#
# This is the one place that knows which concrete providers exist. The service
# layer resolves providers through here and never imports a concrete provider
# directly, so adding a provider is a one-line change in PROVIDERS.

from __future__ import annotations

from resources.diagnostics import print_error
from resources.providers.base_provider import ChatProvider
from resources.providers.provider_anthropic import AnthropicProvider
from resources.providers.provider_google import GoogleProvider
from resources.providers.provider_openai import OpenAIProvider

# Instantiated once and reused. Each provider holds a module-level SDK client
# (or None when its key is missing), so construction is cheap and side-effect free.
PROVIDERS: dict[str, ChatProvider] = {
    OpenAIProvider.provider_name: OpenAIProvider(),
    AnthropicProvider.provider_name: AnthropicProvider(),
    GoogleProvider.provider_name: GoogleProvider(),
}


def get_provider(provider_name: str) -> ChatProvider:
    """
    Resolve a provider by its canonical key ("openai", "anthropic", "google").

    Raises:
      KeyError: The name is not registered, with the list of known providers.
    """
    try:
        return PROVIDERS[provider_name]
    except KeyError:
        known = ", ".join(sorted(PROVIDERS))
        raise KeyError(
            print_error(
                f"Unknown provider '{provider_name}'. Known providers: {known}",
                module="registry.py",
                func="get_provider",
            )
        ) from None
