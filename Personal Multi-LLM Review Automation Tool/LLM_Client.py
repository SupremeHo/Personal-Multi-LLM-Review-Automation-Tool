# Calls to LLMs(GPT/Claude/Gemini/etc)

# This code using OpenAI API calls GPT
# You can replace it with calls to other LLMs like Claude or Gemini by changing the API endpoint and request format accordingly. 

import os
import time
import openai
from openai import OpenAI
import pandas as pd
import env_check

def main():
    # 1) Load environment variables from .env file with the check function defined in env_check.py.
    env_check.check_environment_variables()

    # 2) Create an instance of the OpenAI client, which will be used to interact with the OpenAI API.
    client = OpenAI()

    # 3) Prompt the user to decide whether they want to list all available models.
    list_models = input("Do you want to list all available models? (y/n): ").lower() == "y"

    if list_models:
        models = client.models.list()
        print("\n" + "======== Available GPT Models ========")
        for model in models:
            if 'gpt' in model.id:
                print(model.id)
        print("======== End of GPT Models ========\n")
    else:
        print("\nSkipping model listing...\n")



    # 4) Make a call to the OpenAI API to create a chat completion using the LLM model (ex. "gpt-4o-mini").
    try:
        # You can adjust the response style of the model by providing detailed parameters.
        LLM_response = client.chat.completions.create( 
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are my personal assistant."},
                {"role": "user", "content": "Please give a brief introduction about yourself."}
            ]
        )

        LLM_choice = LLM_response.choices[0]
        LLM_usage = LLM_response.usage

        # Print the response from the LLM, which contains the generated content based on the input messages.
        print("\n" + "======== LLM's Response ========")
        print(LLM_choice.message.content + "\n")

        # Outputs meta data such as the tokens used, model name, and finish_reason.
        print("======== LLM Usage ========")
        print(f"Model: {LLM_response.model}")
        print(f"Finish Reason: {LLM_choice.finish_reason}")
        print(f"Prompt Tokens: {LLM_usage.prompt_tokens}")
        print(f"Completion Tokens: {LLM_usage.completion_tokens}")
        print(f"Total Tokens: {LLM_usage.total_tokens}")

    # 5) Handle exceptions that may occur during the API call.
    except openai.APIError as err:
        # Handle API error here, e.g. retry or log.
        print(f"OpenAI API returned an API Error: {err}" + "\n")
        pass
    except openai.APIConnectionError as err:
        # Handle connection error here.
        print(f"Failed to connect to OpenAI API: {err}" + "\n")
        pass
    except openai.RateLimitError as err:
        # Handle rate limit error (we recommend using exponential backoff).
        print(f"OpenAI API request exceeded rate limit: {err}" + "\n")
        pass
    else:
        print(f"An error occurred: {err}" + "\n")

if __name__ == "__main__":
    main()
