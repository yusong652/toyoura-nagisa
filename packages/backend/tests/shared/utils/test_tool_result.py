"""
Tests for ToolResult - tool response utilities.

Tests ANSI code cleaning, success/error response helpers.
"""

import pytest
from backend.shared.utils.tool_result import (
    ToolResult,
    success_response,
    error_response,
    user_rejected_response,
    strip_ansi_codes,
    clean_llm_content,
)


class TestAnsiCleaning:
    """Test ANSI escape sequence cleaning."""

    def test_strip_ansi_codes_with_color(self):
        """Test removing ANSI color codes from text."""
        # Arrange
        text = "\x1b[36magent-20251104-beta\x1b[39m"

        # Act
        result = strip_ansi_codes(text)

        # Assert
        assert result == "agent-20251104-beta"

    def test_strip_ansi_codes_multiple_codes(self):
        """Test removing multiple ANSI codes from text."""
        # Arrange
        text = "\x1b[1m\x1b[32mSuccess:\x1b[0m Operation complete"

        # Act
        result = strip_ansi_codes(text)

        # Assert
        assert result == "Success: Operation complete"

    def test_strip_ansi_codes_no_codes(self):
        """Test that plain text is unchanged."""
        # Arrange
        text = "Plain text without ANSI codes"

        # Act
        result = strip_ansi_codes(text)

        # Assert
        assert result == "Plain text without ANSI codes"

    def test_strip_ansi_codes_empty_string(self):
        """Test that empty string is handled."""
        # Arrange
        text = ""

        # Act
        result = strip_ansi_codes(text)

        # Assert
        assert result == ""

    def test_clean_llm_content_string(self):
        """Test cleaning ANSI codes from simple string llm_content."""
        # Arrange
        content = "\x1b[36mHello\x1b[39m World"

        # Act
        result = clean_llm_content(content)

        # Assert
        assert result == "Hello World"

    def test_clean_llm_content_parts_structure(self):
        """Test cleaning ANSI codes from parts-based llm_content."""
        # Arrange
        content = {
            "parts": [
                {"type": "text", "text": "\x1b[36mHello\x1b[39m World"},
                {"type": "text", "text": "\x1b[1mBold text\x1b[0m"}
            ]
        }

        # Act
        result = clean_llm_content(content)

        # Assert
        assert result["parts"][0]["text"] == "Hello World"
        assert result["parts"][1]["text"] == "Bold text"

    def test_clean_llm_content_none(self):
        """Test that None content is handled."""
        # Arrange
        content = None

        # Act
        result = clean_llm_content(content)

        # Assert
        assert result is None

    def test_clean_llm_content_preserves_structure(self):
        """Test that clean_llm_content preserves non-text parts."""
        # Arrange
        content = {
            "parts": [
                {"type": "text", "text": "\x1b[36mText\x1b[39m"},
                {"type": "image", "url": "http://example.com/image.png"}
            ]
        }

        # Act
        result = clean_llm_content(content)

        # Assert
        assert len(result["parts"]) == 2
        assert result["parts"][0]["text"] == "Text"
        assert result["parts"][1] == {"type": "image", "url": "http://example.com/image.png"}


class TestToolResult:
    """Test ToolResult Pydantic model."""

    def test_create_success_tool_result(self):
        """Test creating a success ToolResult."""
        # Arrange & Act
        result = ToolResult(
            status="success",
            message="Operation completed",
            llm_content={"parts": [{"type": "text", "text": "Done"}]},
            data={"count": 5}
        )

        # Assert
        assert result.status == "success"
        assert result.message == "Operation completed"
        assert result.llm_content == {"parts": [{"type": "text", "text": "Done"}]}
        assert result.data == {"count": 5}

    def test_create_error_tool_result(self):
        """Test creating an error ToolResult."""
        # Arrange & Act
        result = ToolResult(
            status="error",
            message="Operation failed",
            llm_content={"parts": [{"type": "text", "text": "<error>Failed</error>"}]}
        )

        # Assert
        assert result.status == "error"
        assert result.message == "Operation failed"
        assert result.llm_content == {"parts": [{"type": "text", "text": "<error>Failed</error>"}]}
        assert result.data is None

    def test_tool_result_extra_fields_allowed(self):
        """Test that extra fields are allowed via model_config."""
        # Arrange & Act
        result = ToolResult(
            status="success",
            message="Done",
            extra_field="extra_value"
        )

        # Assert - extra field is preserved
        assert result.model_dump()["extra_field"] == "extra_value"


