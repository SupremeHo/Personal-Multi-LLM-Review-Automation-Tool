# Tests for the free `list-models` command (no API calls; clients are fakes).

from __future__ import annotations

from openai import OpenAIError

from resources import list_models
from resources.list_models import list_available_models


class _Model:
    """A model row shaped like whichever SDK is being faked (.id or .name)."""

    def __init__(self, **fields):
        self.__dict__.update(fields)


class _Models:
    def __init__(self, items, error):
        self._items = items
        self._error = error

    def list(self):
        if self._error is not None:
            raise self._error
        return self._items


class _Client:
    def __init__(self, items=(), error=None):
        self.models = _Models(items, error)


def _answer(monkeypatch, reply):
    """Drive the command's interactive prompt."""
    monkeypatch.setattr(list_models.console, "input", lambda *_a, **_kw: reply)


def _output(capsys):
    """Captured stdout with wrapping collapsed, so asserts survive any width."""
    return " ".join(capsys.readouterr().out.split())


def test_one_failing_provider_does_not_abort_the_listing(monkeypatch, capsys):
    # Regression: _list_models re-raised after printing, so answering 'Yes' with
    # one bad key abandoned every provider after it - and ended the CLI on a
    # traceback rather than the friendly message the other branches print.
    _answer(monkeypatch, "yes")

    list_available_models(
        _Client(error=OpenAIError("invalid api key")),
        _Client([_Model(id="claude-haiku-4-5")]),
        _Client([_Model(name="models/gemini-2.5-flash")]),
    )

    out = _output(capsys)
    assert "Failed to list OpenAI's models" in out
    assert "claude-haiku-4-5" in out  # listed despite the earlier failure
    assert "gemini-2.5-flash" in out


def test_unavailable_client_is_reported_without_raising(monkeypatch, capsys):
    # The other half of the contract: a provider whose key is missing has a None
    # client, which must read as a plain message, not an error.
    _answer(monkeypatch, "anthropic")

    list_available_models(_Client(), None, _Client())

    assert "Anthropic client is unavailable" in _output(capsys)
