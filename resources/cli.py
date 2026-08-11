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


def _price(log) -> str:
    """One call's cost, or why there isn't one. Never invents a zero."""
    if log.result is None:
        return "not billed" if log.salvage is None else "billed, unpriced"
    if log.result.cost is None:
        return "billed, unpriced"
    return typer.style(
        f"${log.result.cost.total_usd:.6f}",
        fg=typer.colors.YELLOW,
    )


def _render_log(log) -> None:
    """Print a single call's outcome (success, salvaged partial, or failure)."""
    provider = typer.style(log.provider, fg=typer.colors.BRIGHT_BLUE)
    model = typer.style(log.model, fg=typer.colors.MAGENTA)

    if log.success and log.result is not None:
        typer.echo(f"\n==== {provider} / {model}'s response  [{_price(log)}] ====\n")
        typer.echo(f"{log.result.response_text}\n")
    elif log.result is not None:
        # Billed but a later step failed; the paid response was preserved.
        typer.echo(
            f"[cli.py] Partial failure ({_price(log)}, response preserved): {log.error}"
        )
        typer.echo(f"{log.result.response_text}\n")
    else:
        typer.echo(f"[cli.py] Error Message: {log.error}")
        if log.salvage is not None:
            typer.echo(
                f"[cli.py] This call was billed but nothing could be read from it "
                f"(failed at {log.salvage.failed_stage}); it is in the audit log."
            )


def _render_compare_entry(log) -> None:
    """Print one target's outcome. Driven by the log, so target order is preserved."""
    label = f"{log.provider} / {log.model}"

    if log.success and log.result is not None:
        typer.echo(f"\n---- {label}  [{_price(log)}] ----")
        typer.echo(log.result.response_text)
    elif log.result is not None:
        typer.echo(f"\n---- {label}  [{_price(log)}]  [PARTIAL: {log.error_type}] ----")
        typer.echo("(billed; the answer survived but its cost did not)")
        typer.echo(log.result.response_text)
    else:
        typer.echo(f"\n---- {label}  [FAILED: {log.error_type}] ----")
        typer.echo(log.error or "")
        if log.salvage is not None:
            typer.echo(
                f"(billed, but nothing readable came back - failed at "
                f"{log.salvage.failed_stage})"
            )


def _render_cost_summary(logs) -> None:
    """Total what this command spent, and say so when the total is understated."""
    total = sum(
        log.result.cost.total_usd
        for log in logs
        if log.result is not None and log.result.cost is not None
    )
    unpriced = sum(
        1
        for log in logs
        if (log.result is not None and log.result.cost is None)
        or log.salvage is not None
    )

    line = f"\nTotal: ${total:.6f}"
    if unpriced:
        line += f"  ({unpriced} billed call(s) could not be priced - the real total is higher)"
    typer.echo(line)


@app.command()
def ask(
    system_prompt: str,
    user_question: str,
    provider: str = "openai",
    model: str = "gpt-4o-mini",
):
    """
    Ask a single provider/model a question; logs to JSONL + SQLite.

    Defaults to OpenAI gpt-4o-mini if no provider/model is specified. The system prompt is optional but recommended.
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
    Ask several providers the same question and print every answer in target order.

    Each target makes a real (paid) call, so targets must be given explicitly, and
    the same provider:model may not be repeated.
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

    # Rejected targets (e.g. the same provider:model twice) are refused before any
    # paid call, so this is a usage error to report, not a crash to surface.
    try:
        result = service_ask.compare(system_prompt, user_question, targets)
    except ValueError as e:
        typer.echo(f"[cli.py] {e}")
        raise typer.Exit(code=1) from e

    typer.echo(f"\n==== Comparison (group {result.group_id}) ====")
    typer.echo(
        f"{len(result.usable_responses)}/{len(result.logs)} usable "
        f"(quorum {service_ask.QUORUM})  |  collection: {result.collection_status}"
        f"  |  audit: {result.audit_status}"
    )
    if result.collection_status == "insufficient":
        typer.secho(
            f"Not a comparison: fewer than {service_ask.QUORUM} usable answers came "
            "back. Read what follows as single answers, not as cross-checked ones.",
            fg=typer.colors.YELLOW,
            bold=True,
        )

    # Render from result.logs, which is in target order. Printing successes first
    # and failures after would reorder the answers behind the user's back.
    for log in result.logs:
        _render_compare_entry(log)

    _render_cost_summary(result.logs)

    # The answers above survived the storage fault, but the audit trail did not -
    # say so here, where it cannot scroll past unnoticed during the calls.
    if result.persist_errors:
        typer.secho(
            "\n---- WARNING: these answers were not fully archived ----",
            fg=typer.colors.YELLOW,
            bold=True,
        )
        for p in result.persist_errors:
            stored = (
                f"; stored in {', '.join(p.written_sinks)}" if p.written_sinks else ""
            )
            typer.echo(f"run {p.run_id}: {p.sink} failed ({p.error_type}{stored})")


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


def _snippet(text: str | None, width: int = 120) -> str:
    """Collapse whitespace and truncate to a single short line for listing."""
    if not text:
        return ""
    one_line = " ".join(text.split())
    return one_line if len(one_line) <= width else one_line[: width - 3] + "..."


def _render_history_entry(log) -> None:
    """Print one past call as a compact, newest-first history line."""
    # Logs are stamped in UTC; show them in local time. astimezone() also does the
    # right thing for older naive rows, which were written in local time already.
    ts = typer.style(
        log.created_at.astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        fg=typer.colors.YELLOW,
    )

    styled_providers_name = typer.style(
        log.provider,
        fg=typer.colors.BRIGHT_BLUE,
    )
    styled_models_name = typer.style(
        log.model or (log.result.model if log.result else None) or "?",
        fg=typer.colors.MAGENTA,
    )

    ok = typer.style("OK", fg=typer.colors.GREEN, bold=True)
    fail = typer.style("FAILED", fg=typer.colors.RED, bold=True)
    q = typer.style(">> Q", fg=typer.colors.CYAN, bold=True)
    a = typer.style(">> A", fg=typer.colors.CYAN, bold=True)
    e = typer.style(">> Error", fg=typer.colors.RED, bold=True)

    if log.success and log.result is not None:
        typer.echo(
            f"\n[{ts}] {styled_providers_name}/{styled_models_name}  {ok}  {_price(log)}"
        )
        typer.echo(f"{q}: {_snippet(log.user_prompt)}")
        typer.echo(f"{a}: {_snippet(log.result.response_text)}")
    else:
        # log.model (the requested one) is the only model a failed run knows.
        typer.echo(
            f"\n[{ts}] {styled_providers_name}/{styled_models_name}  {fail}  {_price(log)}"
        )
        typer.echo(f"{q}: {_snippet(log.user_prompt)}")
        typer.echo(f"{e}: {_snippet(log.error_type)}")


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
        typer.secho(
            "\n>>> [cli.py] No history yet.",
            fg=typer.colors.RED,
        )
        raise typer.Exit()

    header = (
        f"History (latest {len(logs)} calls)"
        if group is None
        else f"History for group {group}"
    )

    typer.secho(
        f"\n==== {header} ====",
        fg=typer.colors.BRIGHT_CYAN,
    )

    for log in logs:
        _render_history_entry(log)


if __name__ == "__main__":
    app()
