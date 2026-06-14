# Module for listing all available models.
# You can choose to list all models or skip this step based on user input.

import sys

from anthropic import Anthropic, AnthropicError
from google import genai
from google.genai import errors
from openai import OpenAI, OpenAIError


def list_available_models(client_openai: OpenAI, client_anthropic: Anthropic, client_google: genai):
    """The function to ask users whether they want to list the available LLM models or not"""
    while True:
        try:
            print(
                "\nWould you like to list the available API's models? Please select and enter one of the three companies. (OpenAI, Anthropic, or Google)"
            )
            answer = input(
                "If you want to check the all available models, input the word 'Yes'. If you want to skip, input the word 'No': "
            ).lower()

            if answer == "openai":
                list_available_openai_models(client_openai)
                break
            elif answer == "anthropic":
                list_available_claude_models(client_anthropic)
                break
            elif answer == "google":
                list_available_gemini_models(client_google)
                break
            elif answer == "yes":
                list_available_openai_models(client_openai)
                list_available_claude_models(client_anthropic)
                list_available_gemini_models(client_google)
                break
            elif answer == "no":
                print("\nSkipping model listing...\n")
                break
            else:
                print("\nError. Please enter your input correctly.")
                continue
        except EOFError:
            sys.exit("Invalid value input. Exit the program.")


def list_available_openai_models(client=OpenAI()):
    """The function listing the available models in OpenAI."""
    try:
        models = client.models.list()
        print("\n" + "======== Available OpenAI's Models ========")
        for model in models:
            if "gpt" in model.id:
                print(model.id)
        print("======== Finished listing OpenAI's Models list ========\n")
    except OpenAIError as e:
        print(f"Failed to list OpenAI's models: {e}")
        raise


def list_available_claude_models(client=Anthropic()):
    """The function listing the available models in Anthropic."""
    try:
        models = client.models.list()
        print("\n" + "======== Available Anthropic's Models ========")
        for model in models:
            print(model.id)
        print("======== Finished listing Anthropic's Models list ========\n")
    except AnthropicError as e:
        print(f"Failed to list Anthropic's models: {e}")
        raise


def list_available_gemini_models(client=genai.Client()):
    """The function listing the available models in Google Gemini."""
    try:
        models = client.models.list()
        print("\n" + "======== Available Google's Models ========")
        for model in models:
            if "gemini" in model.name:
                text = model.name
                new_text = text.strip("models/")
                print(new_text)
        print("======== Finished listing Google's Models list ========\n")
    except errors.APIError as e:
        print(f"Failed to list Google's models: {e}")
        raise


def main():
    client_openai = OpenAI()
    client_anthropic = Anthropic()
    client_google = genai.Client()
    list_available_models(client_openai, client_anthropic, client_google)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Program failed: {e}", file=sys.stderr)
        sys.exit(1)
