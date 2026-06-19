# Module for outputting the user's questions, LLM's prompts, and metadata as JSON.
# Save the received objects such as dict or Pydantic models as JSON/JSONL files.
# Only take charges of saving the JSON/JSONL using the function defined in Storage_JSON.py.

import json  # noqa: I001
from pathlib import Path
from pydantic import BaseModel


def append_jsonl(file_path: str, record: BaseModel | dict) -> None:
    """
    Append a record (dict or Pydantic model) to a JSONL file. If the file does not exist, it will be created.
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert the record to a JSON string.
    if isinstance(record, BaseModel):
        json_data = record.model_dump(mode="json")
    else:
        json_data = record

    # Append the JSON string to the file, ensuring that each record is on a new line (JSONL format).
    try:
        with path.open("a", encoding="utf-8") as json_file:
            json_file.write(json.dumps(json_data, ensure_ascii=False) + "\n")

    except PermissionError:
        print(f"[storage_json.py] Error Message: Permission denied → cannot write to {file_path}")
        raise

    except OSError as e:
        print(f"[storage_json.py] Error Message: Failed to write to {file_path}: {e}")
        raise

    # Print a message indicating that the LLM response has been saved, along with the file path.
    print(f"\nLLM response has been saved to <{file_path}>\n")


def load_jsonl_file(file_path: Path):
    """
    Load the JSONL file in logs' path.
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with path.open("r", encoding="utf-8") as file:
            json_data = json.load(file)

    except FileNotFoundError:
        print(f"[storage_json.py] Error Message: File not found - {file_path}")
        raise

    except json.JSONDecodeError as e:
        print(f"[storage_json.py] Error Message: Invalid JSON on line - {e}")
        raise

    return json_data


def save_jsonl():
    print("temp")


# def main():
#     json_data = load_jsonl_file("resources/logs/OpenAI/gpt_response_log_20260618_161842.jsonl")
#     print(json_data)


# if __name__ == "__main__":
#     main()
