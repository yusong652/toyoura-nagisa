"""
Test suite for OpenAI context_manager.add_response() refactoring

This test file captures the current behavior of add_response() before refactoring,
then validates that the refactored version produces identical results.

Tests cover OpenAI Responses API specific features:
- Multiple output types: message, reasoning, function_call
- One response producing multiple context items
- Reasoning-function_call pairing mechanism
- Removal of function_call_output dead code branch
"""

import json
from typing import Any, Dict, List, Optional
from unittest.mock import Mock

import pytest
from openai.types.responses import Response

from backend.infrastructure.llm.providers.openai.context_manager import (
    OpenAIContextManager,
)


# ============================================================================
# Mock Helper Functions
# ============================================================================


def create_mock_response(
    output_items: List[Dict[str, Any]]
) -> Response:
    """
    Create a mock OpenAI Response object for testing.

    Args:
        output_items: List of output item dicts with type and content

    Returns:
        Mock Response object
    """
    response = Mock(spec=Response)

    # Create mock output items
    mock_items = []
    for item_data in output_items:
        item = Mock()

        # Set model_dump to return the item data
        item.model_dump = Mock(return_value=item_data)

        mock_items.append(item)

    response.output = mock_items
    return response


# ============================================================================
# Test Cases
# ============================================================================


