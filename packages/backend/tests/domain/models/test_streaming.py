"""
Tests for streaming domain models.

Demonstrates testing Pydantic models with various field types and validators.
"""

import pytest
from pydantic import ValidationError

from backend.domain.models.streaming import StreamingChunk


# =====================
# StreamingChunk Tests
# =====================

class TestStreamingChunk:
    """Test suite for StreamingChunk model."""

    def test_create_thinking_chunk(self, sample_thinking_chunk):
        """Test creating a thinking chunk."""
        # Arrange & Act
        chunk = StreamingChunk(**sample_thinking_chunk)

        # Assert
        assert chunk.chunk_type == "thinking"
        assert chunk.content == "Let me analyze this step by step..."
        assert chunk.metadata == {"thought": True}
        assert chunk.function_call is None
        assert chunk.thought_signature is None

    def test_create_text_chunk(self, sample_text_chunk):
        """Test creating a text chunk."""
        # Arrange & Act
        chunk = StreamingChunk(**sample_text_chunk)

        # Assert
        assert chunk.chunk_type == "text"
        assert chunk.content == "The answer is 42."
        assert chunk.metadata == {}

    def test_create_function_call_chunk(self, sample_function_call_chunk):
        """Test creating a function call chunk."""
        # Arrange & Act
        chunk = StreamingChunk(**sample_function_call_chunk)

        # Assert
        assert chunk.chunk_type == "function_call"
        assert chunk.content == "calculate"
        assert chunk.function_call is not None
        assert chunk.function_call["name"] == "calculate"
        assert chunk.function_call["args"] == {"expression": "2 + 2"}

    def test_streaming_chunk_with_minimal_fields(self):
        """Test creating chunk with only required fields."""
        # Arrange & Act
        chunk = StreamingChunk(
            chunk_type="text",
            content="Hello"
        )

        # Assert
        assert chunk.chunk_type == "text"
        assert chunk.content == "Hello"
        assert chunk.metadata == {}  # Default factory dict
        assert chunk.function_call is None
        assert chunk.thought_signature is None

    def test_streaming_chunk_rejects_invalid_type(self):
        """Test that invalid chunk_type is rejected."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            StreamingChunk(
                chunk_type="invalid_type",  # type: ignore
                content="Test"
            )

        # Verify error is about chunk_type
        errors = exc_info.value.errors()
        assert any("chunk_type" in str(error) for error in errors)

    def test_streaming_chunk_with_thought_signature(self):
        """Test chunk with thought signature (Gemini-specific)."""
        # Arrange
        signature = b"cryptographic_signature_bytes"

        # Act
        chunk = StreamingChunk(
            chunk_type="thinking",
            content="Analyzing...",
            thought_signature=signature
        )

        # Assert
        assert chunk.thought_signature == signature
        assert isinstance(chunk.thought_signature, bytes)

    def test_streaming_chunk_metadata_is_dict(self):
        """Test that metadata field accepts dict."""
        # Arrange
        metadata = {
            "provider": "google",
            "model": "gemini-2.0-flash-thinking-exp",
            "temperature": 0.7
        }

        # Act
        chunk = StreamingChunk(
            chunk_type="text",
            content="Response",
            metadata=metadata
        )

        # Assert
        assert chunk.metadata == metadata
        assert isinstance(chunk.metadata, dict)

    def test_streaming_chunk_content_can_be_empty(self):
        """Test that content can be empty string."""
        # Arrange & Act
        chunk = StreamingChunk(
            chunk_type="text",
            content=""
        )

        # Assert
        assert chunk.content == ""

    def test_streaming_chunk_serialization(self):
        """Test chunk can be serialized to dict."""
        # Arrange
        chunk = StreamingChunk(
            chunk_type="function_call",
            content="get_weather",
            metadata={"provider": "google"},
            function_call={"name": "get_weather", "args": {"city": "Tokyo"}}
        )

        # Act
        serialized = chunk.model_dump()

        # Assert
        assert isinstance(serialized, dict)
        assert serialized["chunk_type"] == "function_call"
        assert serialized["content"] == "get_weather"
        assert serialized["metadata"] == {"provider": "google"}
        assert serialized["function_call"]["name"] == "get_weather"


# =====================
# Parametrized Tests
# =====================

class TestStreamingChunkParametrized:
    """Parametrized tests for streaming chunks."""

    @pytest.mark.parametrize("chunk_type", ["thinking", "text", "function_call"])
    def test_valid_chunk_types(self, chunk_type):
        """Test all valid chunk types are accepted."""
        # Arrange & Act
        chunk = StreamingChunk(
            chunk_type=chunk_type,  # type: ignore
            content="Test content"
        )

        # Assert
        assert chunk.chunk_type == chunk_type

    @pytest.mark.parametrize("content", [
        "Simple text",
        "",  # Empty string
        "Unicode 世界 🌍",
        "Line 1\nLine 2",
        "A" * 10000,  # Long content
    ])
    def test_various_content_formats(self, content):
        """Test chunks with various content formats."""
        # Arrange & Act
        chunk = StreamingChunk(
            chunk_type="text",
            content=content
        )

        # Assert
        assert chunk.content == content


# =====================
# Edge Cases
# =====================

class TestStreamingChunkEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_function_call_chunk_without_function_call_field(self):
        """Test that function_call chunk can exist without function_call field."""
        # This is valid - the field is optional
        # Arrange & Act
        chunk = StreamingChunk(
            chunk_type="function_call",
            content="function_name"
        )

        # Assert
        assert chunk.chunk_type == "function_call"
        assert chunk.function_call is None  # Optional field

    def test_chunk_with_complex_metadata(self):
        """Test chunk with complex nested metadata."""
        # Arrange
        complex_metadata = {
            "level1": {
                "level2": {
                    "level3": "deep value"
                }
            },
            "list_field": [1, 2, 3],
            "mixed": ["string", 123, {"key": "value"}]
        }

        # Act
        chunk = StreamingChunk(
            chunk_type="text",
            content="Test",
            metadata=complex_metadata
        )

        # Assert
        assert chunk.metadata == complex_metadata
        assert chunk.metadata["level1"]["level2"]["level3"] == "deep value"

    def test_chunk_immutability_after_creation(self):
        """Test that chunk fields can be modified (Pydantic is not frozen by default)."""
        # Note: If you want immutability, add `frozen=True` to Config
        # Arrange
        chunk = StreamingChunk(
            chunk_type="text",
            content="Original"
        )

        # Act - Modify content
        chunk.content = "Modified"

        # Assert
        assert chunk.content == "Modified"

    def test_chunk_with_none_values_for_optional_fields(self):
        """Test chunk with explicit None for optional fields."""
        # Arrange & Act
        chunk = StreamingChunk(
            chunk_type="text",
            content="Test",
            metadata={},
            function_call=None,
            thought_signature=None
        )

        # Assert
        assert chunk.function_call is None
        assert chunk.thought_signature is None
        assert chunk.metadata == {}
