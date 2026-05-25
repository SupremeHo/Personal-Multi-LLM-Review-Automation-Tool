# CLI module
# In charge of Typer command line.

import typer
#import time
#from rich.progress import Progress, SpinnerColumn, TextColumn

# def main():
#     with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
#         task = progress.add_task("Processing...", total=None)
#         # Simulate some work being done, such as calling an LLM or processing data. You can replace this with actual logic for your application.
#         # ex) time.sleep(5)  # Simulating a delay for demonstration purposes
#         progress.update(task, description="Done!")

# Creating a Typer object, using to define a CLI application with multiple commands and options. Typer is a library for building command-line interfaces in Python, and it provides an easy way to create user-friendly CLI applications.
app = typer.Typer()

# Defining the greeting command. Enter the first and last name to output a greeting message. The last name is optional, and if not provided, it will default to an empty string.
@app.command()
def greeting(name: str, lastname: str = ""):
    typer.echo(f"Hello, {name} {lastname}.")

# Defining the goodbye command. Enter the first and last name to output goodbye message. The last name is optional, and if not provided, it will default to an empty string. The formal option is a boolean flag.
@app.command()
def goodbye(name: str, lastname: str = "", formal: bool = False):
    if formal:
        typer.echo(f"Goodbye, Mr. {name} {lastname}. I hope you have a good day.")
    else:
        typer.echo(f"Goodbye, {name} {lastname}. See you later.")

# Defining the ask command. Prompt the user for a question and output the question.
@app.command()
def ask():
    question = typer.prompt("What is your question?")
    typer.echo(f"You asked: {question}")

# Run the Typer application, handling commands and accepting user input.
if __name__ == "__main__":
    app()
