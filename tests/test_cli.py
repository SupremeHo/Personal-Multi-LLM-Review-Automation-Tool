# CLI rendering tests (no paid calls; providers and storage are redirected).

from __future__ import annotations

import inspect

import pytest
from typer.testing import CliRunner

from resources import cli
from resources.count_cost import preflight_pricing
from resources.providers import provider_openai, registry
from resources.services import service_ask as svc
from tests.fakes import (
    FailProvider,
    GoodProvider,
    PaidFailProvider,
    TruncatedProvider,
)

runner = CliRunner()


@pytest.fixture
def cli_env(monkeypatch, tmp_path, temp_db):
    """Fake providers plus storage pointed at a temp dir, never the real archive."""
    monkeypatch.setattr(
        registry,
        "PROVIDERS",
        {
            "good": GoodProvider(),
            "fail": FailProvider(),
            "paidfail": PaidFailProvider(),
            "truncated": TruncatedProvider(),
        },
    )
    monkeypatch.setattr(svc, "BASE_DIR", tmp_path)
    monkeypatch.setattr(svc, "DB_PATH", temp_db)


def _headers(output: str) -> list[str]:
    return [line for line in output.splitlines() if line.startswith("---- ")]


def test_the_default_ask_target_is_priced():
    # `ask` is the one command that can run with no model argument, so its default
    # has to survive preflight_pricing - an unpriced default means the tool's
    # simplest invocation fails before it ever reaches the API. Nothing pinned this
    # while the default was gpt-4o-mini, so moving it to gpt-5.6-luna was untested.
    defaults = {
        p.name: p.default for p in inspect.signature(cli.ask).parameters.values()
    }

    assert defaults["provider"] == "openai"
    preflight_pricing(provider_openai.PRICE_PATH_OPENAI, defaults["model"])


def test_compare_renders_answers_in_target_order(cli_env):
    # Regression: successes were printed first and failures after, so a
    # success-failure-success run came out as success-success-failure.
    result = runner.invoke(
        cli.app,
        ["compare", "s", "q", "-t", "good:m1", "-t", "fail:m2", "-t", "good:m3"],
    )

    assert result.exit_code == 0
    headers = _headers(result.stdout)
    assert "good / m1" in headers[0]
    assert "fail / m2" in headers[1]
    assert "good / m3" in headers[2]


def test_compare_shows_spend_and_admits_when_it_is_understated(cli_env):
    # Three paid calls used to print no cost at all. The uncosted one must be
    # flagged rather than quietly counted as zero.
    result = runner.invoke(
        cli.app, ["compare", "s", "q", "-t", "good:m1", "-t", "paidfail:m2"]
    )

    assert result.exit_code == 0
    assert "$0.000300" in result.stdout  # only the priced call is summed
    assert "could not be priced" in result.stdout
    assert "the real total is higher" in result.stdout


def test_compare_marks_a_truncated_answer_so_the_usable_count_makes_sense(cli_env):
    # The answer prints in full but does not count toward the quorum. Without the
    # tag the header says "1/2 usable" above two answers that both look complete,
    # and the reader has no way to tell which one was discounted or why.
    result = runner.invoke(
        cli.app, ["compare", "s", "q", "-t", "good:m1", "-t", "truncated:m2"]
    )

    assert result.exit_code == 0
    assert "1/2 usable" in result.stdout
    truncated_header = next(h for h in _headers(result.stdout) if "truncated / m2" in h)
    assert "TRUNCATED" in truncated_header
    assert "MAX_TOKENS" in truncated_header
    # ...and the partial answer is still shown rather than hidden.
    assert "The three candidate causes are" in result.stdout


def test_compare_warns_when_the_batch_is_not_a_comparison(cli_env):
    result = runner.invoke(
        cli.app, ["compare", "s", "q", "-t", "good:m1", "-t", "fail:m2"]
    )

    assert result.exit_code == 0
    assert "collection: insufficient" in result.stdout
    assert "Not a comparison" in result.stdout


def test_compare_rejects_duplicate_targets_without_calling_anything(cli_env):
    result = runner.invoke(
        cli.app, ["compare", "s", "q", "-t", "good:m1", "-t", "good:m1"]
    )

    assert result.exit_code == 1
    assert "Duplicate compare targets" in result.stdout
    assert _headers(result.stdout) == []  # nothing was asked, nothing was billed
