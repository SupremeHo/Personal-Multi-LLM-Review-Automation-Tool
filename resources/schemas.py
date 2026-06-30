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

    input_tokens: int
    """Number of tokens in the prompt."""

    output_tokens: int
    """Number of tokens in the generated completion."""

    total_tokens: int
    """Total number of tokens used in the request (input(prompt) + output(completion) + cached tokens)."""

    cached_tokens: int | None = None
    """Cached tokens present in the prompt."""


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


class LLMRequest(BaseModel):
    """
    Define a Pydantic model to represent a request to LLMs,
    including the system prompt, user's question, and selected model.
    """

    model_config = ConfigDict(extra="forbid")

    system_prompt: str
    user_question: str
    selected_model: str


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


class ErrorInfo(BaseModel):
    """
    I put ErrorInfo in the list of common schemas. Stop here and ask myself.

    Is this ErrorInfo "data recording failures in the log" or "failure expression that provider returns instead of raise"? The two are completely different decisions, and when mixed, it becomes the worst (a mix of exceptions and data) that we warned last time.

    * Now the code is exception propagation. If the provider fails, raise it, and bring up partial results with PaidResponseError.

    * But in comparison (three calls at the same time), the situation is different. If one provider raises, the other two can be stopped. For simultaneous calls, it is correct to collect the results of each provider as a 'value' whether it is successful or unsuccessful — so that the last partial/quorum is established.

    In other words, single-ask and multi-compare can have different error models. Claude's recommendation is to keep provider contracts simple (LLMCallResult on success, raise on failure), and the conversion to ErrorInfo is done by the service layer compare loop with an exception. This ensures that provider contracts are not dirty, and the responsibility to "turn failure into data" arises only where multi-calls are aggregated.

    → It's not a fixed issue. Before putting ErrorInfo into the schema, I need to decide "where this is made (provider or service)". The whole structure depends on who makes it.
    """

    model_config = ConfigDict(extra="forbid")
