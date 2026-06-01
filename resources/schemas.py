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

class CostInfo(BaseModel):
    """Define a Pydantic model to represent the cost information of the LLM's call, including input, output, and total cost in USD."""
    input_usd: float
    output_usd: float
    total_usd: float

class LLMCallResult(BaseModel):
    """Define a Pydantic model to represent the result of an LLM's call, including the response text, token usage, and other metadata."""
    model_config = ConfigDict(extra="forbid")   # Forbid extra fields to ensure strict adherence to the defined schema.

    provider: str
    model: str
    response_text: str
    usage: TokenUsage
    cost: CostInfo
    finish_reason: Optional[str] = None
    raw_response_id: Optional[str] = None

class LLMCallLog(BaseModel):
    """Define a Pydantic model to represent the log of an LLM's call."""
    model_config = ConfigDict(extra="forbid")   # Forbid extra fields to ensure strict adherence to the defined schema.

    run_id: str
    created_at: datetime
    user_prompt: str
    result: Optional[LLMCallResult] = None
    success: bool
    error: Optional[str] = None
    elapsed_sec: Optional[float] = None
