# Module for outputting the user's questions, LLM's prompts, and metadata as JSON.

import json
from openai import OpenAI
from datetime import datetime


LLM_response = {
    "request_id": "2026-05-27T12-45-30",
    "created_at": "2026-05-27T12:45:30+09:00",
    "provider": "openai",
    "model": "gpt-4o-mini-2024-07-18",
    "user_prompt": "Who are you?",
    "assistant_response": "...",
    "usage": {
    "prompt_tokens": 25,
    "completion_tokens": 70,
    "total_tokens": 95
    },
    "cost": {
        "input_usd": 0.00000375,
        "output_usd": 0.000042,
        "total_usd": 0.00004575
    },
    "finish_reason": "stop",
    "success": true, # type: ignore
    "error": null # type: ignore
}

