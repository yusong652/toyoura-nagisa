"""
Tests for streaming models - Application layer data structures.

Tests StreamingState and ConversationResult models used by Agent.
"""

import pytest
from backend.application.services.streaming_models import (
    StreamingState,
    ConversationResult,
)
from backend.domain.models.streaming import StreamingChunk
from backend.domain.models.messages import AssistantMessage


class TestStreamingState:
    """Test StreamingState model."""

    def test_create_streaming_state(self):
        """Test creating a StreamingState with default values."""
        # Arrange & Act
        state = StreamingState(message_id="msg_123")

        # Assert
        assert state.message_id == "msg_123"
        assert state.collected_chunks == []
        assert state.thinking_buffer == ""
        assert state.text_buffer == ""
        assert state.last_raw_response is None

    def test_add_thinking_chunk(self):
        """Test adding a thinking chunk updates thinking buffer."""
        # Arrange
        state = StreamingState(message_id="msg_123")
        chunk = StreamingChunk(chunk_type="thinking", content="Let me think...")

        # Act
        state.add_chunk(chunk)

        # Assert
        assert len(state.collected_chunks) == 1
        assert state.thinking_buffer == "Let me think..."
        assert state.text_buffer == ""

    def test_add_text_chunk(self):
        """Test adding a text chunk updates text buffer."""
        # Arrange
        state = StreamingState(message_id="msg_123")
        chunk = StreamingChunk(chunk_type="text", content="Hello world")

        # Act
        state.add_chunk(chunk)

        # Assert
        assert len(state.collected_chunks) == 1
        assert state.thinking_buffer == ""
        assert state.text_buffer == "Hello world"

    def test_add_multiple_chunks(self):
        """Test adding multiple chunks accumulates content."""
        # Arrange
        state = StreamingState(message_id="msg_123")
        chunks = [
            StreamingChunk(chunk_type="thinking", content="First, "),
            StreamingChunk(chunk_type="thinking", content="I need to think. "),
            StreamingChunk(chunk_type="text", content="The answer "),
            StreamingChunk(chunk_type="text", content="is 42."),
        ]

        # Act
        for chunk in chunks:
            state.add_chunk(chunk)

        # Assert
        assert len(state.collected_chunks) == 4
        assert state.thinking_buffer == "First, I need to think. "
        assert state.text_buffer == "The answer is 42."

    def test_get_content_blocks_with_both_types(self):
        """Test getting content blocks with both thinking and text."""
        # Arrange
        state = StreamingState(message_id="msg_123")
        state.add_chunk(StreamingChunk(chunk_type="thinking", content="Analyzing..."))
        state.add_chunk(StreamingChunk(chunk_type="text", content="Result: success"))

        # Act
        blocks = state.get_content_blocks()

        # Assert
        assert len(blocks) == 2
        assert blocks[0] == {"type": "thinking", "thinking": "Analyzing..."}
        assert blocks[1] == {"type": "text", "text": "Result: success"}

    def test_get_content_blocks_thinking_only(self):
        """Test getting content blocks with only thinking content."""
        # Arrange
        state = StreamingState(message_id="msg_123")
        state.add_chunk(StreamingChunk(chunk_type="thinking", content="Just thinking"))

        # Act
        blocks = state.get_content_blocks()

        # Assert
        assert len(blocks) == 1
        assert blocks[0] == {"type": "thinking", "thinking": "Just thinking"}

    def test_get_content_blocks_text_only(self):
        """Test getting content blocks with only text content."""
        # Arrange
        state = StreamingState(message_id="msg_123")
        state.add_chunk(StreamingChunk(chunk_type="text", content="Just text"))

        # Act
        blocks = state.get_content_blocks()

        # Assert
        assert len(blocks) == 1
        assert blocks[0] == {"type": "text", "text": "Just text"}

    def test_get_content_blocks_empty(self):
        """Test getting content blocks with no content."""
        # Arrange
        state = StreamingState(message_id="msg_123")

        # Act
        blocks = state.get_content_blocks()

        # Assert
        assert blocks == []


class TestConversationResult:
    """Test ConversationResult model."""

    def test_create_conversation_result(self):
        """Test creating ConversationResult with default values."""
        # Arrange
        message = AssistantMessage(
            role="assistant",
            content=[{"type": "text", "text": "Hello"}]
        )

        # Act
        result = ConversationResult(final_message=message)

        # Assert
        assert result.final_message == message
        assert result.streaming_message_id is None
        assert result.interrupted is False
        assert result.iteration_count == 0

    def test_create_conversation_result_with_all_fields(self):
        """Test creating ConversationResult with all fields set."""
        # Arrange
        message = AssistantMessage(
            role="assistant",
            content=[{"type": "text", "text": "Hello"}]
        )

        # Act
        result = ConversationResult(
            final_message=message,
            streaming_message_id="msg_456",
            interrupted=True,
            iteration_count=3
        )

        # Assert
        assert result.final_message == message
        assert result.streaming_message_id == "msg_456"
        assert result.interrupted is True
        assert result.iteration_count == 3

    def test_conversation_result_with_interruption(self):
        """Test ConversationResult representing an interrupted conversation."""
        # Arrange
        message = AssistantMessage(
            role="assistant",
            content=[{"type": "text", "text": "Partial response"}]
        )

        # Act
        result = ConversationResult(
            final_message=message,
            interrupted=True,
            iteration_count=1
        )

        # Assert
        assert result.interrupted is True
        assert result.iteration_count == 1

    def test_conversation_result_with_iterations(self):
        """Test ConversationResult with multiple tool calling iterations."""
        # Arrange
        message = AssistantMessage(
            role="assistant",
            content=[{"type": "text", "text": "Final answer after tool calls"}]
        )

        # Act
        result = ConversationResult(
            final_message=message,
            iteration_count=5
        )

        # Assert
        assert result.iteration_count == 5
        assert result.interrupted is False
