# Module for outputting the user's questions, LLM's prompts, and metadata as JSON.

import json

def save_response_as_json(LLM_response_dict: dict):

    # Convert the LLM response to JSON format.
    json_data = json.dumps(LLM_response_dict, indent=4)

    # Save the JSON data to a file named "LLM_response.json".
    with open("LLM_response.json", "w", encoding="utf-8") as json_file:
        json_file.write(json_data)
        
    print("\nLLM response has been saved to LLM_response.json")

