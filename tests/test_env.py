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

from resources.env import load_env
from resources.env_check import check_environment_variables

PROJECT_ROOT = Path(__file__).resolve().parent.parent
API_KEYS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY")


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
