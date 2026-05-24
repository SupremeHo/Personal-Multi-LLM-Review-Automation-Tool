# CLI module
# In charge of Typer command line.

import typer

app = typer.Typer() # Typer 객체 생성, CLI 애플리케이션을 정의하는 데 사용

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
