# Small shared helper for the project's standard error-line format.
# Centralizes the "[module][def func] Error Message: ..." prefix that was
# otherwise hand-formatted at every error site. The caller still decides
# whether to re-raise.

from __future__ import annotations


def print_error(message: str, *, module: str, func: str | None = None) -> None:
    """
    Print one standardized error line.

    Format: "[<module>][def <func>] Error Message: <message>"
    (the "[def <func>]" part is omitted when func is None).
    """
    location = f"[{module}][def {func}]" if func else f"[{module}]"
    print(f"{location} Error Message: {message}")
