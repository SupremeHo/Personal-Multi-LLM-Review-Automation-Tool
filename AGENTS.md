# Personal-Multi-LLM-Review-Automation-Tool Guide

> **Note:** `CLAUDE.md` is a one-line stub that imports this file (`@AGENTS.md`). Edit **this** file; `CLAUDE.md` never holds content of its own.

## What this is

A personal CLI tool that sends a prompt to LLM providers, then logs each response together with token usage, locally-computed cost, and audit metadata into JSONL files and a SQLite database. The end goal is *cross-validation* across multiple models (the "review" in the name): the `compare` command asks several providers the same question and shows every answer side by side. OpenAI and Anthropic providers are implemented; Google/Gemini is a stub. The philosophy is to surface blind spots/counterarguments, not to treat an AI majority vote as truth — the human always makes the final call.

> **Project context, history & roadmap:** see [docs/PROJECT_NOTES.ko-KR.md](docs/PROJECT_NOTES.ko-KR.md) — the author's development journal (milestones with status, stage-by-stage progress, design decisions, and design questions). Consult it when you need the *why* behind a decision or the planned direction, not just the current code. Note some entries predate the layered refactor below; the code is the source of truth for current structure.

## Architecture (one layered structure)

The code is a single layered architecture under `resources/`, used as a package with **package-absolute imports** (`from resources.schemas import ...`) and run from the **project root**. The earlier "flat modules vs. SOLID rewrite" split is gone (`llm_client.py` was removed; its logic now lives in the provider/service layers).

```bash
cli.py                              # thin Typer layer: parse args → delegate → render
  └─ services/service_ask.py        # owns ids (run_id/group_id/response_id), builds logs, collects ErrorInfo, archives
       ├─ providers/registry.py     # name → ChatProvider instance (the only place that knows concrete providers)
       │    └─ providers/provider_{openai,anthropic,google}.py   # per-provider API specifics
       │         └─ providers/runner.py     # run_chat(): the shared call pipeline, provider differences injected as callbacks
       │              └─ count_cost.py / schemas.py
       └─ log_repository.py         # LogRepository: fans one log out to every writer; reads back via SqliteLogReader
            └─ storage_json.py / storage_sqlite.py
```

- **`providers/base_provider.py`** defines the `ChatProvider` Protocol (structural contract): `provider_name: str` + `ask(request: LLMRequest) -> LLMCallResult`. Concrete providers satisfy it by structure, not inheritance. (Design choice: Protocol over ABC; shared behavior is reused via `runner.run_chat`, not a base class.)
- **`providers/runner.py`** holds the common chat pipeline once (preflight → paid call → parse → best-effort cost → assemble result → `PaidResponseError`). Each provider only supplies two callbacks: `_call_api` (the paid call) and `_parse_response` (raw response → `ParsedResponse`).
- **`services/service_ask.py`** is the orchestration entry point: `ask()` (single) and `compare()` (multi). It mints `run_id`/`group_id`/`response_id`, resolves providers via the registry, turns every outcome into an `LLMCallLog`, collects failures as `ErrorInfo` (compare only), and archives via `persist_log()`.
- **`log_repository.py`** is the persistence seam. `LogWriter` (Protocol) is one destination; `LogRepository.save()` fans a log out to all of them; `LogReader`/`SqliteLogReader` serves the `history` command. `default_repository()` wires the production set: `JsonlLogWriter` then `SqliteLogWriter`. The service knows only `save()`/`recent()` — never JSONL layout or SQLite connections.
- Small shared helpers: **`diagnostics.py`** (`print_error`, the `[file][func] Error Message:` convention) and **`providers/response_error.py`** (`PaidResponseError`).
- **`config.py`, `models.py`, `prompts.py` are empty placeholders** left from the pre-refactor layout. Nothing imports them; don't go looking for logic there.

When fixing behavior, touch the layer that owns it: the shared flow → `runner.py`; a provider's API quirks → that `provider_*.py`; orchestration → `service_ask.py`; where/how a log is stored → `log_repository.py`. Adding a provider = add a `provider_*.py` + one line in `registry.PROVIDERS`.

## Commands

Run from the **project root** as a module (not `cd resources`):

