"""
Module for outputting the user's questions, LLM's prompts, and metadata as JSON.
Save the received objects such as dict or Pydantic models as JSON/JSONL files.
Only take charges of saving the JSON/JSONL using the function defined in Storage_JSON.py.
"""


import json                         # For handling JSON data.
from pathlib import Path            # For handling file paths and operations.
from pydantic import BaseModel      # For defining structured data models.


def append_jsonl(file_path: str, record: BaseModel | dict) -> None:
    """
    Append a record (dict or Pydantic model) to a JSONL file. If the file does not exist, it will be created.
    """
    path = Path(file_path)
    path.parent.mkdir(parents = True, exist_ok = True)

    # Convert the record to a JSON string.
    if isinstance(record, BaseModel):
        json_data = record.model_dump(mode = "json") 
    else:
        json_data = record

    # Append the JSON string to the file, ensuring that each record is on a new line (JSONL format).
    with path.open("a", encoding = "utf-8") as json_file:
        json_file.write(json.dumps(json_data, ensure_ascii = False, indent = 4) + "\n")

    # Print a message indicating that the LLM response has been saved, along with the file path.
    print(f"\nLLM response has been saved to {file_path}\n")

