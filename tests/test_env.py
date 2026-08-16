# Tests for the .env fallback and, above all, for WHEN it is loaded.
#
# The bug these guard against: load_dotenv() used to run inside the `check-env`
# command body, long after resources.providers.* had been imported and had built
# their SDK clients from os.environ. A machine configured the way the README
# describes - .env only, no OS variables - therefore ran `ask`/`compare` with
# every client set to None, while `check-env` cheerfully reported all keys set.

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from resources.env import load_env
from resources.env_check import (
    check_environment_variables,
    missing_environment_variables,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Every variable that can configure a provider, so "a fresh machine" really is one:
# leaving ANTHROPIC_AUTH_TOKEN behind would let a developer's own environment
# satisfy Anthropic and quietly pass the missing-key cases.
API_KEYS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "GEMINI_API_KEY",
)


def _clear_api_keys(monkeypatch):
    """Simulate a fresh machine: no API keys in the OS environment at all."""
    for name in API_KEYS:
        monkeypatch.delenv(name, raising=False)


def test_load_env_reads_dotenv_when_os_environment_is_empty(tmp_path, monkeypatch):
    """The README setup: .env only, nothing exported in the shell."""
    _clear_api_keys(monkeypatch)
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "OPENAI_API_KEY=sk-openai-from-dotenv\n"
        "ANTHROPIC_API_KEY=sk-anthropic-from-dotenv\n"
        "GEMINI_API_KEY=gemini-from-dotenv\n",
        encoding="utf-8",
    )

    load_env(dotenv)

    assert os.getenv("OPENAI_API_KEY") == "sk-openai-from-dotenv"
    assert os.getenv("ANTHROPIC_API_KEY") == "sk-anthropic-from-dotenv"
    assert os.getenv("GEMINI_API_KEY") == "gemini-from-dotenv"


def test_os_environment_wins_over_dotenv(tmp_path, monkeypatch):
    """Precedence is a promise the README makes, so it is pinned here."""
    _clear_api_keys(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-os")
    dotenv = tmp_path / ".env"
    dotenv.write_text("OPENAI_API_KEY=sk-from-dotenv\n", encoding="utf-8")

    load_env(dotenv)

    assert os.getenv("OPENAI_API_KEY") == "sk-from-os"


def test_missing_dotenv_file_is_a_no_op(tmp_path, monkeypatch):
    """Running on OS variables alone is a supported setup, not an error."""
    _clear_api_keys(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-os")

    load_env(tmp_path / "there-is-no-such-file.env")

    assert os.getenv("OPENAI_API_KEY") == "sk-from-os"


def test_env_is_loaded_before_any_provider_module_is_imported():
    """
    The ordering invariant itself.

    sys.modules is insertion-ordered and a module is registered when its import
    begins, so comparing positions shows whether resources.env ran before the
    provider modules built their clients. Run in a subprocess because this test
    session has already imported everything.
    """
    script = (
        "import sys\n"
        "import resources.cli\n"
        "mods = [m for m in sys.modules if m.startswith('resources')]\n"
        "providers = [m for m in mods if m.startswith('resources.providers')]\n"
        "assert 'resources.env' in mods, 'package init no longer loads the .env fallback'\n"
        "assert providers, 'expected the CLI to import the provider modules'\n"
        "first_provider = min(mods.index(p) for p in providers)\n"
        "assert mods.index('resources.env') < first_provider, (\n"
        "    'a provider module was imported before the .env fallback was loaded'\n"
        ")\n"
        "print('ok')\n"
    )

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "ok"


def test_missing_environment_variables_reads_os_environ(monkeypatch):
    """The check itself, without the interactive prompt wrapped around it."""
    _clear_api_keys(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-anthropic")

    missing = missing_environment_variables()

    assert missing["OpenAI"] == ["OPENAI_API_KEY"]
    assert missing["Anthropic"] == []
    assert missing["Google"] == ["GEMINI_API_KEY"]


def test_anthropic_is_configured_by_either_of_its_two_variables(monkeypatch):
    # The provider builds its client from ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN
    # (see provider_anthropic._build_default_client), so check-env used to warn that
    # Anthropic "stays disabled" on a token-only setup where it in fact worked.
    _clear_api_keys(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "token-from-env")

    assert missing_environment_variables()["Anthropic"] == []


def test_check_env_offers_the_anthropic_variables_as_a_choice(monkeypatch, capsys):
    # Both names have to appear when neither is set - naming only the api key hides
    # the alternative - but joined so that setting one is clearly enough.
    _clear_api_keys(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")

    check_environment_variables()

    assert "ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN" in capsys.readouterr().err


def test_missing_environment_variables_treats_a_blank_value_as_missing(monkeypatch):
    """A .env copied from .env.example supplies "" rather than nothing at all."""
    _clear_api_keys(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "")

    assert missing_environment_variables()["OpenAI"] == ["OPENAI_API_KEY"]


def test_check_env_reports_only_the_missing_keys(monkeypatch, capsys):
    """check-env reads os.environ, which is now the same view the providers got."""
    _clear_api_keys(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-anthropic")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini")
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")

    check_environment_variables()

    captured = capsys.readouterr()
    assert "OPENAI_API_KEY" in captured.err
    assert "ANTHROPIC_API_KEY" not in captured.err
    assert "GEMINI_API_KEY" not in captured.err


def test_check_env_points_at_both_key_sources(monkeypatch, capsys):
    # The advice used to name .env alone, which is the source that does NOT
    # decide this: an OS variable overrides it, and the README recommends it.
    _clear_api_keys(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")

    check_environment_variables()

    err = capsys.readouterr().err
    assert "OS environment variable" in err
    assert ".env" in err


def test_check_env_exits_cleanly_on_interrupt(monkeypatch):
    # Ctrl+C at the prompt used to end the command on a traceback, unlike the
    # same prompt in list_models.py.
    _clear_api_keys(monkeypatch)

    def interrupt(_prompt):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", interrupt)

    with pytest.raises(SystemExit) as excinfo:
        check_environment_variables()

    assert "interrupted by user" in str(excinfo.value)


def test_check_env_never_fails_the_command_when_keys_are_missing(monkeypatch):
    # Missing keys are warnings by design: a missing key disables one provider,
    # not the tool, so a single-provider setup must not read as a failed command.
    _clear_api_keys(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")

    assert check_environment_variables() is None  # no SystemExit, no raise
