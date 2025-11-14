"""
Test suite for Kimi context_manager.add_response() refactoring

This test file captures the current behavior of add_response() before refactoring,
then validates that the refactored version produces identical results.
"""

import json
from typing import Any, Dict, List, Optional
from unittest.mock import Mock

import pytest
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)

from backend.infrastructure.llm.providers.kimi.context_manager import (
    KimiContextManager,
)


# ============================================================================
# Mock Helper Functions
# ============================================================================


def create_mock_response(
    content: Optional[str] = None,
    reasoning_content: Optional[str] = None,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    role: str = "assistant",
) -> ChatCompletion:
    """
    Create a mock ChatCompletion response for testing.

    Args:
        content: Message text content
        reasoning_content: Reasoning content (K2 Thinking models)
        tool_calls: List of tool call dicts with 'id', 'name', 'arguments'
        role: Message role (default: assistant)

    Returns:
        Mock ChatCompletion object
    """
    # Create message mock
    message = Mock(spec=ChatCompletionMessage)
    message.role = role
    message.content = content

    # Add reasoning_content attribute (K2 Thinking)
    if reasoning_content is not None:
        message.reasoning_content = reasoning_content
    else:
        # Use getattr default behavior when attribute doesn't exist
        type(message).reasoning_content = property(
            lambda self: getattr(self, "_reasoning_content", None)
        )
        message._reasoning_content = None

    # Add tool_calls
    if tool_calls:
        mock_tool_calls = []
        for tc in tool_calls:
            tool_call = Mock(spec=ChatCompletionMessageToolCall)
            tool_call.id = tc["id"]
            tool_call.type = "function"

            function = Mock(spec=Function)
            function.name = tc["name"]
            function.arguments = (
                json.dumps(tc["arguments"])
                if isinstance(tc["arguments"], dict)
                else tc["arguments"]
            )

            tool_call.function = function
            mock_tool_calls.append(tool_call)

        message.tool_calls = mock_tool_calls
    else:
        message.tool_calls = None

    # Create choice mock
    choice = Mock(spec=Choice)
    choice.message = message

    # Create response mock
    response = Mock(spec=ChatCompletion)
    response.choices = [choice]

    return response


# ============================================================================
# Test Cases
# ============================================================================


