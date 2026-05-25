# Calls to LLMs(GPT/Claude/Gemini/etc)

# This code using OpenAI API calls GPT
# You can replace it with calls to other LLMs like Claude or Gemini by changing the API endpoint and request format accordingly. 

import openai
import os 
from dotenv import load_dotenv
import pandas as pd
import time

load_dotenv()  # Load environment variables from a .env file, which is a common practice for managing sensitive information like API keys

key = os.getenv("OPENAI_API_KEY")  # Retrieve the OpenAI API key from environment variables
print("key 10 chars:", key[:10] if key else "Key not found")  # Print the first 10 characters of the API key for verification (avoid printing the entire key for security reasons)
print("key length:", len(key) if key else "Key not found")  # Print the length of the API key to confirm it has been loaded correctly

# Set your OpenAI API key here. You can generate an API key from the OpenAI dashboard and replace the placeholder string below with your actual key.
#OPENAI_YOUR_API_KEY = "Your Generated API Key Here"
#OPENAI_YOUR_API_KEY = os.getenv("OPENAI_API_KEY")  # It's a good practice to store API keys in environment variables for security reasons. You can set the OPENAI_API_KEY environment variable in your system or use a .env file with a library like python-dotenv to load it.
#openai.api_key = OPENAI_YOUR_API_KEY

#client = openai.OpenAI(api_key=OPENAI_YOUR_API_KEY)  # Create an instance of the OpenAI client to interact with the API

# models = client.models.list()
# for model in models:
#     if 'gpt' in model.id:
#         print(model.id)

