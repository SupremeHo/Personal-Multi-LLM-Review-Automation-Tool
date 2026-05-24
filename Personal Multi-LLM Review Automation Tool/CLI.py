# CLI module
# In charge of Typer command line.

import typer
import time
from rich.progress import Progress, SpinnerColumn, TextColumn

# def main():
#     with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
#         task = progress.add_task("Processing...", total=None)
#         # 여기에 실제 작업을 수행하는 코드를 추가할 수 있습니다.
#         # 예: time.sleep(5)  # 작업 시뮬레이션
#         progress.update(task, description="Done!")

app = typer.Typer() # Typer 객체 생성, CLI 애플리케이션을 정의하는 데 사용

# Typer 명령어 정의, name 매개변수를 받아서 "Hello, {name}." 메시지를 출력하는 역할
@app.command()
def greeting(name: str):
    typer.echo(f"Hello, {name}.")

# formal이 True일 때, 이름 앞에 "Mr."를 붙이고, 좋은 하루 되라는 메시지를 추가
# formal이 False일 때, 이름만 출력하고, 나중에 보자는 메시지를 추가
@app.command()
def goodbye(name: str, formal: bool = False):
    if formal:
        typer.echo(f"Goodbye, Mr. {name}. I hope you have a good day.")
    else:
        typer.echo(f"Goodbye, {name}. See you later.")

# Typer 애플리케이션 실행, 명령어를 처리하고 사용자 입력을 받아들이는 역할
if __name__ == "__main__":
    app()
