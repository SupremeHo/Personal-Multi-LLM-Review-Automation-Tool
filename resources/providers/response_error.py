# This module covers methods for multiple error codes about LLMs' responses.
from resources.schemas import LLMCallResult


class PaidResponseError(Exception):
    """
    Raised when a paid API call already succeeded (a response was billed and received)
    but a later, non-billing step failed - for example cost calculation.

    The run should be judged a failure, yet the response and token usage we already
    paid for must not be discarded. This exception carries that partial result so the
    caller can persist it as an audit log instead of losing it.
    """

    def __init__(self, result: LLMCallResult, original: Exception):
        self.result = result  # The response/tokens that were already paid for.
        self.original = original  # The underlying failure that happened after billing.
        super().__init__(str(original))
