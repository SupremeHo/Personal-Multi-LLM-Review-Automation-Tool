# Module for listing all available models.
# You can choose to list all models or skip this step based on user input.

from anthropic import Anthropic
from google import genai
from openai import OpenAI


def list_available_models(client_openai: OpenAI, client_anthropic: Anthropic, client_google: genai):
    print("Would you like to list the available models in OpenAI, Anthropic, and Google?")
    answer = input(
        "If you input the word 'all', list the all available models. If you want to skip, input the word 'No': "
    ).lower()
    if answer == "openai":
        list_available_openai_models(client_openai)
    elif answer == "anthropic":
        list_available_claude_models(client_anthropic)
    elif answer == "google":
        list_available_claude_models(client_google)
    elif answer == "all":
        list_available_openai_models(client_openai)
        list_available_claude_models(client_anthropic)
        list_available_gemini_models(client_google)
    elif answer == "no":
        print("\nSkipping model listing...\n")
    else:
        print("\nPlease check your input.\n")


def list_available_openai_models(client=OpenAI()):
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
    try:
        models = client.models.list()
        print("\n" + "======== Available Anthropic's Models ========")
        for model in models:
            print(model.id)
        print("======== End of Anthropic's Models ========\n")
    except Exception as e:
        print(e)


def list_available_gemini_models(client=genai.Client()):
    try:
        models = client.models.list()
        print("\n" + "======== Available Google's Models ========")
        for model in models:
            if "gemini" in model.name:
                print(model.name)
        print("======== End of Google's Models ========\n")
    except Exception as e:
        print(e)


if __name__ == "__main__":
    client_openai = OpenAI()
    client_anthropic = Anthropic()
    client_gemini = genai.Client()
    list_available_models(client_openai, client_anthropic, client_gemini)
