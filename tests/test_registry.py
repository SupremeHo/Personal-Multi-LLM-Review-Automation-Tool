# Provider registry tests.

from __future__ import annotations

import pytest

from resources.providers import registry
from resources.providers.base_provider import ChatProvider


def test_known_providers_resolve_and_satisfy_contract():
    for name in ("openai", "anthropic", "google"):
        provider = registry.get_provider(name)
        assert provider.provider_name == name
        assert isinstance(provider, ChatProvider)


def test_providers_are_shared_instances():
    # compare() calls one instance from several threads at once, so the contract
    # that ask() is thread-safe rests on this sharing being deliberate.
    assert registry.get_provider("openai") is registry.get_provider("openai")


def test_unknown_provider_raises_keyerror():
    with pytest.raises(KeyError) as excinfo:
        registry.get_provider("does-not-exist")

    # Raised as KeyError(print_error(...)), so the name and the list of known
    # providers only reach the caller if print_error returns the message.
    raised = str(excinfo.value)
    assert "does-not-exist" in raised
    assert "openai" in raised
