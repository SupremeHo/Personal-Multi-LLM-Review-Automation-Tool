"""Tests for the shared error-line helper."""

from __future__ import annotations

from resources.diagnostics import print_error


def test_print_error_returns_the_message_it_printed(capsys):
    # Regression: this returned None, so `raise RuntimeError(print_error(...))`
    # - written at two call sites - built an exception whose only argument was
    # None. str(e) was then the string "None", which is what a failed run's
    # audit log recorded as its reason.
    returned = print_error("boom", module="m.py", func="f")

    assert returned == "boom"
    assert "boom" in capsys.readouterr().out


def test_print_error_return_value_excludes_the_console_prefix(capsys):
    # The [module][def func] decoration belongs on the console, not in the log:
    # LLMCallLog keeps the provider and error type in their own fields.
    returned = print_error("just the reason", module="m.py", func="f")
    printed = capsys.readouterr().out

    assert returned == "just the reason"
    assert "m.py" in printed
    assert "m.py" not in returned
