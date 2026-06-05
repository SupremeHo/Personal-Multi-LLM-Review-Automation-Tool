"""
Schemas for defining the structure of the LLM response and metadata as Pydantic's BaseModel.
The structure containing the LLM response content and metadata such as tokens used, model name, and finish_reason.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class TokenUsage(BaseModel):
    """Define a Pydantic models to represent the structure of the LLM's response and metadata."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cached_tokens: Optional[int] = None


class CostInfo(BaseModel):
    """Define a Pydantic model to represent the cost information of the LLM's call, including input, output, and total cost in USD."""

    input_usd: float
    cached_input_usd: Optional[float] = None
    output_usd: float
    total_usd: float
    estimated: Optional[bool] = None
    pricing_updated_at: Optional[str] = None
    pricing_source: Optional[str] = None


class LLMCallResult(BaseModel):
    """Define a Pydantic model to represent the result of an LLM's call, including the response text, token usage, and other metadata."""

    model_config = ConfigDict(extra="forbid")  # Forbid extra fields to ensure strict adherence to the defined schema.

    provider: str
    model: str
    system_prompt: str
    response_text: str
    finish_reason: Optional[str] = None
    raw_response_id: Optional[str] = None
    usage: TokenUsage
    cost: CostInfo


class LLMCallLog(BaseModel):
    """Define a Pydantic model to represent the log of an LLM's call."""

    model_config = ConfigDict(extra="forbid")  # Forbid extra fields to ensure strict adherence to the defined schema.

    run_id: str
    created_at: datetime
    user_prompt: str
    success: bool
    error: Optional[str] = None
    elapsed_sec: Optional[float] = None
    result: Optional[LLMCallResult] = None
