# Schemas for defining the structure of the LLM response and metadata as Pydantic's BaseModel.
# The structure containing the LLM response content and metadata such as tokens used, model name, and finish_reason.

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TokenUsageInfo(BaseModel):
    """
    Define a Pydantic models to represent the structure of the LLM's response and metadata.
    """

    model_config = ConfigDict(
        extra="forbid"
    )  # Forbid extra fields to ensure strict adherence to the defined schema.

    prompt_tokens: int
    """Number of tokens in the prompt in TokenUsage."""

    completion_tokens: int
    """Number of tokens in the generated completion in TokenUsage."""

    total_tokens: int
    """Total number of tokens used in the request (prompt + completion) in TokenUsage."""

    cached_tokens: int | None = None
    """Cached tokens present in the prompt in TokenUsage."""


class CostInfo(BaseModel):
    """
    Define a Pydantic model to represent the cost information of the LLM's call,
    includiig input, output, and total cost in USD.
    """

    model_config = ConfigDict(extra="forbid")

    input_usd: float
    """The cost of the input token present in the prompt."""

    cached_input_usd: float | None = None
    """The cost of the cached tokens present in the prompt."""

    output_usd: float
    """The cost of the output tokens present in the prompt."""

    total_usd: float
    """The cost of the total tokens used in the request (prompt + completion)."""

    estimated: bool | None = None
    """Indicate estimated cost to avoid confusion when compared to actual billing data."""

    pricing_updated_at: str | None = None
    """Date the token price table was updated. (YYYY-MM-DD)"""

    pricing_source: str | None = None
    """
    Source of token price

    (ex. for OpenAI, refer to [this page](https://developers.openai.com/api/docs/pricing))
    """


class LLMCallResult(BaseModel):
    """
    Define a Pydantic model to represent the result of an LLM's call,
    including the response text, token usage, and other metadata.
    """

    model_config = ConfigDict(extra="forbid")

    response_id: str
    """UUID for identification of individual LLM response units in LLMCallResult"""

    provider: str
    """Provider(ex. OpenAI, Anthropic, Google,) of the model that generates the response."""

    model: str
    """Model used to generate the response."""

    response_text: str
    """Content of the responses provided by the model."""

    finish_reason: str | None = None
    """
    The reason the model stopped generating tokens.

    If the answer has ended normally, it will be marked `stop`.
    """

    raw_response_id: str | None = None
    """Unique ID given to identify the initial response source (Raw Response)."""

    usage: TokenUsageInfo
    """Token usage infomation about the prompt and model's response."""

    cost: CostInfo | None = None
    """Cost information calculated based on token usage."""


class LLMCallLog(BaseModel):
    """
    Define a Pydantic model to represent the log of an LLM's call.
    """

    model_config = ConfigDict(extra="forbid")
    run_id: str
    created_at: datetime
    provider: str | None = (
        None  # Which provider was attempted (kept even when the call fails and result is None).
    )
    system_prompt: str
    user_prompt: str
    success: bool
    error: str | None = None
    error_type: str | None = (
        None  # Exception class name, so failed calls stay queryable without parsing the message.
    )
    elapsed_sec: float | None = (
        None  # Latency in seconds, recorded for both successful and failed attempts.
    )
    result: LLMCallResult | None = None


class LLMRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raise NotImplementedError
