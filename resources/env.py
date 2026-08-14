# Loads the .env fallback, once, before anything reads os.environ.
#
# Keys are read from the OS environment first; a .env file in the project root is
# an optional fallback for machines where they are not set. Order matters here:
# every provider_*.py builds its SDK client at import time from os.environ, so a
# .env loaded any later is a .env that was never seen. That is why load_env() is
# called from resources/__init__.py, which Python runs before any resources.*
# submodule - and not from a CLI command body, where the providers are already
# imported and their clients already decided.

from __future__ import annotations

from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # .env is the fallback path; OS variables still work.
    load_dotenv = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOTENV_PATH = PROJECT_ROOT / ".env"


def load_env(dotenv_path: Path | None = None) -> None:
    """
    Load the .env fallback into os.environ. Never overrides an OS variable.

    The path is stated rather than discovered: python-dotenv's default search
    walks up from whichever file calls it, so what gets loaded would depend on
    the working directory and on the caller. Tests pass their own path.

    A missing file is a no-op - running on OS environment variables alone is a
    supported setup, not an error.
    """
    if load_dotenv is None:
        return

    # override=False (the default, stated here because the precedence is a
    # promise the README makes): a variable already in the OS environment wins.
    load_dotenv(dotenv_path or DOTENV_PATH, override=False)
