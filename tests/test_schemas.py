"""Domain schema contract tests."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from resources.schemas import (
    CostInfo,
    ErrorInfo,
    LLMCallLog,
    LLMCallResult,
    LLMRequest,
    TokenUsageInfo,
)


def test_token_usage_openai_shape():
    u = TokenUsageInfo(
        input_tokens=100, output_tokens=50, total_tokens=150, cached_input_tokens=20
    )
    assert u.total_tokens == 150
    assert u.cached_input_tokens == 20
    # Anthropic-only fields stay None for an OpenAI-shaped usage.
    assert u.cache_creation_input_tokens is None
    assert u.cache_read_input_tokens is None


def test_token_usage_anthropic_shape():
    u = TokenUsageInfo(
        input_tokens=200,
        output_tokens=80,
        cache_creation_input_tokens=30,
        cache_read_input_tokens=10,
    )
    # total_tokens is optional; Anthropic omits it.
    assert u.total_tokens is None
    assert u.cached_input_tokens is None
    assert (u.cache_creation_input_tokens, u.cache_read_input_tokens) == (30, 10)


def test_schemas_forbid_extra_fields():
    with pytest.raises(ValidationError):
        TokenUsageInfo(input_tokens=1, output_tokens=1, cached_tokens=5)  # old name


def test_llm_request_requires_response_id_and_defaults_max_tokens():
    req = LLMRequest(
        response_id="rid",
        system_prompt="s",
        user_question="q",
        selected_model="m",
    )
    assert req.response_id == "rid"
    assert req.max_tokens == 4096

    with pytest.raises(ValidationError):
        LLMRequest(system_prompt="s", user_question="q", selected_model="m")


def test_error_info_is_a_value_type():
    e = ErrorInfo(
        provider="openai",
        error_type="RuntimeError",
        message="boom",
        created_at=datetime.now(),
    )
    assert e.partial_result is None
    assert e.model is None


def test_llm_call_log_wraps_optional_result():
    result = LLMCallResult(
        response_id="r",
        provider="openai",
        model="m",
        response_text="t",
        usage=TokenUsageInfo(input_tokens=1, output_tokens=1, total_tokens=2),
        cost=CostInfo(input_usd=0.1, output_usd=0.2, total_usd=0.3, estimated=True),
    )
    log = LLMCallLog(
        run_id="run",
        created_at=datetime.now(),
        provider="openai",
        system_prompt="s",
        user_prompt="q",
        success=True,
        result=result,
    )
    assert log.success is True
    assert log.result.response_text == "t"

    failed = LLMCallLog(
        run_id="run",
        created_at=datetime.now(),
        provider="openai",
        system_prompt="s",
        user_prompt="q",
        success=False,
    )
    assert failed.result is None
