# Module for outputting the user's questions, LLM's prompts, and metadata as JSON.

import json
import openai
from openai import OpenAI
from datetime import datetime

def save_response_as_json(LLM_response):
    # Create a dictionary to store the LLM response and metadata.
    LLM_response_dict = {
        "request_id": LLM_response.get("request_id", ""),
        "created_at": LLM_response.get("created_at", ""),
        "provider": LLM_response.get("provider", ""),
        "model": LLM_response.get("model", ""),
        "system_prompt": LLM_response.get("system_prompt", ""),
        "user_prompt": LLM_response.get("user_prompt", ""),
        "assistant_response": LLM_response.get("assistant_response", ""),
        "usage": LLM_response.get("usage", {}),
        "cost": LLM_response.get("cost", {}),
        "finish_reason": LLM_response.get("finish_reason", ""),
        "success": LLM_response.get("success", False),
        "error": LLM_response.get("error", False)
    }

    # Convert the LLM response to JSON format.
    json_data = json.dumps(LLM_response_dict, indent=4)

    # Save the JSON data to a file named "LLM_response.json".
    with open("LLM_response.json", "w", encoding="utf-8") as json_file:
        json_file.write(json_data)
        
    print("\nLLM response has been saved to LLM_response.json")

