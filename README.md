# Personal Multi-LLM Review Automation Tool 🚀

![Language](https://img.shields.io/badge/Language-Python_100%25-blue)
![Status](https://img.shields.io/badge/Status-MVP_Phase_1.5-brightgreen)

## 📖 Overview / Description

The **Personal Multi-LLM Review Automation Tool** is a CLI-based auxiliary system designed to automate the cross-validation of responses from multiple Large Language Models (LLMs).

In the process of cross-reviewing answers from various LLMs, manually switching between platforms (the "tab-switching hell") causes severe context-switching and fatigue. This tool orchestrates multiple AI models to simultaneously evaluate a single prompt, logging the answers, metadata, and costs into structured formats (JSONL and SQLite).

## 🎯 Purpose & Philosophy

This project starts as a personal research automation tool to assist with business and investment decisions. Inspired by the philosophy of multi-agent orchestration systems (like Sakana's Fugu), it has been strictly optimized into a Minimum Viable Product (MVP) for personal use.

**⚠️ Core Philosophy:**

* **AI Majority Vote ≠ Absolute Truth:** The consensus of multiple AIs does not guarantee the truth. _The final decision always belongs to the human user._
* **Reducing Blind Spots:** The true purpose of this tool is _not_ to delegate finding the right answer to AI. Instead, it is designed to automatically reveal missing evidence, counterarguments, and risk factors—effectively minimizing the user's cognitive blind spots before making critical decisions.

## 💻 Tech Stack & Versions

* **Language:** Python 3.x (100%)
* **CLI Framework:** [Typer](https://typer.tiangolo.com/) (For rapid, type-hinted CLI generation)
* **Data Validation:** Pydantic (For structured LLM outputs)
* **Database:** SQLite3 (For local logging and analytical queries)
* **Environment Management:** `venv` with `dotenv` for secure API Key handling

## 🚀 Usage

### 1. Prerequisites

Ensure you have Python installed, create a virtual environment, and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Setup

Create a .env file in the root directory and add your API keys:
>OPENAI_API_KEY="your-openai-api-key-here"

Future updates will include ANTHROPIC_API_KEY, GEMINI_API_KEY, etc

### 3. Local Configuration (Pricing)

Set up the token pricing for cost calculation in config/pricing.json (Standard Prices // USD per 1M tokens):

```JSON
{
  "models": {
    "gpt-4o-mini": {
      "input": 0.15,
      "cached_input": 0.075,
      "output": 0.60
      }
  }
}
```

### 4. Running the CLI

Use the Typer CLI to ask a question. The tool will call the API, output the answer, and automatically save the logs (JSONL) and metadata to the SQLite database.

> python cli.py ask "system_prompt" "user_prompt"

* **"system_prompt"** is an instruction that predetermines how LLM should respond.
* **"user_prompt"** is a message to LLM for questions or instructions (The more specific and clear, the better.).

## 📂 Architecture

* cli.py: Handles terminal inputs and user interactions via Typer.
* llm_client.py: Manages API calls and retrieves responses.
* schemas.py: Defines data structures using Pydantic.
* storage_json.py & storage_sqlite.py: Manages data persistence.
* count_cost.py: Calculates token usage costs locally without additional API calls.

## 🤝 Contribution Guide

Since this is currently a personal MVP, direct pull requests to the core logic may be limited. However, contributions and forks are highly welcome in the following areas:

1. Adding New Providers: Implementing ClaudeProvider, GeminiProvider, or LocalLLMProvider (e.g., Ollama).
2. Evaluator Prompts: Enhancing the prompts used by the "Coordinator AI" to detect conflicts and highlight missing citations.
3. Cost Analytics: Creating SQL views or Pandas scripts to analyze model cost-efficiency over time.

***
Feel free to fork the repository, experiment with local LLM integrations, and open an issue if you discover a robust prompting strategy!

***
Other Info: I live in S.Korea. I am not very good at English, but I was forced to use a translator to write README.md , so I ask for your understanding.
