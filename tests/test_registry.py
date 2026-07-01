"""Provider registry tests."""

from __future__ import annotations

import pytest

from resources.providers import registry
from resources.providers.base_provider import ChatProvider


def test_known_providers_resolve_and_satisfy_contract():
    for name in ("openai", "anthropic", "google"):
        provider = registry.get_provider(name)
        assert provider.provider_name == name
        assert isinstance(provider, ChatProvider)


def test_unknown_provider_raises_keyerror():
    with pytest.raises(KeyError):
        registry.get_provider("does-not-exist")
