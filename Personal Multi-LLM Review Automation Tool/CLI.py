# CLI module
# In charge of Typer command line.

import typer

app = typer.Typer()

@app.command()
def hello(name: str):
    """이름을 입력 받아 인사를 출력합니다."""
    typer.echo(f"Hello {name}!")

if __name__ == "__main__":
    app()
