# Module for listing all available models.
# You can choose to list all models or skip this step based on user input.

import sys

from anthropic import Anthropic
from google import genai
from openai import OpenAI


def list_available_models(client_openai: OpenAI, client_anthropic: Anthropic, client_google: genai):
    """"""
    while True:
        try:
            print(
                "Would you like to list the available API's models? Please select and enter one of the three companies. (OpenAI, Anthropic, or Google)"
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
                print("\nError. Please enter your input correctly.\n")
                continue
        except ValueError as e:
            sys.exit(e + " Invalid value input. Exit the program.")


def list_available_openai_models(client=OpenAI()):
    """The function listing the available models in OpenAI."""

    try:
        models = client.models.list()
        print("\n" + "======== Available OpenAI's Models ========")
        for model in models:
            if "gpt" in model.id:
                print(model.id)
        print("======== End of OpenAI's Models ========\n")
    except Exception as e:
        print(e)


def list_available_claude_models(client=Anthropic()):
    """The function listing the available models in Anthropic."""

    try:
        models = client.models.list()
        print("\n" + "======== Available Anthropic's Models ========")
        for model in models:
            print(model.id)
        print("======== End of Anthropic's Models ========\n")
    except Exception as e:
        print(e)


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
        print("======== End of Google's Models ========\n")
    except Exception as e:
        print(e)


# if __name__ == "__main__":
#     client_openai = OpenAI()
#     client_anthropic = Anthropic()
#     client_gemini = genai.Client()
#     list_available_models(client_openai, client_anthropic, client_gemini)
