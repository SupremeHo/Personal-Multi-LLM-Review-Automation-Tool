# CLI module
# In charge of Typer command line.

import typer

#app = typer.Typer()

friend = typer.style("SupremeHo", bold=True)

def main():
    typer.echo(f"Hello, {friend}.")

# 해당 Python 모듈이 메인으로 실행, 
# Python으로 CLI 제작 시 대부분 필요한 if 조건 구문
if __name__ == "__main__":
    # run() 메서드를 호출할 때 실행시킬 함수 전달
    typer.run(main)
    #app()
