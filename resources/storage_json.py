# Module for outputting the user's questions, LLM's prompts, and metadata as JSON.
# Save the received objects such as dict or Pydantic models as JSON/JSONL files.
# Only take charges of saving the JSON/JSONL using the function defined in Storage_JSON.py.

import json  # noqa: I001
from pathlib import Path
from pydantic import BaseModel

from resources.diagnostics import print_error


def append_jsonl(file_path: str, record: BaseModel | dict) -> None:
    """
    Append a record (dict or Pydantic model) to a JSONL file.
    If the file does not exist, it will be created.
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
        print_error(
            f"Permission denied → cannot write to {file_path}",
            module="storage_json.py",
            func="append_jsonl",
        )
        raise

    except OSError as e:
        print_error(
            f"Failed to write to {file_path}: {e}",
            module="storage_json.py",
            func="append_jsonl",
        )
        raise

    # Print a message indicating that the LLM response has been saved, along with the file path.
    print(f"\nLLM response has been saved to {file_path}")


def load_jsonl_file(file_path: str | Path):
    """
    Load the JSONL file in logs' path.
    """
    path = Path(file_path)

    try:
        with path.open("r", encoding="utf-8") as file:
            json_data = [json.loads(line) for line in file if line.strip()]

    except FileNotFoundError:
        print_error(
            f"File not found - {file_path}",
            module="storage_json.py",
            func="load_jsonl_file",
        )
        raise

    except json.JSONDecodeError as e:
        print_error(
            f"Invalid JSON on line - {e}",
            module="storage_json.py",
            func="load_jsonl_file",
        )
        raise

    return json_data
