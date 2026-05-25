# CLI module
# In charge of Typer command line.

import typer
#import time
#from rich.progress import Progress, SpinnerColumn, TextColumn

# def main():
#     with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
#         task = progress.add_task("Processing...", total=None)
#         # 여기에 실제 작업을 수행하는 코드를 추가할 수 있습니다.
#         # 예: time.sleep(5)  # 작업 시뮬레이션
#         progress.update(task, description="Done!")

# Typer 객체 생성, CLI 애플리케이션을 정의하는 데 사용
app = typer.Typer()

# greeting 명령어 정의, 이름과 성을 입력받아 인사 메시지를 출력
@app.command()
def greeting(name: str, lastname: str = ""):
    typer.echo(f"Hello, {name} {lastname}.")

# goodbye 명령어 정의, 이름과 성을 입력받아 작별 인사 메시지를 출력, formal 옵션에 따라 메시지 형식이 달라짐
@app.command()
def goodbye(name: str, lastname: str = "", formal: bool = False):
    if formal:
        typer.echo(f"Goodbye, Mr. {name} {lastname}. I hope you have a good day.")
    else:
        typer.echo(f"Goodbye, {name} {lastname}. See you later.")

# 사용자로부터 질문을 입력받아 출력하는 명령어
@app.command()
def ask():
    question = typer.prompt("What is your question?")
    typer.echo(f"You asked: {question}")

# Typer 애플리케이션 실행, 명령어를 처리하고 사용자 입력을 받아들이는 역할
if __name__ == "__main__":
    app()
