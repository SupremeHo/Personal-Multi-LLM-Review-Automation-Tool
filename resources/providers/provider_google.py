# This module is responsible for absorbing the unique fields of Google's API and translating them into LLMCallResult.

from typing import Protocol

from resources.schemas import LLMCallResult


class GoogleProvider(Protocol):
    def ask(
        self, system_prompt: str, user_question: str, selected_model: str
    ) -> LLMCallResult:
        raise NotImplementedError
