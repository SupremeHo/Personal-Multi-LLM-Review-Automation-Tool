# This module covers methods for multiple error codes about LLMs' responses.
from resources.schemas import LLMCallResult, SalvageInfo


class PaidResponseError(Exception):
    """
    Raised when a paid API call already succeeded (a response was billed and received)
    but a later, non-billing step failed - parsing, cost calculation, or result validation.

    The run should be judged a failure, yet what we already paid for must not be
    discarded. How much survives depends on where the pipeline broke:

    * cost calculation failed → ``result`` holds the full response (cost is None);
    * parsing or result validation failed → there is no result to carry, so
      ``salvage`` holds what could still be read off the billed raw response.

    At least one of the two is always present, so the caller can persist an audit
    record proving money was spent instead of losing the call.
    """

    def __init__(
        self,
        original: Exception,
        *,
        result: LLMCallResult | None = None,
        salvage: SalvageInfo | None = None,
    ):
        if result is None and salvage is None:
            raise ValueError(
                "PaidResponseError requires result or salvage to preserve."
            )
        # The underlying failure that happened after billing.
        self.original = original
        # The response/tokens that were already paid for, if still assembled.
        self.result = result
        # Diagnostics for a billed response that never became a result.
        self.salvage = salvage
        super().__init__(str(original))
