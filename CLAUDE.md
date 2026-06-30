# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A personal CLI tool that sends a prompt to LLM providers, then logs each response together with token usage, locally-computed cost, and audit metadata into JSONL files and a SQLite database. The end goal is *cross-validation* across multiple models (the "review" in the name), but the current working code only calls OpenAI for a single answer. The philosophy is to surface blind spots/counterarguments, not to treat an AI majority vote as truth — the human always makes the final call.

> **Project context, history & roadmap:** see [docs/PROJECT_NOTES.md](docs/PROJECT_NOTES.md) — the author's development journal (milestones with status, stage-by-stage progress, design decisions like Protocol-vs-ABC and the partial-failure policy, and open design questions). Consult it when you need the *why* behind a decision or the planned direction, not just the current code.

## Two parallel architectures live in this repo (read this first)

The `solid_refactoring` branch contains **two overlapping code structures**. Know which one you are touching:

1. **Flat modules in `resources/` — this is the working, runnable code.** `cli.py`, `llm_client.py`, `count_cost.py`, `schemas.py`, `storage_json.py`, `storage_sqlite.py`, `env_check.py`, `list_models.py`. These use **bare imports** (`import llm_client`, `from schemas import ...`), so they only resolve when `resources/` is the working directory / on `sys.path`. This is what `python cli.py ask ...` runs.

2. **`resources/providers/` and `resources/services/` — in-progress SOLID rewrite, mostly stubs/scaffolding.** `services/service_ask.py` raises `NotImplementedError`; `providers/registry.py` is fully commented out; `providers/provider_google.py` is a stub; `base_provider.py` and the `provider_*.py` files are `Protocol` sketches, some with known bugs (e.g. `provider_anthropic.py` reads `usage.prompt_tokens`/`completion_tokens`, which are OpenAI field names, not Anthropic's). These files also **mix import styles** — some use package-absolute `from resources.schemas import ...` (run from project root) and others use bare `from count_cost import ...` — so they are not cleanly importable yet. Treat this layer as a design target, not behavior to preserve, unless the task is explicitly to advance the refactor.

When fixing a bug in actual behavior, change the **flat `resources/` modules**. When extending the multi-provider architecture, work in `providers/`/`services/` and expect to fix imports as you go.

## Commands

The CLI is `resources/cli.py` and relies on bare imports, so **run it from inside the `resources/` directory**:

```bash
cd resources
python cli.py ask "<system_prompt>" "<user_question>"   # paid OpenAI call; logs to JSONL + SQLite
python cli.py check-env                                  # validate .env keys (interactive prompt)
python cli.py list-models                                # list models across configured providers
# `history` is declared but raises NotImplementedError
```

Lint / format (config in `pyproject.toml`, target `py312`, line length 88):

```bash
ruff check .
ruff format .
```

Environments & deps — two Windows venvs are committed, `.venv_py312` and `.venv_py313`, with matching pinned requirement files. There is **no** generic `requirements.txt`:

```bash
pip install -r requirements_py313_win.txt   # or requirements_py312_win.txt
```

Database — the SQLite file `db/llm_responses.db` is created/seeded from `db/_create_table.sql` (run it once with the `sqlite3` CLI or any client). `storage_sqlite.py` connects to an **existing** DB and only `ALTER`s in missing audit columns; it does not create the tables.

Tests — `test/` contains `test.py`, `test_anthropic_api.py`, `test_google_api.py`, but they are ad-hoc scripts (much of `test.py` is commented out), not a pytest suite. There is no configured test runner.

## Data flow (the working `ask` path)

`cli.ask` → `llm_client.ask_openai` → returns `LLMCallResult` (or raises `PaidResponseError`) → `cli` wraps it in an `LLMCallLog` → `storage_json.append_jsonl` writes to `logs/OpenAI/gpt_response_log_<timestamp>.jsonl` → `storage_sqlite.import_jsonl_to_sqlite` upserts into `db/llm_responses.db`.

## Design invariants — preserve these when editing the paid path

These conventions encode hard-won billing/safety decisions; don't undo them casually:

- **Never discard a billed response.** Inside `ask_openai`, validation that can be done for free happens in `preflight_pricing` (price file exists + parses, model name is known) **before** the paid API call. Anything that fails *after* billing — currently cost calculation — must not throw away the response: it is caught, wrapped in `PaidResponseError(result, original)`, and re-raised so the caller can still persist the paid result. `cli.ask` catches `PaidResponseError` separately from generic `Exception` for exactly this reason.

- **The audit log is always written.** `cli.ask` builds a single `log_data` dict up front (success/error/result all defaulted), mutates it in the try/except/finally, and saves it no matter what — including on failure, with `elapsed_sec` recorded either way. Failed runs still produce a `runs` row.

- **Money/precision uses `Decimal`.** `count_cost.py` computes per-token cost in `Decimal` (per-1M-token rates) and only converts to `float` at the dict boundary. `cost.estimated` is always `True` to distinguish local estimates from real billing.

- **Pricing is data, not code.** Rates live in `config/prices/prices_{openai,anthropic,gemini}.json` (`per_1m_tokens`, with `updated_at`/`source`). `resolve_model_entry` follows `alias_of` so dated model IDs (`gpt-4o-2024-08-06`) reuse a base entry; `notice_price_tag_update` warns when a table is >30 days old.

- **SQLite schema & idempotency.** Two tables: `runs` (one per CLI invocation) and `model_responses` (one per model answer, FK → `runs`, cascade delete). Both insert with `INSERT OR IGNORE` keyed on UUIDs, so re-importing a JSONL is safe. A **failed** run writes only the `runs` row and skips `model_responses` (no `model`/`response_id` → would violate NOT NULL). `ensure_audit_columns` adds `provider`/`error_type` to older DBs idempotently.

- **Schemas are strict.** All Pydantic models in `schemas.py` use `ConfigDict(extra="forbid")`. The canonical objects are `LLMRequest` (input), `LLMCallResult` (provider output: text + `TokenUsageInfo` + `CostInfo`), and `LLMCallLog` (the persisted audit record wrapping an optional `LLMCallResult`). `ErrorInfo` is an intentionally-empty placeholder whose docstring records an open design question about where failures become data (provider vs. service layer) — don't flesh it out without resolving that.

## Environment

Provider clients (`OpenAI()`, `Anthropic()`, Google) are constructed at import time and set to `None` if their key/init fails, rather than crashing — so a missing key disables one provider instead of the whole tool. `env_check.py` mirrors this: missing keys are **warnings**, not fatal. Keys come from `.env` (see `.env.example`): `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`.
