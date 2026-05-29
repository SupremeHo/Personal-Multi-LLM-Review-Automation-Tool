# CLI module
# In charge of Typer command line.

import typer
from openai import OpenAI
from env_check import check_environment_variables
import LLM_Client
import List_Models

app = typer.Typer()

# Load environment variables from .env file with the checking function defined in env_check.py.
@app.command()
def check_env():
    check_environment_variables()

# Defining the ask command. Prompt the user for a question and output the question.
@app.command()
def ask(system_prompt: str, user_question: str):
    typer.echo(f"System prompt: {system_prompt}")
    typer.echo(f"Your question: {user_question}")
    LLM_Client.ask_llm(system_prompt, user_question)
    
# Defining the list-models command. This will list available models from the OpenAI API.
@app.command()
def list_models():
    List_Models.list_available_models(OpenAI())

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
