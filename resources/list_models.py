# Module for listing all available models.
# You can choose to list all models or skip this step based on user input.

import sys
from collections.abc import Callable
from typing import Any

from anthropic import Anthropic, AnthropicError
from google import genai
from google.genai import errors
from openai import OpenAI, OpenAIError


def _list_models(
    client: Any,
    *,
    label: str,
    error_type: type[Exception],
    extract: Callable[[Any], str | None],
) -> None:
    """
    List a single provider's models.

    Providers differ only in their label, the error type they raise, and how a
    model id is extracted/filtered (`extract` returns the name to print, or None
    to skip), so the listing logic itself is written once here.
    """
    if client is None:
        print(f"Error Message: {label} client is unavailable. Check that the API key is set.")
        return

    try:
        models = client.models.list()
        print("\n" + f"======== Available {label}'s Models ========")
        for model in models:
            name = extract(model)
            if name is not None:
                print(name)
        print(f"======== Finished listing {label}'s Models list ========\n")

    except error_type as e:
        print(f"Error Message: Failed to list {label}'s models: {e}")
        raise


def list_available_models(
    client_openai: OpenAI, client_anthropic: Anthropic, client_google: genai
):
    """Ask the user which provider's models to list, then list them."""
    listers = {
        "openai": lambda: _list_models(
            client_openai,
            label="OpenAI",
            error_type=OpenAIError,
            extract=lambda m: m.id if "gpt" in m.id else None,
        ),
        "anthropic": lambda: _list_models(
            client_anthropic,
            label="Anthropic",
            error_type=AnthropicError,
            extract=lambda m: m.id,
        ),
        "google": lambda: _list_models(
            client_google,
            label="Google",
            error_type=errors.APIError,
            extract=lambda m: (
                m.name.removeprefix("models/") if "gemini" in m.name else None
            ),
        ),
    }

    while True:
        try:
            print(
                "\nWould you like to list the available API's models? Please select and enter one of the three companies. (OpenAI, Anthropic, or Google)"
            )

            answer = input(
                "If you want to check the all available models, input the word 'Yes'. If you want to skip, input the word 'No': "
            ).lower()

            if answer in listers:
                listers[answer]()
                break
            elif answer == "yes":
                for lister in listers.values():
                    lister()
                break
            elif answer == "no":
                print("\nSkipping model listing...\n")
                break
            else:
                print("\nPlease enter your input correctly.")
                continue

        except EOFError:
            sys.exit("Error Message: Read beyond end of file. Exit the program.")

        except KeyboardInterrupt:
            sys.exit("Error Message: Program interrupted by user. Exit the program.")
