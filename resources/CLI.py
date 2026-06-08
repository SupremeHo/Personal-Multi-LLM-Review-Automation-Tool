"""CLI module in charge of Typer command line."""

import time  # noqa: I001
from datetime import datetime, timezone, timedelta
from uuid import uuid4

# from rich.progress import track
import typer

import env_check
import llm_client
from list_models import list_available_models
from llm_client import ask_gpt
from schemas import LLMCallLog
from storage_json import append_jsonl
from storage_sqlite import import_jsonl_to_sqlite

DB_PATH = "D:/My Documents/Dev_Python/Personal Multi-LLM Review Automation Tool/resources/db/sqlite.db"


app = typer.Typer()


# Load environment variables from .env file with the checking function defined in env_check.py.
@app.command()
def check_env():
    env_check.check_environment_variables()


# Defining the ask command. Prompt the user for a question and output the question.
@app.command()
def ask(system_prompt: str, user_question: str):
    run_id = str(uuid4())  # Create a unique non-overlapping unique ID.
    created_at = datetime.now(timezone(timedelta(hours=9)))  # Set timezone to KST (UTC+9, Seoul).
    start_time = time.time()  # Measure the time which API call starts.

    try:
        result = ask_gpt(system_prompt, user_question)

        end_time = time.time()  # Measure the time which API call ends.

        log = LLMCallLog(
            run_id=run_id,
            created_at=created_at,
            system_prompt=system_prompt,
            user_prompt=user_question,
            success=True,
            error=None,
            elapsed_sec=round(
                (end_time - start_time), 3
            ),  # Calculate the elapsed time (seconds) and round the value to third decimal place.
            result=result,
        )

        typer.echo("\n==== OpenAI GPT's Response ====\n")
        typer.echo(f"{result.response_text}\n")

    except Exception as e:
        end_time = time.time()  # Measure the time which API call ends.

        log = LLMCallLog(
            run_id=run_id,
            created_at=created_at,
            user_prompt=user_question,
            success=False,
            error=str(e),
            elapsed_sec=round(
                (end_time - start_time), 3
            ),  # Calculate the elapsed time (seconds) and round the value to third decimal place.
            result=None,
        )

        typer.echo(f"An error occurred: {e}")

    # Attatch the created time after the log's name.
    gpt_response_filename = f"gpt_response_log_{created_at.strftime('%Y%m%d_%H%M%S')}.jsonl"

    # Save the log as .jsonl file in specified path.
    jsonl_path = f"resources/logs/OpenAI/{gpt_response_filename}"
    append_jsonl(jsonl_path, log)

    import_jsonl_to_sqlite(jsonl_path, DB_PATH)


# Defining the list-models command. This will list available models from the OpenAI API.
@app.command()
def list_models():
    list_available_models(llm_client.client)


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
