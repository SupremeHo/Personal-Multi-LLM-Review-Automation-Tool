# This module is responsible for 'generating request → calling providers → assembling logs → requesting archive'.
# Just gets a ChatProvider infused and call the .ask() method. It doesn't need to know specific providers.

from resources.providers import base_provider


def ask():
    base_provider.ChatProvider.generate()
    raise NotImplementedError
