"""Mock LLM for testing AI-dependent code without real API calls.

Provides drop-in replacements for:
- invoke_with_retry(llm, messages) from core/llm.py
- get_llm(state) from core/llm.py
- The LangChain ChatAnthropic / ChatOpenAI interface

Usage in tests:
    from tests.helpers.mock_llm import MockLLM, patch_llm

    def test_analysis(sample_state):
        with patch_llm("The case involves an assault charge."):
            result = some_function_that_calls_llm(sample_state)
            assert "assault" in result.lower()
"""

from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock, patch


class MockAIMessage:
    """Mimics langchain_core.messages.AIMessage."""

    def __init__(self, content: str):
        self.content = content
        self.response_metadata = {
            "token_usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }

    def __str__(self) -> str:
        return self.content


class MockLLM:
    """Mock LangChain LLM that returns canned responses.

    Supports both single response and per-call response sequences.
    """

    def __init__(self, responses: str | list[str] = "Mock LLM response."):
        if isinstance(responses, str):
            self._responses = [responses]
        else:
            self._responses = list(responses)
        self._call_index = 0
        self.call_log: list[Any] = []

    def invoke(self, messages: Any, **kwargs: Any) -> MockAIMessage:
        self.call_log.append({"messages": messages, "kwargs": kwargs})
        response = self._responses[min(self._call_index, len(self._responses) - 1)]
        self._call_index += 1
        return MockAIMessage(response)

    @property
    def call_count(self) -> int:
        return len(self.call_log)


def create_mock_llm(responses: str | list[str] = "Mock LLM response.") -> MockLLM:
    """Create a MockLLM instance."""
    return MockLLM(responses)


@contextmanager
def patch_llm(responses: str | list[str] = "Mock LLM response."):
    """Context manager that patches get_llm and invoke_with_retry.

    Usage:
        with patch_llm("Expected response") as mock:
            result = function_under_test(state)
            assert mock.call_count == 1
    """
    mock = MockLLM(responses)

    def mock_get_llm(state: dict, **kwargs: Any) -> MockLLM:
        return mock

    def mock_invoke_with_retry(llm: Any, messages: Any, **kwargs: Any) -> MockAIMessage:
        return mock.invoke(messages, **kwargs)

    with (
        patch("core.llm.get_llm", side_effect=mock_get_llm),
        patch("core.llm.invoke_with_retry", side_effect=mock_invoke_with_retry),
    ):
        yield mock


@contextmanager
def patch_llm_in_module(module_path: str, responses: str | list[str] = "Mock LLM response."):
    """Patch LLM calls within a specific module.

    Usage:
        with patch_llm_in_module("core.war_game", '{"score": 75}') as mock:
            result = generate_round_attack(state, session, "theory")
    """
    mock = MockLLM(responses)

    def mock_invoke(llm: Any, messages: Any, **kwargs: Any) -> MockAIMessage:
        return mock.invoke(messages, **kwargs)

    with (
        patch(f"{module_path}.get_llm", return_value=mock),
        patch(f"{module_path}.invoke_with_retry", side_effect=mock_invoke),
    ):
        yield mock


def mock_extract_json(text: str) -> dict | list | None:
    """A passthrough mock for extract_json that handles common test patterns."""
    import json
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON in the text
        for start_char in ["{", "["]:
            idx = text.find(start_char)
            if idx >= 0:
                end_char = "}" if start_char == "{" else "]"
                depth = 0
                for i in range(idx, len(text)):
                    if text[i] == start_char:
                        depth += 1
                    elif text[i] == end_char:
                        depth -= 1
                        if depth == 0:
                            try:
                                return json.loads(text[idx : i + 1])
                            except json.JSONDecodeError:
                                break
        return None
