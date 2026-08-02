"""CLI rendering tests (no paid calls; providers and storage are redirected)."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from resources import cli
from resources.providers import registry
from resources.services import service_ask as svc
from tests.fakes import FailProvider, GoodProvider, PaidFailProvider

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
        },
    )
    monkeypatch.setattr(svc, "BASE_DIR", tmp_path)
    monkeypatch.setattr(svc, "DB_PATH", temp_db)


def _headers(output: str) -> list[str]:
    return [line for line in output.splitlines() if line.startswith("---- ")]


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
