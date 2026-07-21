# Small shared helper for the project's standard error-line format.
# Centralizes the "[module][def func] Error Message: ..." prefix that was
# otherwise hand-formatted at every error site. The caller still decides
# whether to re-raise.

from __future__ import annotations

from rich.console import Console
from rich.text import Text

console = Console()


def print_error(message: str, *, module: str, func: str | None = None) -> None:
    """
    Print one standardized error line.

    Format: [module] [def func] Error Message: 'message_about_error'

    (the "[def func]" part is omitted when func is None).
    """
    location = f">> [{module}] [def {func}]" if func else f">> [{module}]"

    location_text = Text(location, style="red")
    message_text = Text(message, style="magenta")

    text = Text.assemble(location_text, " Error Message: ", message_text)

    console.print(text)


def test_print_warning():
    print_error(
        "This is a test error message.", module="diagnostics.py", func="print_error"
    )


if __name__ == "__main__":
    test_print_warning()
