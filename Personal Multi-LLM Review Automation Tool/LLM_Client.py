# Calls to LLMs(GPT/Claude/Gemini/etc)

# This code using OpenAI API calls GPT
# You can replace it with calls to other LLMs like Claude or Gemini by changing the API endpoint and request format accordingly. 

import os 
from dotenv import load_dotenv
from openai import OpenAI
import pandas as pd
import time
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
        for model in models:
            if 'gpt' in model.id:
                print(model.id)
    else:
        print("\nSkipping model listing...\n")

    
    # 4) Make a call to the OpenAI API to create a chat completion using the LLM model (ex. "gpt-4o-mini").
    try:
        LLM_completion = client.chat.completions.create( 
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are my personal assistant."},
                {"role": "user", "content": "Please give a brief introduction about yourself."}
            ]
        )
        # Print the response from the LLM, which contains the generated content based on the input messages.
        print(LLM_completion.choices[0].message.content)

    # 5) Handle exceptions that may occur during the API call.
    except Exception as e:
        if "429" in str(e):
            print("Rate limit exceeded. You exceeded your current quota, please check your plan and billing details.\n")
            print("Please check the OpenAI API documentation for more information on rate limits and how to manage them: https://developers.openai.com/api/docs/guides/error-codes#:~:text=429%20%2D%20You%20exceeded,your%20limits \n")
        else:
            print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
