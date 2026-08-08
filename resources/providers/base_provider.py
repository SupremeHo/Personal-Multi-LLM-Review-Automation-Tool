# Common, provider-neutral contract that every LLM provider must satisfy.
# Per-provider API differences are NOT defined here; each `provider_<name>.py`
# absorbs those differences and returns an LLMCallResult that conforms to this contract.

from typing import Protocol, runtime_checkable

from resources.schemas import LLMCallResult, LLMRequest


@runtime_checkable
class ChatProvider(Protocol):
    """
    Structural contract for a single-model chat provider.

    A provider is anything that exposes ``provider_name`` and ``ask()`` with the
    signatures below — no inheritance required (structural typing). Concrete
    implementations live in ``provider_<name>.py``.

    Contract invariants:

    * Success → return an :class:`LLMCallResult`.
    * Failure *before* billing (e.g. missing client, preflight pricing failure)
      → raise a plain exception. No money was spent, nothing to preserve.
    * Failure *after* billing (parsing, cost calculation, or result validation on
      an already-charged response) → raise
      :class:`resources.providers.response_error.PaidResponseError`, carrying the
      salvaged ``LLMCallResult`` when one could still be assembled and
      ``SalvageInfo`` otherwise, so a billed response is never discarded.

    A provider never returns an error as data. Turning a failure into a value
    (``ErrorInfo``) is solely the service layer's job in the multi-compare flow,
    keeping this contract free of the exceptions-vs-data mix.

    The call is synchronous, matching the rest of the codebase, and ``ask()`` must
    be **safe to call concurrently**: the registry holds one instance per provider
    and ``compare`` calls it from several threads at once. The bundled providers
    satisfy this by holding only immutable state after construction (an SDK client
    and a price path), and the OpenAI/Anthropic/Gemini clients are themselves
    thread-safe. A provider that caches mutable per-call state on ``self`` would
    break that and must not be added without a lock.
    """

    provider_name: str
    """Canonical registry key for this provider ("openai", "anthropic", "google")."""

    def ask(self, request: LLMRequest) -> LLMCallResult:
        """
        Send ``request`` to a single model and return the result.

        Args:
          request: The provider-agnostic request. Carries the system prompt, the
            user question, the selected model, ``max_tokens``, and the
            service-injected ``response_id``.

        Returns:
          An :class:`LLMCallResult` on success.

        Raises:
          PaidResponseError: A response was billed but a later, non-billing step
            failed; the partial result and/or salvage diagnostics are attached
            for the caller to persist.
          Exception: Any pre-billing failure.
        """
        ...
