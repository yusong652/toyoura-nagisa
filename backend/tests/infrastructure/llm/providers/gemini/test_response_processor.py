"""
Unit tests for Gemini response processor multipart text extraction.

Tests the new multipart text handling functionality that collects all text parts
from Gemini API responses instead of only the first one.
"""

import pytest
from typing import List, Dict, Any
from unittest.mock import Mock
from backend.infrastructure.llm.providers.gemini.response_processor import GeminiResponseProcessor


class MockPart:
    """Mock Gemini API Part object"""
    def __init__(self, text: str = None, thought: bool = False, function_call=None):
        self.text = text
        self.thought = thought
        self.function_call = function_call


class MockContent:
    """Mock Gemini API Content object"""
    def __init__(self, parts: List[MockPart]):
        self.parts = parts


class MockCandidate:
    """Mock Gemini API Candidate object"""
    def __init__(self, content: MockContent, thought: str = None):
        self.content = content
        self.thought = thought


class MockResponse:
    """Mock Gemini API Response object"""
    def __init__(self, candidates: List[MockCandidate]):
        self.candidates = candidates


class TestMultipartTextExtraction:
    """Test cases for multipart text extraction"""

    def test_single_text_part(self):
        """Test that single text part is correctly stored"""
        # Arrange
        part = MockPart(text="Single text part")
        content = MockContent(parts=[part])
        candidate = MockCandidate(content=content)
        response = MockResponse(candidates=[candidate])

        # Act
        result = GeminiResponseProcessor.format_response_for_storage(response)

        # Assert
        assert result.role == "assistant"
        assert isinstance(result.content, list)
        assert len(result.content) == 1
        assert result.content[0]["type"] == "text"
        assert result.content[0]["text"] == "Single text part"

    def test_multiple_text_parts(self):
        """Test that multiple text parts are all stored as separate blocks"""
        # Arrange
        parts = [
            MockPart(text="First text part"),
            MockPart(text="Second text part"),
            MockPart(text="Third text part")
        ]
        content = MockContent(parts=parts)
        candidate = MockCandidate(content=content)
        response = MockResponse(candidates=[candidate])

        # Act
        result = GeminiResponseProcessor.format_response_for_storage(response)

        # Assert
        assert result.role == "assistant"
        assert isinstance(result.content, list)
        assert len(result.content) == 3  # All three parts should be saved

        # Check each part
        for i, expected_text in enumerate(["First text part", "Second text part", "Third text part"]):
            assert result.content[i]["type"] == "text"
            assert result.content[i]["text"] == expected_text

    def test_text_with_thinking_parts(self):
        """Test that thinking parts are excluded but text parts are kept"""
        # Arrange
        parts = [
            MockPart(text="Thinking content", thought=True),
            MockPart(text="Actual response text 1"),
            MockPart(text="More thinking", thought=True),
            MockPart(text="Actual response text 2")
        ]
        content = MockContent(parts=parts)
        candidate = MockCandidate(content=content)
        response = MockResponse(candidates=[candidate])

        # Act
        result = GeminiResponseProcessor.format_response_for_storage(response)

        # Assert
        # Only non-thinking text parts should be in content
        text_parts = [item for item in result.content if item.get("type") == "text"]
        assert len(text_parts) == 2
        assert text_parts[0]["text"] == "Actual response text 1"
        assert text_parts[1]["text"] == "Actual response text 2"

    def test_text_tool_text_interleaving(self):
        """Test that text and tool_use parts maintain correct order"""
        # Arrange
        mock_function_call = Mock()
        mock_function_call.name = "read_file"
        mock_function_call.args = {"path": "file.py"}
        mock_function_call.id = "call_123"

        parts = [
            MockPart(text="I'll read the file first"),
            MockPart(function_call=mock_function_call),
            MockPart(text="Analysis complete")
        ]
        content = MockContent(parts=parts)
        candidate = MockCandidate(content=content)
        response = MockResponse(candidates=[candidate])

        # Act
        result = GeminiResponseProcessor.format_response_for_storage(response)

        # Assert
        assert len(result.content) == 3

        # Check order is preserved
        assert result.content[0]["type"] == "tool_use"
        assert result.content[0]["name"] == "read_file"

        assert result.content[1]["type"] == "text"
        assert result.content[1]["text"] == "I'll read the file first"

        assert result.content[2]["type"] == "text"
        assert result.content[2]["text"] == "Analysis complete"

    def test_empty_text_parts_filtered(self):
        """Test that empty text parts are filtered out"""
        # Arrange
        parts = [
            MockPart(text="Valid text"),
            MockPart(text="   "),  # Whitespace only
            MockPart(text=""),  # Empty
            MockPart(text="Another valid text")
        ]
        content = MockContent(parts=parts)
        candidate = MockCandidate(content=content)
        response = MockResponse(candidates=[candidate])

        # Act
        result = GeminiResponseProcessor.format_response_for_storage(response)

        # Assert
        # Only non-empty text parts should be saved
        text_parts = [item for item in result.content if item.get("type") == "text"]
        assert len(text_parts) == 2
        assert text_parts[0]["text"] == "Valid text"
        assert text_parts[1]["text"] == "Another valid text"

    def test_top_level_thinking(self):
        """Test that top-level thinking is handled separately from parts"""
        # Arrange
        parts = [
            MockPart(text="Response text 1"),
            MockPart(text="Response text 2")
        ]
        content = MockContent(parts=parts)
        candidate = MockCandidate(content=content, thought="Top-level thinking content")
        response = MockResponse(candidates=[candidate])

        # Act
        result = GeminiResponseProcessor.format_response_for_storage(response)

        # Assert
        # Top-level thinking should be in thinking block
        thinking_blocks = [item for item in result.content if item.get("type") == "thinking"]
        assert len(thinking_blocks) == 1
        assert "Top-level thinking content" in thinking_blocks[0]["thinking"]

        # Text parts should still be separate
        text_parts = [item for item in result.content if item.get("type") == "text"]
        assert len(text_parts) == 2


