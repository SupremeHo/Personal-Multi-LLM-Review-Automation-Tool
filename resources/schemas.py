# Schemas for defining the structure of the LLM response and metadata as Pydantic's BaseModel.
# The structure containing the LLM response content and metadata such as tokens used, model name, and finish_reason.

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TokenUsage(BaseModel):
    """Define a Pydantic models to represent the structure of the LLM's response and metadata."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cached_tokens: int | None = None


class CostInfo(BaseModel):
    """Define a Pydantic model to represent the cost information of the LLM's call, including input, output, and total cost in USD."""

    input_usd: float
    cached_input_usd: float | None = None
    output_usd: float
    total_usd: float
    estimated: bool | None = None
    pricing_updated_at: str | None = None
    pricing_source: str | None = None


class LLMCallResult(BaseModel):
    """Define a Pydantic model to represent the result of an LLM's call, including the response text, token usage, and other metadata."""

    model_config = ConfigDict(extra="forbid")  # Forbid extra fields to ensure strict adherence to the defined schema.

    response_id: str
    provider: str
    model: str
    response_text: str
    finish_reason: str | None = None
    raw_response_id: str | None = None
    usage: TokenUsage
    cost: CostInfo | None = None


class LLMCallLog(BaseModel):
    """Define a Pydantic model to represent the log of an LLM's call."""

    model_config = ConfigDict(extra="forbid")  # Forbid extra fields to ensure strict adherence to the defined schema.

    run_id: str
    created_at: datetime
    system_prompt: str
    user_prompt: str
    success: bool
    error: str | None = None
    elapsed_sec: float | None = None
    result: LLMCallResult | None = None