class TestContextManagerAddResponse:
    """Test current behavior of context_manager.add_response()"""

    def test_basic_text_response(self):
        """Test 1: Basic text response without reasoning or tools"""
        ctx = KimiContextManager(session_id="test-session")
        response = create_mock_response(content="Hello, world!")

        ctx.add_response(response)

        assert len(ctx.working_contents) == 1
        msg = ctx.working_contents[0]

        assert msg["role"] == "assistant"
        assert msg["content"] == "Hello, world!"
        assert "reasoning_content" not in msg
        assert "tool_calls" not in msg

    def test_response_with_reasoning_content(self):
        """Test 2: Response with reasoning_content (K2 Thinking model)"""
        ctx = KimiContextManager(session_id="test-session")
        response = create_mock_response(
            content="The answer is 42",
            reasoning_content="Let me think step by step...",
        )

        ctx.add_response(response)

        assert len(ctx.working_contents) == 1
        msg = ctx.working_contents[0]

        assert msg["role"] == "assistant"
        assert msg["content"] == "The answer is 42"
        assert msg["reasoning_content"] == "Let me think step by step..."
        assert "tool_calls" not in msg

    def test_response_with_single_tool_call(self):
        """Test 3: Response with single tool call"""
        ctx = KimiContextManager(session_id="test-session")
        response = create_mock_response(
            content="Using calculator",
            tool_calls=[
                {"id": "call_123", "name": "calculator", "arguments": {"expr": "2+2"}}
            ],
        )

        ctx.add_response(response)

        assert len(ctx.working_contents) == 1
        msg = ctx.working_contents[0]

        assert msg["role"] == "assistant"
        assert msg["content"] == "Using calculator"
        assert "tool_calls" in msg
        assert len(msg["tool_calls"]) == 1

        tool_call = msg["tool_calls"][0]
        assert tool_call["id"] == "call_123"
        assert tool_call["type"] == "function"
        assert tool_call["function"]["name"] == "calculator"
        assert tool_call["function"]["arguments"] == '{"expr": "2+2"}'

    def test_response_with_multiple_tool_calls(self):
        """Test 4: Response with multiple tool calls"""
        ctx = KimiContextManager(session_id="test-session")
        response = create_mock_response(
            content="Using multiple tools",
            tool_calls=[
                {"id": "call_1", "name": "tool_a", "arguments": {"param": "a"}},
                {"id": "call_2", "name": "tool_b", "arguments": {"param": "b"}},
            ],
        )

        ctx.add_response(response)

        assert len(ctx.working_contents) == 1
        msg = ctx.working_contents[0]

        assert msg["role"] == "assistant"
        assert msg["content"] == "Using multiple tools"
        assert len(msg["tool_calls"]) == 2

    def test_response_with_tool_calls_and_empty_content(self):
        """Test 5: Response with tool calls and empty content - content should be omitted"""
        ctx = KimiContextManager(session_id="test-session")
        response = create_mock_response(
            content="",  # Empty content
            tool_calls=[
                {"id": "call_123", "name": "calculator", "arguments": {"expr": "2+2"}}
            ],
        )

        ctx.add_response(response)

        assert len(ctx.working_contents) == 1
        msg = ctx.working_contents[0]

        assert msg["role"] == "assistant"
        # When content is empty and has tool_calls, content should be omitted
        assert "content" not in msg or msg.get("content") == ""
        assert "tool_calls" in msg

    def test_response_with_tool_calls_and_none_content(self):
        """Test 6: Response with tool calls and None content - content should be omitted"""
        ctx = KimiContextManager(session_id="test-session")
        response = create_mock_response(
            content=None,  # None content
            tool_calls=[
                {"id": "call_123", "name": "calculator", "arguments": {"expr": "2+2"}}
            ],
        )

        ctx.add_response(response)

        assert len(ctx.working_contents) == 1
        msg = ctx.working_contents[0]

        assert msg["role"] == "assistant"
        # When content is None and has tool_calls, content should be omitted
        assert "content" not in msg or msg.get("content") is None
        assert "tool_calls" in msg

    def test_response_with_reasoning_and_tool_calls(self):
        """Test 7: Response with both reasoning_content and tool_calls"""
        ctx = KimiContextManager(session_id="test-session")
        response = create_mock_response(
            content="Let me calculate",
            reasoning_content="I need to use the calculator tool",
            tool_calls=[
                {"id": "call_123", "name": "calculator", "arguments": {"expr": "2+2"}}
            ],
        )

        ctx.add_response(response)

        assert len(ctx.working_contents) == 1
        msg = ctx.working_contents[0]

        assert msg["role"] == "assistant"
        assert msg["content"] == "Let me calculate"
        assert msg["reasoning_content"] == "I need to use the calculator tool"
        assert "tool_calls" in msg
        assert len(msg["tool_calls"]) == 1

    def test_empty_response_no_choices(self):
        """Test 8: Empty response with no choices"""
        ctx = KimiContextManager(session_id="test-session")
        response = Mock(spec=ChatCompletion)
        response.choices = []

        ctx.add_response(response)

        # Should not add anything to working_contents
        assert len(ctx.working_contents) == 0

    def test_invalid_response_type(self):
        """Test 9: Invalid response type (not ChatCompletion)"""
        ctx = KimiContextManager(session_id="test-session")
        response = {"invalid": "response"}

        ctx.add_response(response)

        # Should not add anything to working_contents
        assert len(ctx.working_contents) == 0

    def test_response_without_content_and_without_tool_calls(self):
        """Test 10: Response with neither content nor tool_calls"""
        ctx = KimiContextManager(session_id="test-session")
        response = create_mock_response(content=None, tool_calls=None)

        ctx.add_response(response)

        assert len(ctx.working_contents) == 1
        msg = ctx.working_contents[0]

        assert msg["role"] == "assistant"
        # When no tool_calls, content should be included even if None
        assert "content" in msg
        assert msg["content"] is None

    def test_reasoning_content_empty_string(self):
        """Test 11: Reasoning content as empty string should not be added"""
        ctx = KimiContextManager(session_id="test-session")
        response = create_mock_response(
            content="Hello", reasoning_content=""  # Empty string
        )

        ctx.add_response(response)

        assert len(ctx.working_contents) == 1
        msg = ctx.working_contents[0]

        # Empty reasoning_content should not be added
        assert "reasoning_content" not in msg

    def test_reasoning_content_whitespace(self):
        """Test 12: Reasoning content with only whitespace should not be added"""
        ctx = KimiContextManager(session_id="test-session")
        response = create_mock_response(
            content="Hello", reasoning_content="   "  # Only whitespace
        )

        ctx.add_response(response)

        assert len(ctx.working_contents) == 1
        msg = ctx.working_contents[0]

        # Whitespace-only reasoning_content should not be added (after strip)
        assert "reasoning_content" not in msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