class TestSuccessResponse:
    """Test success_response helper function."""

    def test_success_response_basic(self):
        """Test basic success response."""
        # Arrange & Act
        result = success_response("File read successfully")

        # Assert
        assert result["status"] == "success"
        assert result["message"] == "File read successfully"
        assert result["llm_content"] is None
        assert result["data"] is None

    def test_success_response_with_llm_content(self):
        """Test success response with llm_content."""
        # Arrange & Act
        result = success_response(
            "Command executed",
            llm_content={"parts": [{"type": "text", "text": "Output here"}]}
        )

        # Assert
        assert result["status"] == "success"
        assert result["message"] == "Command executed"
        assert result["llm_content"] == {"parts": [{"type": "text", "text": "Output here"}]}

    def test_success_response_with_data(self):
        """Test success response with data fields."""
        # Arrange & Act
        result = success_response(
            "Found matches",
            file_count=3,
            total_matches=15
        )

        # Assert
        assert result["status"] == "success"
        assert result["data"]["file_count"] == 3
        assert result["data"]["total_matches"] == 15

    def test_success_response_cleans_ansi(self):
        """Test that success_response automatically cleans ANSI codes."""
        # Arrange & Act
        result = success_response(
            "Done",
            llm_content={"parts": [{"type": "text", "text": "\x1b[36mOutput\x1b[39m"}]}
        )

        # Assert
        assert result["llm_content"]["parts"][0]["text"] == "Output"


class TestErrorResponse:
    """Test error_response helper function."""

    def test_error_response_auto_wraps_in_error_tags(self):
        """Test that error_response auto-wraps message in <error> tags."""
        # Arrange & Act
        result = error_response("File not found")

        # Assert
        assert result["status"] == "error"
        assert result["message"] == "File not found"
        assert result["llm_content"]["parts"][0]["text"] == "<error>File not found</error>"

    def test_error_response_with_custom_llm_content(self):
        """Test error response with custom llm_content."""
        # Arrange & Act
        result = error_response(
            "API error",
            llm_content={"parts": [{"type": "text", "text": "Custom error context"}]}
        )

        # Assert
        assert result["status"] == "error"
        assert result["message"] == "API error"
        assert result["llm_content"]["parts"][0]["text"] == "Custom error context"

    def test_error_response_with_data(self):
        """Test error response with additional error context data."""
        # Arrange & Act
        result = error_response(
            "Validation failed",
            error_code=400,
            details="Invalid input"
        )

        # Assert
        assert result["status"] == "error"
        assert result["data"]["error_code"] == 400
        assert result["data"]["details"] == "Invalid input"

    def test_error_response_cleans_ansi(self):
        """Test that error_response automatically cleans ANSI codes."""
        # Arrange & Act
        result = error_response(
            "Error",
            llm_content={"parts": [{"type": "text", "text": "\x1b[31mError\x1b[39m"}]}
        )

        # Assert
        assert result["llm_content"]["parts"][0]["text"] == "Error"


class TestUserRejectedResponse:
    """Test user_rejected_response helper function."""

    def test_user_rejected_response_basic(self):
        """Test basic user rejection response."""
        # Arrange & Act
        result = user_rejected_response()

        # Assert
        assert result["status"] == "error"
        assert "user doesn't want to proceed" in result["message"]
        assert "STOP what you are doing" in result["message"]
        assert "<error>" in result["llm_content"]["parts"][0]["text"]

    def test_user_rejected_response_with_user_message(self):
        """Test user rejection with user's explanation."""
        # Arrange & Act
        result = user_rejected_response(user_message="This looks dangerous")

        # Assert
        assert result["status"] == "error"
        assert "This looks dangerous" in result["message"]
        assert "<error>" in result["llm_content"]["parts"][0]["text"]

    def test_user_rejected_response_without_stop_instruction(self):
        """Test user rejection for reject_and_tell case."""
        # Arrange & Act
        result = user_rejected_response(
            user_message="Do it differently",
            include_stop_instruction=False
        )

        # Assert
        assert result["status"] == "error"
        assert "Do it differently" in result["message"]
        assert "proceed based on the user's instruction" in result["message"]
        assert "STOP what you are doing" not in result["message"]

    def test_user_rejected_response_reject_and_tell(self):
        """Test that reject_and_tell case has different instruction."""
        # Arrange & Act
        result_reject = user_rejected_response(include_stop_instruction=True)
        result_reject_and_tell = user_rejected_response(include_stop_instruction=False)

        # Assert
        assert "STOP" in result_reject["message"]
        assert "STOP" not in result_reject_and_tell["message"]
        assert "proceed based" in result_reject_and_tell["message"]