```bash
python -m resources.cli ask "<system_prompt>" "<user_question>"                 # default provider=openai, model=gpt-4o-mini
python -m resources.cli ask "<system_prompt>" "<user_question>" --provider anthropic --model claude-haiku-4-5
python -m resources.cli compare "<system_prompt>" "<user_question>" -t openai:gpt-4o-mini -t anthropic:claude-haiku-4-5
python -m resources.cli check-env                                               # validate .env keys (interactive prompt)
python -m resources.cli list-models                                             # list models across configured providers
python -m resources.cli history -n 10                                           # recent calls, newest first (free; reads SQLite)
python -m resources.cli history -g <group_id>                                   # only the calls of one comparison batch
```

`ask` and `compare` make real (paid) calls. `compare` requires at least one `--target/-t provider:model` and runs the targets in parallel under one shared `group_id` (each target keeps its own `run_id`), so wall time is the slowest call rather than their sum.

`history` is free — it only reads the local SQLite DB.

Lint / format (config in `pyproject.toml`, target `py314`, line length 88):

```bash
ruff check .
ruff format .
```

Environments & deps — development is consolidated on **Python 3.14** (standard build; free-threading and the JIT were evaluated and deliberately not used). Dependencies are pinned in a single `requirements.txt`, which includes the test-only `pytest`. Virtualenvs live in the working tree but are **gitignored** (`.venv*/`), so a fresh clone has none — older `.venv_py312`/`.venv_py313` directories may still exist locally and are leftovers:

```bash
pip install -r requirements.txt
```

Database — the SQLite file `_db/llm_responses.db` is created/seeded from `_db/_create_table.sql` (run it once with the `sqlite3` CLI or any client). `storage_sqlite.py` connects to an **existing** DB and only `ALTER`s in missing audit columns; it does not create the tables.

Tests — the pytest suite lives in `tests/` (config in `pyproject.toml` sets `testpaths = ["tests"]`). It makes **no paid calls**: provider parsing is tested with fake SDK responses, and the service layer by injecting fakes into `registry.PROVIDERS` and calling `service_ask.ask(..., persist=False)`. Shared fakes/fixtures are in `tests/fakes.py` and `tests/conftest.py`. The legacy `test/` (singular) holds the author's older ad-hoc scripts that hit real APIs; those are intentionally excluded from collection. Run from the project root:

```bash
python -m pytest
```

## Data flow (the `ask` path)

`cli.ask` → `service_ask.ask` (mints ids, builds `LLMRequest`) → `service_ask.run_request` → `registry.get_provider` → `provider.ask` → `runner.run_chat` → returns `LLMCallResult` (or raises `PaidResponseError`) → `run_request` wraps it in an `LLMCallLog` → `service_ask.persist_log` → `default_repository(...).save(log)` fans the log out to `JsonlLogWriter` (appends to `_logs/<Provider>/<prefix>_response_log_<timestamp>.jsonl`) and then `SqliteLogWriter` (upserts into `_db/llm_responses.db`).

`compare` runs the provider-call half of this concurrently per target under one `group_id`, then walks the futures in target order to persist and to collect `ErrorInfo` for any failures.

Two things to know about this path:

- **SQLite is written straight from the in-memory log**, not by re-reading the JSONL. `storage_sqlite.import_jsonl_to_sqlite` still exists as a standalone backfill utility for existing JSONL files, but **nothing on the live path calls it** — don't wire it back in.
- The **read** path is separate: `cli.history` → `service_ask.read_history` → `SqliteLogReader.recent`, which rebuilds each `LLMCallLog` from the `raw_json` column (so failed calls, which have a `runs` row but no `model_responses` row, come back too).

## Design invariants — preserve these when editing the paid path

These conventions encode hard-won billing/safety decisions; don't undo them casually:

- **Never discard a billed response.** In `runner.run_chat`, validation that can be done for free happens in `preflight_pricing` (price file exists + parses, model name is known) **before** the paid call. Anything that fails *after* billing — currently cost calculation — must not throw away the response: it is caught, wrapped in `PaidResponseError(result, original)`, and re-raised so the caller can still persist the paid result. `service_ask.run_request` catches `PaidResponseError` separately from generic `Exception` for exactly this reason, and `compare` preserves the salvaged result in `ErrorInfo.partial_result`.

- **The audit log is always written.** `service_ask.run_request` builds a single `log_data` dict up front (success/error/result all defaulted), mutates it in the try/except/finally, and returns an `LLMCallLog` no matter what — including on failure, with `elapsed_sec` recorded either way. `persist_log` then writes it, so failed runs still produce a `runs` row.

