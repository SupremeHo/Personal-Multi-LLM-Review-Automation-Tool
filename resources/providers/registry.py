# Provider registry: maps a canonical provider key to a ready-to-use ChatProvider.
#
# This is the one place that knows which concrete providers exist. The service
# layer resolves providers through here and never imports a concrete provider
# directly, so adding a provider is a one-line change in PROVIDERS.

from __future__ import annotations

from pathlib import Path

from resources.diagnostics import print_error
from resources.providers.base_provider import ChatProvider
from resources.providers.provider_anthropic import (
    PRICE_PATH_ANTHROPIC,
    AnthropicProvider,
)
from resources.providers.provider_google import PRICE_PATH_GOOGLE, GoogleProvider
from resources.providers.provider_openai import PRICE_PATH_OPENAI, OpenAIProvider

# Instantiated once and reused. Each provider holds a module-level SDK client
# (or None when its key is missing), so construction is cheap and side-effect free.
PROVIDERS: dict[str, ChatProvider] = {
    OpenAIProvider.provider_name: OpenAIProvider(),
    AnthropicProvider.provider_name: AnthropicProvider(),
    GoogleProvider.provider_name: GoogleProvider(),
}

# Each provider's price table, keyed like PROVIDERS. The service layer reads it
# to resolve model aliases (`alias_of`) before a paid call - the providers keep
# owning their own price path; this only makes the mapping resolvable by key.
# Adding a provider adds one line here too.
PRICE_PATHS: dict[str, Path] = {
    OpenAIProvider.provider_name: PRICE_PATH_OPENAI,
    AnthropicProvider.provider_name: PRICE_PATH_ANTHROPIC,
    GoogleProvider.provider_name: PRICE_PATH_GOOGLE,
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
