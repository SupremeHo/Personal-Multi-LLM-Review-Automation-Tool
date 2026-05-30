# CLI module
# In charge of Typer command line.

import time
import typer
from rich.progress import track
from openai import OpenAI
import env_check
import llm_client
import list_models

app = typer.Typer()

# Load environment variables from .env file with the checking function defined in env_check.py.
@app.command()
def check_env():
    env_check.check_environment_variables()

# Defining the ask command. Prompt the user for a question and output the question.
@app.command()
def ask(system_prompt: str, user_question: str):
    typer.echo(f"System prompt: {system_prompt}")
    typer.echo(f"Your question: {user_question}")

    # Simulate a loading process while the LLM generates a response (this is just for demonstration and can be removed or replaced with actual progress tracking).
    # for step in track(range(100), description="\nResponse generating..."):
    #     time.sleep(1)
    # print("Response generated.\n")

    llm_client.ask_llm(system_prompt, user_question)

# Defining the list-models command. This will list available models from the OpenAI API.
@app.command()
def list_models():
    list_models.list_available_models(OpenAI())

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
