# CLI module
# In charge of Typer command line.

import typer
from openai import OpenAI
import env_check
import LLM_Client
import List_Models
import Storage_JSON

app = typer.Typer()

# Load environment variables from .env file with the check function defined in env_check.py.
env_check.check_environment_variables()

# Defining the ask command. Prompt the user for a question and output the question.
@app.command()
def ask(system_prompt: str, user_question: str):
    typer.echo(f"System prompt: {system_prompt}")
    typer.echo(f"Your question: {user_question}")
    LLM_Client.ask_llm(system_prompt, user_question)
    
@app.command()
def list_models():
    List_Models.list_available_models(OpenAI())

# Not yet implemented. This command will list available models from the OpenAI API or a predefined list.
@app.command()
def models(name: str, lastname: str = ""):
    typer.echo(f"Hello {name} {lastname}! Here are the available models.")
    # You can add code here to list available models from the OpenAI API or a predefined list.

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