- **Provider contract is simple; failures-as-data live in the service layer.** A provider returns `LLMCallResult` on success and *raises* on failure (`PaidResponseError` for a billed partial). Providers never return errors as values. Turning a failure into a value (`ErrorInfo`) happens only in `service_ask.compare`, so one provider failing never stops the others.

- **`compare` parallelizes the calls only; persistence stays single-threaded.** The targets' API calls run in a `ThreadPoolExecutor` (`max_workers=len(targets)`), which is safe because `run_request` is a self-contained unit that never raises and the registry's provider instances are read-only after construction. But the futures are consumed in **submission order, not completion order**, so `persist_log` only ever runs on the calling thread. Two things depend on that: same-provider targets share one JSONL file (the filename is keyed on the batch-wide `created_at`), and `SqliteLogReader.recent` orders by insertion `id` to keep a group's rows deterministic — concurrent writers would corrupt the first and randomize the second. Do **not** add a `future.result(timeout=...)`: a blocking socket read cannot be cancelled, so a timeout would abandon an already-billed call and break the first invariant above.

- **Money/precision uses `Decimal`.** `count_cost.py` computes per-token cost in `Decimal` (per-1M-token rates) and only converts to `float` at the dict boundary. `cost.estimated` is always `True` to distinguish local estimates from real billing. The cost dict keys are kept 1:1 with `CostInfo` fields so `runner` builds it via `CostInfo(**cost)`.

- **Pricing is data, not code.** Rates live in `config/prices/prices_{openai,claude,gemini}.json` (`per_1m_tokens`, with `updated_at`/`source`) — note the Anthropic table is `prices_claude.json`, keyed off the model family rather than the registry name. `resolve_model_entry` follows `alias_of` so dated model IDs (`gpt-4o-2024-08-06`) reuse a base entry; `notice_price_tag_update` warns when a table is >30 days old.

- **SQLite schema & idempotency.** Two tables: `runs` (one per CLI invocation) and `model_responses` (one per model answer, FK → `runs`, cascade delete). Both insert with `INSERT OR IGNORE` keyed on UUIDs, so re-importing a JSONL is safe. A **failed** run writes only the `runs` row and skips `model_responses` (no `model`/`response_id` → would violate NOT NULL). `ensure_audit_columns` adds `provider`/`error_type`/`group_id` to older DBs idempotently. `storage_sqlite` maps the provider-neutral schema onto the flat columns: `input_tokens`→`prompt_tokens`, `output_tokens`→`completion_tokens`, `total_tokens` derived from input+output when null, and the split cache fields summed into the single `cached_tokens` column (the full breakdown stays in `raw_json`).

- **Schemas are strict and provider-neutral.** All Pydantic models in `schemas.py` use `ConfigDict(extra="forbid")`. Canonical objects:
  - `LLMRequest` (input): system/user prompts, `selected_model`, `max_tokens` (default 4096; required by Anthropic), and a service-injected `response_id`.
  - `TokenUsageInfo`: `input_tokens`/`output_tokens`, optional `total_tokens`, and provider-specific cache fields kept separate — `cached_input_tokens` (OpenAI), `cache_creation_input_tokens`/`cache_read_input_tokens` (Anthropic).
  - `LLMCallResult` (provider output): text + `TokenUsageInfo` + optional `CostInfo`. `provider` uses lowercase registry keys (`openai`/`anthropic`/`google`).
  - `LLMCallLog` (the persisted audit record wrapping an optional `LLMCallResult`).
  - `ErrorInfo`: a service-layer value type for `compare` failures (`provider`/`model`/`error_type`/`message`/`elapsed_sec`/`partial_result`/`created_at`). Produced only by the service layer, never returned by a provider.

## Environment

Each `provider_*.py` constructs its SDK client at import time (`OpenAI()`, `Anthropic()`) and sets `_default_client` to `None` if the key/init fails, rather than crashing — so a missing key disables one provider instead of the whole tool. `env_check.py` mirrors this: missing keys are **warnings**, not fatal. Keys come from `.env` (see `.env.example`): `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`.

## Code Review

Python code reviews should be based on readability, Pythonic grammar, performance, and testability. We recommend automating the most common PEP 8 Style Guide and adapting industry standards such as the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html) to meet team standards.

- **Security**: SQL injection, XSS, Authentication bypass check
- **Performance**: N+1 queries, checking unnecessary repeat statements
- **Convention/Style**: Naming rules, Compliance with import order
- **Test**: Check if the new feature includes a test
