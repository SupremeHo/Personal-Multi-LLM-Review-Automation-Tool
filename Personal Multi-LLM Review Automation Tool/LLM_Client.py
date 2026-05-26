# Calls to LLMs(GPT/Claude/Gemini/etc)

# This code using OpenAI API calls GPT
# You can replace it with calls to other LLMs like Claude or Gemini by changing the API endpoint and request format accordingly. 

import os 
from dotenv import load_dotenv
import pandas as pd
import openai
import time

# Load environment variables from a .env file, which is a common practice for managing sensitive information like API keys
load_dotenv()  

# Create an instance of the OpenAI client to interact with the API
#client = openai.OpenAI(api_key=OPENAI_YOUR_API_KEY)  

# models = client.models.list()
# for model in models:
#     if 'gpt' in model.id:
#         print(model.id)

