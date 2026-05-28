# CLI module
# In charge of Typer command line.

import typer

app = typer.Typer()

# Defining the ask command. Prompt the user for a question and output the question.
@app.command()
def ask():
    question = typer.prompt("What is your question?")
    typer.echo(f"You asked: {question}")


@app.command()
def models(name: str, lastname: str = ""):
    typer.echo(f"Hello {name} {lastname}! Here are the available models.")
    # You can add code here to list available models from the OpenAI API or a predefined list.

@app.command()
def history(name: str, lastname: str = "", formal: bool = False):
    if formal:
        typer.echo(f"Hello, {name} {lastname}! Here is your history.")
    else:
        typer.echo(f"Hi {name}! Here is your history.")

# Run the Typer application, handling commands and accepting user input.
if __name__ == "__main__":
    app()
