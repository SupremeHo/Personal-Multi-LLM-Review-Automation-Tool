# CLI module in charge of the Typer command line.
#
# The cli is thin: it parses arguments, delegates to the service layer (which
# owns ids, provider calls, logging, and archiving), and renders the result.
# Run from the project root: `python -m resources.cli ask "<system>" "<question>"`.

import typer

from resources.env_check import check_environment_variables
from resources.list_models import list_available_models
from resources.services import service_ask

app = typer.Typer()


def _render_log(log) -> None:
    """Print a single call's outcome (success, salvaged partial, or failure)."""
    if log.success and log.result is not None:
        typer.echo(f"\n==== {log.provider} response ====\n")
        typer.echo(f"{log.result.response_text}\n")
    elif log.result is not None:
        # Billed but a later step failed; the paid response was preserved.
        typer.echo(f"[cli.py] Partial failure (response preserved): {log.error}")
        typer.echo(f"{log.result.response_text}\n")
    else:
        typer.echo(f"[cli.py] Error Message: {log.error}")


@app.command()
def ask(
    system_prompt: str,
    user_question: str,
    provider: str = "openai",
    model: str = "gpt-4o-mini",
):
    """
    Ask a single provider/model a question; logs to JSONL + SQLite.
    """
    log = service_ask.ask(system_prompt, user_question, provider, model)
    _render_log(log)


@app.command()
def compare(
    system_prompt: str,
    user_question: str,
    target: list[str] = typer.Option(
        None,
        "--target",
        "-t",
        help="A provider:model pair to query, e.g. -t openai:gpt-4o-mini. Repeatable.",
    ),
):
    """
    Ask several providers the same question and show every answer side by side.

    Each target makes a real (paid) call, so targets must be given explicitly.
    """
    if not target:
        typer.echo(
            "[cli.py] Provide at least one --target (e.g. -t openai:gpt-4o-mini "
            "-t anthropic:claude-haiku-4-5)."
        )
        raise typer.Exit(code=1)

    targets: list[tuple[str, str]] = []
    for raw in target:
        provider_name, _, model = raw.partition(":")
        if not provider_name or not model:
            typer.echo(f"[cli.py] Invalid target '{raw}'. Use provider:model.")
            raise typer.Exit(code=1)
        targets.append((provider_name, model))

    result = service_ask.compare(system_prompt, user_question, targets)

    typer.echo(f"\n==== Comparison (group {result.group_id}) ====")
    for r in result.successes:
        typer.echo(f"\n---- {r.provider} / {r.model} ----")
        typer.echo(r.response_text)
    for f in result.failures:
        typer.echo(f"\n---- {f.provider} / {f.model} [FAILED: {f.error_type}] ----")
        typer.echo(f.message)
        if f.partial_result is not None:
            typer.echo("(partial response preserved:)")
            typer.echo(f.partial_result.response_text)


@app.command()
def check_env():
    """
    Validate .env keys (OpenAI / Anthropic / Gemini); missing keys are warnings.
    """
    check_environment_variables()


@app.command()
def list_models():
    """
    List available models across configured providers.
    """
    from resources.providers import provider_anthropic, provider_google, provider_openai

    list_available_models(
        provider_openai._default_client,
        provider_anthropic._default_client,
        provider_google._default_client,
    )


def _snippet(text: str | None, width: int = 80) -> str:
    """Collapse whitespace and truncate to a single short line for listing."""
    if not text:
        return ""
    one_line = " ".join(text.split())
    return one_line if len(one_line) <= width else one_line[: width - 3] + "..."


def _render_history_entry(log) -> None:
    """Print one past call as a compact, newest-first history line."""
    ts = log.created_at.strftime("%Y-%m-%d %H:%M:%S")
    if log.success and log.result is not None:
        cost = log.result.cost.total_usd if log.result.cost else None
        cost_str = f"${cost:.4f}" if cost is not None else "-"
        typer.echo(f"\n[{ts}] {log.provider}/{log.result.model}  OK  {cost_str}")
        typer.echo(f"  Q: {_snippet(log.user_prompt)}")
        typer.echo(f"  A: {_snippet(log.result.response_text)}")
    else:
        typer.echo(f"\n[{ts}] {log.provider}  FAILED: {log.error_type}")
        typer.echo(f"  Q: {_snippet(log.user_prompt)}")


@app.command()
def history(
    limit: int = typer.Option(
        10, "--limit", "-n", help="How many recent calls to show."
    ),
    group: str = typer.Option(
        None, "--group", "-g", help="Show only calls from this comparison group_id."
    ),
):
    """
    Show recent questions and their LLM responses from the audit log (newest first).
    """
    logs = service_ask.read_history(limit, group)
    if not logs:
        typer.echo("[cli.py] No history yet.")
        raise typer.Exit()

    header = f"History (latest {len(logs)})" if group is None else f"History for group {group}"
    typer.echo(f"\n==== {header} ====")
    for log in logs:
        _render_history_entry(log)


if __name__ == "__main__":
    app()
