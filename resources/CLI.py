# CLI module
# In charge of Typer command line.

from datetime import datetime, timezone
from uuid import uuid4
import time

import typer
from rich.progress import track

import env_check
import llm_client
from list_models import list_available_models
from llm_client import ask_gpt
from storage_json import append_jsonl
from schemas import LLMCallLog


app = typer.Typer()


# Load environment variables from .env file with the checking function defined in env_check.py.
@app.command()
def check_env():
    env_check.check_environment_variables()

# Defining the ask command. Prompt the user for a question and output the question.
@app.command()
def ask(system_prompt: str, user_question: str):
    run_id = str(uuid4())
    created_at = datetime.now(timezone.utc)

    try:
        result = ask_gpt(system_prompt, user_question)

        log = LLMCallLog(
            run_id = run_id,
            created_at = created_at,
            user_prompt = user_question,
            result = result,
            success = True,
            error = None,
            elapsed_ms = None
        )

        typer.echo(f"OpenAI GPT's Response:\n{result.response_text}\n")

    except Exception as e:
        log = LLMCallLog(
            run_id = run_id,
            created_at = created_at,
            user_prompt = user_question,
            result = None,
            success = False,
            error = str(e),
            elapsed_ms = None
        )

        typer.echo(f"An error occurred: {e}")
    
    append_jsonl("logs/GPT_call_logs.jsonl", log)


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
