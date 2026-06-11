# Module for listing all available models.
# You can choose to list all models or skip this step based on user input.

from openai import OpenAI


def list_available_models(client: OpenAI):
    if input("Do you want to list all available models? (y/n): ").lower() == "y":
        models = client.models.list()
        print("\n" + "======== Available GPT Models ========")
        for model in models:
            if "gpt" in model.id:
                print(model.id)
        print("======== End of GPT Models ========\n")
    else:
        print("\nSkipping model listing...\n")
