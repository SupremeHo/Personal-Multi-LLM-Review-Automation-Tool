# Personal Multi-LLM Review Automation Tool

## How did you start the project?

> In the process of cross-reviewing the answers I received from several LLMs, I personally found it a bit of a hassle to use multiple platforms alternately. My eyes were so tired. So I thought a program that *automates cross-validation of responses from multiple LLMs* would be nice.

## What is your plan?

> It starts at the level of a personal research automation tool that assists business and investment decisions.
> I will use the philosophy of Sakana's Fugu system and develop it as an auxiliary system that will increase investment, business, and research productivity by making it a minimum viable product for personal use.

## Commands currently available

- ask: Prompt the user for a question and output the question.
  - `python cli.py ask "system_prompt" "user_prompt"`
  - system_prompt: A top-level guideline and basic setting that pre-defined 'who are you', 'how to act', and 'what not to do' for LLM models.
  - user_prompt: Specific instructions, questions, or requests that users enter to LLM models to get the desired results.

- check-env: Check environment variables from .env file.
  - `python cli.py check-env`

- list-models: This will list available models from the OpenAI API.
  - `python cli.py list-models`