class TestExtractCombinedText:
    """Test cases for extract_combined_text_from_content utility"""

    def test_extract_single_text_part(self):
        """Test extraction from single text part"""
        content = [
            {"type": "text", "text": "Single part"}
        ]
        result = GeminiResponseProcessor.extract_combined_text_from_content(content)
        assert result == "Single part"

    def test_extract_multiple_text_parts(self):
        """Test extraction and combination of multiple text parts"""
        content = [
            {"type": "text", "text": "Part 1"},
            {"type": "text", "text": "Part 2"},
            {"type": "text", "text": "Part 3"}
        ]
        result = GeminiResponseProcessor.extract_combined_text_from_content(content)
        assert result == "Part 1Part 2Part 3"

    def test_extract_with_tool_use(self):
        """Test that tool_use blocks are skipped during extraction"""
        content = [
            {"type": "text", "text": "Before tool"},
            {"type": "tool_use", "name": "read_file", "input": {}},
            {"type": "text", "text": "After tool"}
        ]
        result = GeminiResponseProcessor.extract_combined_text_from_content(content)
        assert result == "Before toolAfter tool"

    def test_extract_with_thinking(self):
        """Test that thinking blocks are skipped during extraction"""
        content = [
            {"type": "thinking", "thinking": "Internal reasoning"},
            {"type": "text", "text": "User-facing text"}
        ]
        result = GeminiResponseProcessor.extract_combined_text_from_content(content)
        assert result == "User-facing text"

    def test_extract_empty_content(self):
        """Test extraction from empty content array"""
        content = []
        result = GeminiResponseProcessor.extract_combined_text_from_content(content)
        assert result == ""

    def test_extract_no_text_parts(self):
        """Test extraction when no text parts exist"""
        content = [
            {"type": "tool_use", "name": "read_file"},
            {"type": "thinking", "thinking": "thoughts"}
        ]
        result = GeminiResponseProcessor.extract_combined_text_from_content(content)
        assert result == ""


class TestBackwardCompatibility:
    """Test backward compatibility with existing functionality"""

    def test_extract_text_content_still_works(self):
        """Test that extract_text_content method still works with multipart"""
        # Arrange
        parts = [
            MockPart(text="Text 1"),
            MockPart(text="Text 2")
        ]
        content = MockContent(parts=parts)
        candidate = MockCandidate(content=content)
        response = MockResponse(candidates=[candidate])

        # Act
        result = GeminiResponseProcessor.extract_text_content(response)

        # Assert - should combine all text parts
        assert result == "Text 1Text 2"

    def test_empty_response_handling(self):
        """Test that empty responses are handled gracefully"""
        # Arrange
        parts = []
        content = MockContent(parts=parts)
        candidate = MockCandidate(content=content)
        response = MockResponse(candidates=[candidate])

        # Act
        result = GeminiResponseProcessor.format_response_for_storage(response)

        # Assert - should have default empty text
        assert result.role == "assistant"
        assert isinstance(result.content, list)
        assert len(result.content) == 1
        assert result.content[0]["type"] == "text"
        assert result.content[0]["text"] == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
