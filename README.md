# Personal Multi-LLM Review Automation Tool 🚀

![Language](https://img.shields.io/badge/Language-Python_100%25-blue)
![Status](https://img.shields.io/badge/Status-MVP-brightgreen)

> 🇰🇷 한국어 문서는 [README.ko-KR.md](README.ko-KR.md)를 참고하세요.

## 📖 Overview / Description

The **Personal Multi-LLM Review Automation Tool** is a CLI-based auxiliary system designed to automate the cross-validation of responses from multiple Large Language Models (LLMs).

In the process of cross-reviewing answers from various LLMs, manually switching between platforms (the "tab-switching hell") causes severe context-switching and fatigue. This tool orchestrates multiple AI models to evaluate a single prompt, logging the answers, metadata, and locally-computed costs into structured formats (JSONL and SQLite).

## 🎯 Purpose & Philosophy

This project starts as a personal research automation tool to assist with business and investment decisions. Inspired by the philosophy of multi-agent orchestration systems, it has been strictly optimized into a Minimum Viable Product (MVP) for personal use.

**⚠️ Core Philosophy:**

* **AI Majority Vote ≠ Absolute Truth:** The consensus of multiple AIs does not guarantee the truth. _The final decision always belongs to the human user._
* **Reducing Blind Spots:** The true purpose of this tool is _not_ to delegate finding the right answer to AI. Instead, it is designed to automatically reveal missing evidence, counterarguments, and risk factors—effectively minimizing the user's cognitive blind spots before making critical decisions.

## 💻 Tech Stack & Versions

* **Language:** Python 3.12 / 3.13 (100%)
* **CLI Framework:** [Typer](https://typer.tiangolo.com/) (For rapid, type-hinted CLI generation)
* **Data Validation:** Pydantic (Strict, provider-neutral schemas with `extra="forbid"`)
* **Providers:** OpenAI ✅, Anthropic ✅, Google/Gemini ✅
* **Database:** SQLite3 (For local logging and analytical queries)
* **Environment Management:** `venv` with `python-dotenv` for secure API key handling

## 🚀 Usage

### 1. Prerequisites

Ensure you have Python 3.12+ installed, create a virtual environment, and install the pinned dependencies. There is no generic `requirements.txt`; pick the file that matches your Python version:

```bash
python -m venv .venv
# On Windows: .venv\Scripts\activate
# On macOS/Linux: source .venv/bin/activate

pip install -r requirements_py313_win.txt   # or requirements_py312_win.txt
```

To run the test suite you also need the test-only dependency:

```bash
pip install -r requirements_dev_win.txt
```

### 2. Environment Setup

Copy `.env.example` to `.env` in the project root and fill in the API keys you have. All keys are optional—a missing key simply disables that one provider instead of crashing the tool:

```dotenv
OPENAI_API_KEY=your-openai-api-key-here
ANTHROPIC_API_KEY=your-anthropic-api-key-here
GEMINI_API_KEY=your-gemini-api-key-here
```

Validate your setup at any time with:

```bash
python -m resources.cli check-env
```

### 3. Local Configuration (Pricing)

Cost is computed **locally** from data files—no extra API calls. Rates live per provider in `config/prices/prices_{openai,anthropic,gemini}.json` as **USD per 1M tokens**. Each file also carries `updated_at`/`source` metadata, and dated model IDs can reuse a base entry via `alias_of`:

```json
{
  "provider": "OpenAI",
  "currency": "USD",
  "unit": "per_1m_tokens",
  "updated_at": "2026-05-31",
  "source": "https://developers.openai.com/api/docs/pricing",
  "models": {
    "gpt-4o-mini": {
      "input": 0.15,
      "cached_input": 0.075,
      "output": 0.60
    },
    "gpt-4o-mini-2024-07-18": {
      "alias_of": "gpt-4o-mini"
    }
  }
}
```

### 4. Database Setup

The SQLite file `_db/llm_responses.db` is created/seeded once from `_db/_create_table.sql` (run it with the `sqlite3` CLI or any client). The tool connects to an **existing** DB and only `ALTER`s in missing audit columns—it does not create the tables itself.

`_db/_create_table.sql` is the **single source of truth** for the schema (`_db/llm_responses.db` itself is git-ignored). If you ever delete the database and want to recreate it from scratch, re-seed it from that file—do not restore from an ad-hoc DB-client export, which can silently drift from the tracked schema:

```bash
# Recreate an empty, correctly-seeded database
rm _db/llm_responses.db          # optional: remove the old file first
sqlite3 _db/llm_responses.db < _db/_create_table.sql
```

The statements use `CREATE TABLE/INDEX IF NOT EXISTS`, so running the file against an existing DB is safe (it only fills in what is missing). In a GUI client (e.g. DB Browser for SQLite), paste the same file into the **Execute SQL** tab and run it.

### 5. Running the CLI

Run from the **project root** as a module (not `cd resources`). `ask` and `compare` make real (paid) API calls and automatically persist the logs (JSONL) and metadata (SQLite).

**Ask a single provider/model:**

```bash
python -m resources.cli ask "<system_prompt>" "<user_question>"
# defaults: --provider openai --model gpt-4o-mini

python -m resources.cli ask "<system_prompt>" "<user_question>" \
  --provider anthropic --model claude-haiku-4-5
```

**Compare several models side by side** (the core "review" feature)—requires at least one `--target/-t provider:model`. Each call gets its own `run_id`, all tied together by one shared `group_id`:

```bash
python -m resources.cli compare "<system_prompt>" "<user_question>" \
  -t openai:gpt-4o-mini -t anthropic:claude-haiku-4-5
```

**Other commands:**

```bash
python -m resources.cli check-env      # validate .env keys (interactive)
python -m resources.cli list-models    # list models across configured providers
python -m resources.cli history        # show recent calls (newest first)
python -m resources.cli history -n 20              # show the last 20 calls
python -m resources.cli history --group <group_id> # show one comparison's calls
```

* **`system_prompt`** is an instruction that predetermines how the LLM should respond.
* **`user_question`** is the message to the LLM (the more specific and clear, the better).

## 📂 Architecture

The code is a single layered architecture under `resources/`, used as a package with package-absolute imports (`from resources.schemas import ...`) and run from the project root:

```bash
cli.py                                      # thin Typer layer: parse args → delegate → render
  └─ services/service_ask.py                # owns ids (run_id/response_id), builds logs, collects errors, archives
       └─ providers/registry.py             # name → ChatProvider instance
            └─ providers/provider_*.py      # per-provider API specifics (openai, anthropic, google)
                 └─ providers/runner.py     # run_chat(): shared call pipeline, provider differences injected as callbacks
                      └─ count_cost.py / schemas.py / storage_json.py / storage_sqlite.py
```

* **`cli.py`** — thin Typer layer; parses arguments, delegates to the service layer, renders results.
* **`services/service_ask.py`** — orchestration: mints `run_id`/`response_id`, resolves providers, builds the audit log, collects `compare` failures as data, and persists.
* **`providers/registry.py`** — the only place that maps a provider name to a concrete `ChatProvider`.
* **`providers/provider_*.py`** — per-provider API specifics (OpenAI, Anthropic, Google).
* **`providers/runner.py`** — the shared chat pipeline (preflight → paid call → parse → best-effort cost → assemble); each provider only supplies `_call_api` and `_parse_response` callbacks.
* **`schemas.py`** — strict, provider-neutral Pydantic models (`LLMRequest`, `LLMCallResult`, `LLMCallLog`, etc.).
* **`storage_json.py` & `storage_sqlite.py`** — data persistence to JSONL and SQLite.
* **`count_cost.py`** — calculates token usage costs locally (in `Decimal`) without extra API calls.

**Adding a provider** = add a `provider_*.py` + one line in `registry.PROVIDERS`.

## 🧪 Tests

The pytest suite lives in `tests/` and makes **no paid calls**—provider parsing is tested with fake SDK responses, and the service layer by injecting fakes into the registry. Run from the project root:

```bash
python -m pytest
```

## 🤝 Contribution Guide

Since this is currently a personal MVP, direct pull requests to the core logic may be limited. However, contributions and forks are highly welcome in the following areas:

1. **Adding New Providers:** Implementing a `LocalLLMProvider` (e.g., Ollama), or adding other cloud providers.
2. **Evaluator Prompts:** Enhancing the prompts used to detect conflicts and highlight missing citations across model answers.
3. **Cost Analytics:** Creating SQL views or Pandas scripts to analyze model cost-efficiency over time.

***
Feel free to fork the repository, experiment with local LLM integrations, and open an issue if you discover a robust prompting strategy!

***
Other Info: I live in S.Korea. I am not very good at English, so please understand that a translator was used to write this README.
