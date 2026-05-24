# CLI module
# In charge of Typer command line.

import typer
import time
from rich.progress import track # Rich 라이브러리의 track 함수를 가져옴, 진행 상황을 시각적으로 표시하는 데 사용

app = typer.Typer() # Typer 객체 생성, CLI 애플리케이션을 정의하는 데 사용

def main():
    total = 0
    for value in track(range(100), description="Processing..."):
        time.sleep(0.01)
        total += 1
    print(f"Total Processed: {total}") # main 함수 정의, 0부터 99까지의 숫자를 처리하면서 진행 상황을 표시하고, 최종적으로 처리된 총 개수를 출력하는 역할

@app.command()
def greeting(name: str):
    typer.echo(f"Hello, {name}.") # greeting 명령어 정의, name 매개변수를 받아서 "Hello, {name}." 메시지를 출력하는 역할

@app.command()
def goodbye(name: str, formal: bool = False):
    if formal:
        typer.echo(f"Goodbye, Mr. {name}. I hope you have a good day.") # formal이 True일 때, 이름 앞에 "Mr."를 붙이고, 좋은 하루 되라는 메시지를 추가
    else:
        typer.echo(f"Goodbye, {name}. See you later.") # formal이 False일 때, 이름만 출력하고, 나중에 보자는 메시지를 추가

if __name__ == "__main__":
    app() # Typer 애플리케이션 실행, 명령어를 처리하고 사용자 입력을 받아들이는 역할