class TestOpenAIContextManagerAddResponse:
    """Test current behavior of OpenAI context_manager.add_response()"""

    def test_basic_message_response(self):
        """Test 1: Basic message response with text content"""
        ctx = OpenAIContextManager(session_id="test-session")

        response = create_mock_response([
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {"type": "output_text", "text": "Hello, world!"}
                ]
            }
        ])

        ctx.add_response(response)

        assert len(ctx.working_contents) == 1
        msg = ctx.working_contents[0]

        assert msg["role"] == "assistant"
        assert msg["content"] == "Hello, world!"

    def test_message_with_multiple_text_blocks(self):
        """Test 2: Message with multiple text blocks"""
        ctx = OpenAIContextManager(session_id="test-session")

        response = create_mock_response([
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {"type": "output_text", "text": "First part. "},
                    {"type": "output_text", "text": "Second part."}
                ]
            }
        ])

        ctx.add_response(response)

        assert len(ctx.working_contents) == 1
        assert ctx.working_contents[0]["content"] == "First part. Second part."

    def test_message_with_empty_content(self):
        """Test 3: Message with empty content list"""
        ctx = OpenAIContextManager(session_id="test-session")

        response = create_mock_response([
            {
                "type": "message",
                "role": "assistant",
                "content": []
            }
        ])

        ctx.add_response(response)

        assert len(ctx.working_contents) == 1
        assert ctx.working_contents[0]["content"] == ""

    def test_reasoning_item(self):
        """Test 4: Reasoning item with ID and summary"""
        ctx = OpenAIContextManager(session_id="test-session")

        response = create_mock_response([
            {
                "type": "reasoning",
                "id": "reasoning_123",
                "summary": [{"type": "text", "text": "Let me think..."}]
            }
        ])

        ctx.add_response(response)

        assert len(ctx.working_contents) == 1
        reasoning = ctx.working_contents[0]

        assert reasoning["type"] == "reasoning"
        assert reasoning["id"] == "reasoning_123"
        assert reasoning["summary"] == [{"type": "text", "text": "Let me think..."}]

    def test_reasoning_with_empty_summary(self):
        """Test 5: Reasoning with empty summary (should still be kept for pairing)"""
        ctx = OpenAIContextManager(session_id="test-session")

        response = create_mock_response([
            {
                "type": "reasoning",
                "id": "reasoning_456",
                "summary": []
            }
        ])

        ctx.add_response(response)

        assert len(ctx.working_contents) == 1
        reasoning = ctx.working_contents[0]

        assert reasoning["type"] == "reasoning"
        assert reasoning["id"] == "reasoning_456"
        assert reasoning["summary"] == []

    def test_reasoning_without_id_skipped(self):
        """Test 6: Reasoning without ID should be skipped"""
        ctx = OpenAIContextManager(session_id="test-session")

        response = create_mock_response([
            {
                "type": "reasoning",
                "summary": [{"type": "text", "text": "Some reasoning"}]
                # No id field
            }
        ])

        ctx.add_response(response)

        # Should not add reasoning without ID
        assert len(ctx.working_contents) == 0

    def test_function_call_item(self):
        """Test 7: Function call with dual ID system"""
        ctx = OpenAIContextManager(session_id="test-session")

        response = create_mock_response([
            {
                "type": "function_call",
                "id": "fc_123",
                "call_id": "call_456",
                "name": "get_weather",
                "arguments": '{"city": "Tokyo"}'
            }
        ])

        ctx.add_response(response)

        assert len(ctx.working_contents) == 1
        fc = ctx.working_contents[0]

        assert fc["type"] == "function_call"
        assert fc["id"] == "fc_123"
        assert fc["call_id"] == "call_456"
        assert fc["name"] == "get_weather"
        assert fc["arguments"] == '{"city": "Tokyo"}'

    def test_function_call_with_dict_arguments(self):
        """Test 8: Function call with dict arguments (should be JSON serialized)"""
        ctx = OpenAIContextManager(session_id="test-session")

        response = create_mock_response([
            {
                "type": "function_call",
                "id": "fc_789",
                "call_id": "call_101",
                "name": "calculator",
                "arguments": {"expr": "2+2"}  # dict instead of string
            }
        ])

        ctx.add_response(response)

        assert len(ctx.working_contents) == 1
        fc = ctx.working_contents[0]

        # Should be JSON serialized
        assert fc["arguments"] == '{"expr": "2+2"}'

    def test_function_call_with_none_arguments(self):
        """Test 9: Function call with None arguments (should become empty dict)"""
        ctx = OpenAIContextManager(session_id="test-session")

        response = create_mock_response([
            {
                "type": "function_call",
                "id": "fc_111",
                "call_id": "call_222",
                "name": "no_args_tool",
                "arguments": None
            }
        ])

        ctx.add_response(response)

        assert len(ctx.working_contents) == 1
        fc = ctx.working_contents[0]

        assert fc["arguments"] == "{}"

    def test_function_call_missing_arguments(self):
        """Test 10: Function call without arguments field"""
        ctx = OpenAIContextManager(session_id="test-session")

        response = create_mock_response([
            {
                "type": "function_call",
                "id": "fc_333",
                "call_id": "call_444",
                "name": "tool_name"
                # No arguments field
            }
        ])

        ctx.add_response(response)

        assert len(ctx.working_contents) == 1
        fc = ctx.working_contents[0]

        # Should default to empty dict
        assert fc["arguments"] == "{}"

    def test_multiple_items_in_response(self):
        """Test 11: Response with multiple output items (reasoning + function_call)"""
        ctx = OpenAIContextManager(session_id="test-session")

        response = create_mock_response([
            {
                "type": "reasoning",
                "id": "reasoning_555",
                "summary": [{"type": "text", "text": "I need to call a tool"}]
            },
            {
                "type": "function_call",
                "id": "fc_666",
                "call_id": "call_777",
                "name": "search",
                "arguments": '{"query": "test"}'
            }
        ])

        ctx.add_response(response)

        # Should add both items
        assert len(ctx.working_contents) == 2

        # First item is reasoning
        assert ctx.working_contents[0]["type"] == "reasoning"
        assert ctx.working_contents[0]["id"] == "reasoning_555"

        # Second item is function_call
        assert ctx.working_contents[1]["type"] == "function_call"
        assert ctx.working_contents[1]["id"] == "fc_666"

    def test_function_call_output_not_processed(self):
        """Test 12: function_call_output should NOT be processed (dead code removed)"""
        ctx = OpenAIContextManager(session_id="test-session")

        # This would be the old dead code branch scenario
        response = create_mock_response([
            {
                "type": "function_call_output",
                "call_id": "call_888",
                "output": "Some result"
            }
        ])

        ctx.add_response(response)

        # Should NOT add function_call_output to working_contents
        # (previously this was dead code, now it's correctly ignored)
        assert len(ctx.working_contents) == 0

    def test_empty_response(self):
        """Test 13: Empty response with no output"""
        ctx = OpenAIContextManager(session_id="test-session")

        response = Mock(spec=Response)
        response.output = []

        ctx.add_response(response)

        assert len(ctx.working_contents) == 0

    def test_invalid_response_type(self):
        """Test 14: Invalid response type (not Response object)"""
        ctx = OpenAIContextManager(session_id="test-session")

        response = {"invalid": "response"}

        ctx.add_response(response)

        assert len(ctx.working_contents) == 0

    def test_message_without_role(self):
        """Test 15: Message without role should be skipped"""
        ctx = OpenAIContextManager(session_id="test-session")

        response = create_mock_response([
            {
                "type": "message",
                # No role field
                "content": [{"type": "output_text", "text": "Hello"}]
            }
        ])

        ctx.add_response(response)

        # Should skip message without role
        assert len(ctx.working_contents) == 0

    def test_message_with_string_content(self):
        """Test 16: Message with string content instead of list"""
        ctx = OpenAIContextManager(session_id="test-session")

        response = create_mock_response([
            {
                "type": "message",
                "role": "assistant",
                "content": "Plain string content"
            }
        ])

        ctx.add_response(response)

        assert len(ctx.working_contents) == 1
        assert ctx.working_contents[0]["content"] == "Plain string content"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
