# Small shared helper for the project's standard error-line format.
# Centralizes the "[module][def func] Error Message: ..." prefix that was
# otherwise hand-formatted at every error site. The caller still decides
# whether to re-raise.

from __future__ import annotations

from rich.console import Console
from rich.text import Text

console = Console()


def print_error(message: str, *, module: str, func: str | None = None) -> str:
    """
    Print one standardized error line and return the message unchanged.

    Format: [module] [def func] Error Message: 'message_about_error'

    (the "[def func]" part is omitted when func is None).

    The message comes back so a caller can report and raise in one step -
    `raise RuntimeError(print_error(...))`. Two call sites (runner.run_chat's
    unavailable-client guard, registry.get_provider) were already written that
    way while this returned None, so they raised an exception whose only
    argument was None: the reason reached the console but the audit log stored
    the string "None" where it belonged, breaking a failed run's only record of
    why it failed.

    The location prefix is deliberately not part of the return value. It is a
    console convention, and LLMCallLog already keeps the provider and the error
    type in their own fields.
    """
    location = f">> [{module}] [def {func}]" if func else f">> [{module}]"

    location_text = Text(location, style="red")
    message_text = Text(message, style="magenta")

    text = Text.assemble(location_text, " Error Message: ", message_text)

    console.print(text)
    return message


def test_print_warning():
    print_error(
        "This is a test error message.", module="diagnostics.py", func="print_error"
    )


if __name__ == "__main__":
    test_print_warning()
