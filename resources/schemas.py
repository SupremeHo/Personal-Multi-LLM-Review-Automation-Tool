# Schemas for defining the structure of the LLM response and metadata.
# The structure containing the LLM response content and metadata such as tokens used, model name, and finish_reason.

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

# Define Pydantic models to represent the structure of the LLM's response and metadata.
class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

# Define a model to represent the cost information of the LLM's call, including input, output, and total cost in USD.
class CostInfo(BaseModel):
    input_usd: float
    output_usd: float
    total_usd: float

# Define a model to represent the result of an LLM's call.
class LLMCallResult(BaseModel):
    model_config = ConfigDict(extra="forbid")   # Forbid extra fields to ensure strict adherence to the defined schema.

    provider: str
    model: str
    response_text: str
    usage: TokenUsage
    #cost: CostInfo
    finish_reason: Optional[str] = None
    raw_response_id: Optional[str] = None

# Define a model to represent the log of an LLM's call.
class LLMCallLog(BaseModel):
    model_config = ConfigDict(extra="forbid")   # Forbid extra fields to ensure strict adherence to the defined schema.

    run_id: str
    created_at: datetime
    user_prompt: str
    result: Optional[LLMCallResult] = None
    success: bool
    error: Optional[str] = None
    elapsed_ms: Optional[int] = None
