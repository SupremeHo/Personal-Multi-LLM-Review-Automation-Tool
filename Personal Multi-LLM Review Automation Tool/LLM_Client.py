# Calls to LLMs(GPT/Claude/Gemini/etc)

# This code using OpenAI API calls GPT
# You can replace it with calls to other LLMs like Claude or Gemini by changing the API endpoint and request format accordingly. 

import openai
import os               # For handling environment variables, useful for securely storing API keys
import pandas as pd     # For handling data in tabular format, useful for processing and analyzing LLM responses
import time             # For handling rate limits and retries

# Set your OpenAI API key here. You can generate an API key from the OpenAI dashboard and replace the placeholder string below with your actual key.
#OPENAI_YOUR_API_KEY = "Your Generated API Key Here"
OPENAI_YOUR_API_KEY = os.getenv("OPENAI_API_KEY")  # It's a good practice to store API keys in environment variables for security reasons. You can set the OPENAI_API_KEY environment variable in your system or use a .env file with a library like python-dotenv to load it.
openai.api_key = OPENAI_YOUR_API_KEY

client = openai.OpenAI(api_key=OPENAI_YOUR_API_KEY)  # Create an instance of the OpenAI client to interact with the API

models = client.models.list()
for model in models:
    if 'gpt' in model.id:
        print(model.id)

