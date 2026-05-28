# Module for calling LLMs(GPT/Claude/Gemini/etc)

# This code using OpenAI API calls GPT
# You can replace it with calls to other LLMs like Claude or Gemini by changing the API endpoint and request format accordingly. 

import openai
from openai import OpenAI
import env_check
import pandas as pd

MODEL_NAME = "gpt-4o-mini"  # You can change this to the desired model, e.g., "gpt-4o", "gpt-3.5-turbo", etc.
TEMPERATURE = 0     # Adjust the creativity of the response (0.0 to 1.0)
MAX_TOKENS = 500    # Set a limit on the number of tokens in the response (optional)

def ask_llm(user_question: str, system_prompt: str = "You are my personal assistant.") -> dict:
    # 1) Load environment variables from .env file with the check function defined in env_check.py.
    #env_check.check_environment_variables()

    # 2) Create an instance of the OpenAI client, which will be used to interact with the OpenAI API.
    client = OpenAI()

    # 3) List all available models or skip this process.
    list_available_models(client)

    # 4) Make a call to the OpenAI API to create a chat completion using the LLM model (ex. "gpt-4o-mini").
    try:
        # You can adjust the response style of the model by providing detailed parameters.
        LLM_response = client.chat.completions.create( 
            model = MODEL_NAME,
            temperature = TEMPERATURE,
            max_completion_tokens = MAX_TOKENS,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_question}
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
    except openai.RateLimitError as e:
        # Handle rate limit error (we recommend using exponential backoff).
        print(f"OpenAI API request exceeded rate limit: {e}" + "\n")
        pass
    except openai.APIConnectionError as e:
        # Handle connection error here.
        print(f"Failed to connect to OpenAI API: {e}" + "\n")
        pass
    except openai.APIError as e:
        # Handle API error here, e.g. retry or log.
        print(f"OpenAI API returned an API Error: {e}" + "\n")
        pass

# Optional function to list all available models.
# You can choose to list all models or skip this step based on user input.
def list_available_models(client: OpenAI):
    if input("Do you want to list all available models? (y/n): ").lower() == "y":
        models = client.models.list()
        print("\n" + "======== Available GPT Models ========")
        for model in models:
            if 'gpt' in model.id:
                print(model.id)
        print("======== End of GPT Models ========\n")
    else:
        print("\nSkipping model listing...\n")
