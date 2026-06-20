# CLI module in charge of Typer command line.

import time  # noqa: I001
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import typer
import llm_client

from env_check import check_environment_variables
from list_models import list_available_models
from llm_client import ask_openai
from schemas import LLMCallLog
from storage_json import append_jsonl
from storage_sqlite import import_jsonl_to_sqlite

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "db" / "llm_responses.db"

app = typer.Typer()


# Defining the ask command. Prompt the user for a question and output the question.
@app.command()
def ask(system_prompt: str, user_question: str):
    try:
        run_id = str(uuid4())  # Create a unique non-overlapping unique ID.
        response_id = str(uuid4())  # Create a UUID for identification of individual LLM response units.
        created_at = datetime.now()  # The time when the LLMs' responses were made.

        start_time = time.time()  # Measure the time which API call starts.
        result_openai = ask_openai(system_prompt, user_question, response_id)
        end_time = time.time()  # Measure the time which API call ends.

        typer.echo("\n==== OpenAI GPT's Response ====\n")
        typer.echo(f"{result_openai.response_text}\n")

        log_data = {
            "run_id": run_id,
            "created_at": created_at,
            "system_prompt": system_prompt,
            "user_prompt": user_question,
            "success": True,
            "error": None,
            "elapsed_sec": round((end_time - start_time), 3),
            "result": None,
        }

        log_data["result"] = result_openai

    except Exception as e:
        log_data["success"] = False
        log_data["error"] = str(e)
        typer.echo(f"[cli.py] Error Message: {e}")

    log = LLMCallLog(**log_data)

    # Attatch the created time after the log's name.
    filename_response_openai = f"gpt_response_log_{created_at.strftime('%Y%m%d_%H%M%S')}.jsonl"

    # Specify a location to save the log as .jsonl file.
    jsonl_path_openai = BASE_DIR / "logs" / "OpenAI" / filename_response_openai

    # Save the .jsonl file and store the log in SQLite DB.
    append_jsonl(jsonl_path_openai, log)
    import_jsonl_to_sqlite(str(jsonl_path_openai), str(DB_PATH))


# Load environment variables from .env file with the checking function defined in env_check.py.
@app.command()
def check_env():
    check_environment_variables()


# Defining the list-models command. This will list available models from the OpenAI API.
@app.command()
def list_models():
    list_available_models(llm_client.client_openai, llm_client.client_anthropic, llm_client.client_google)


# Not yet implemented. This command will show the user's history of questions and LLM responses.
@app.command()
def history(name: str, lastname: str = "", formal: bool = False):
    if formal:
        typer.echo(f"Hello, {name} {lastname}! Here is your history.")
    else:
        typer.echo(f"Hi {name}! Here is your history.")


# Run the Typer application, handling commands and accepting user input.
if __name__ == "__main__":
    app()
