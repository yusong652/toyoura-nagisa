"""
Tests for message domain models.

This module demonstrates best practices for unit testing:
1. Test one behavior per test function
2. Use descriptive test names (test_<behavior>_<expected_result>)
3. Follow AAA pattern: Arrange, Act, Assert
4. Test both happy paths and edge cases
5. Use fixtures for reusable test data
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from backend.domain.models.messages import (
    BaseMessage,
    UserMessage,
    AssistantMessage,
    ImageMessage,
    VideoMessage,
)


# =====================
# UserMessage Tests
# =====================

class TestUserMessage:
    """Test suite for UserMessage model."""

    def test_create_user_message_with_string_content(self):
        """Test creating a user message with simple string content."""
        # Arrange & Act
        message = UserMessage(content="Hello, world!")

        # Assert
        assert message.role == "user"
        assert message.content == "Hello, world!"
        assert message.id is None  # Optional field defaults to None
        assert message.timestamp is None

    def test_create_user_message_with_all_fields(self, sample_user_message_dict):
        """Test creating a user message with all optional fields provided."""
        # Arrange & Act
        message = UserMessage(**sample_user_message_dict)

        # Assert
        assert message.role == "user"
        assert message.content == "Hello, how are you?"
        assert message.id == "msg_001"
        assert message.timestamp == datetime(2026, 1, 20, 10, 30, 0)

    def test_create_user_message_with_multipart_content(self, sample_multipart_content):
        """Test creating a user message with multipart content (text + image)."""
        # Arrange & Act
        message = UserMessage(content=sample_multipart_content)

        # Assert
        assert message.role == "user"
        assert isinstance(message.content, list)
        assert len(message.content) == 2
        assert message.content[0]["type"] == "text"
        assert message.content[1]["type"] == "image_url"

    def test_user_message_to_dict_conversion(self):
        """Test converting user message to dictionary format."""
        # Arrange
        message = UserMessage(
            content="Test message",
            id="msg_123",
            timestamp=datetime(2026, 1, 20, 12, 0, 0)
        )

        # Act
        result = message.to_dict()

        # Assert
        assert isinstance(result, dict)
        assert result["role"] == "user"
        assert result["content"] == "Test message"
        assert result["id"] == "msg_123"
        assert isinstance(result["timestamp"], datetime)

    def test_user_message_role_cannot_be_changed(self):
        """Test that user message role is fixed to 'user'."""
        # Arrange & Act
        message = UserMessage(content="Hello")

        # Assert
        assert message.role == "user"
        # The role is a literal, so it's always "user"

    def test_user_message_accepts_empty_string_content(self):
        """Test that user message can have empty string content."""
        # Arrange & Act
        message = UserMessage(content="")

        # Assert
        assert message.content == ""
        assert message.role == "user"

    def test_user_message_with_custom_id(self):
        """Test creating user message with custom ID."""
        # Arrange
        custom_id = "custom_msg_12345"

        # Act
        message = UserMessage(content="Test", id=custom_id)

        # Assert
        assert message.id == custom_id


# =====================
# AssistantMessage Tests
# =====================

class TestAssistantMessage:
    """Test suite for AssistantMessage model."""

    def test_create_assistant_message_with_string_content(self):
        """Test creating an assistant message with simple string content."""
        # Arrange & Act
        message = AssistantMessage(content="I can help you with that.")

        # Assert
        assert message.role == "assistant"
        assert message.content == "I can help you with that."

    def test_create_assistant_message_with_all_fields(self, sample_assistant_message_dict):
        """Test creating an assistant message with all fields."""
        # Arrange & Act
        message = AssistantMessage(**sample_assistant_message_dict)

        # Assert
        assert message.role == "assistant"
        assert message.content == "I'm doing well, thank you!"
        assert message.id == "msg_002"
        assert message.timestamp == datetime(2026, 1, 20, 10, 30, 5)

    def test_assistant_message_role_is_fixed(self):
        """Test that assistant message role is always 'assistant'."""
        # Arrange & Act
        message = AssistantMessage(content="Response")

        # Assert
        assert message.role == "assistant"


# =====================
# ImageMessage Tests
# =====================

class TestImageMessage:
    """Test suite for ImageMessage model."""

    def test_create_image_message_with_required_fields(self):
        """Test creating an image message with required fields."""
        # Arrange & Act
        message = ImageMessage(
            content="Image description",
            image_path="/path/to/image.png"
        )

        # Assert
        assert message.role == "image"
        assert message.content == "Image description"
        assert message.image_path == "/path/to/image.png"

    def test_image_message_requires_image_path(self):
        """Test that image message requires image_path field."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ImageMessage(content="Image without path")

        # Verify the error is about missing image_path
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("image_path",) for error in errors)

    def test_image_message_to_dict_includes_image_path(self):
        """Test that to_dict() includes image_path field."""
        # Arrange
        message = ImageMessage(
            content="Test image",
            image_path="/workspace/output.png"
        )

        # Act
        result = message.to_dict()

        # Assert
        assert result["role"] == "image"
        assert result["image_path"] == "/workspace/output.png"


# =====================
# VideoMessage Tests
# =====================

class TestVideoMessage:
    """Test suite for VideoMessage model."""

    def test_create_video_message_with_required_fields(self):
        """Test creating a video message with required fields."""
        # Arrange & Act
        message = VideoMessage(
            content="Video description",
            video_path="/path/to/video.mp4"
        )

        # Assert
        assert message.role == "video"
        assert message.content == "Video description"
        assert message.video_path == "/path/to/video.mp4"

    def test_video_message_requires_video_path(self):
        """Test that video message requires video_path field."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            VideoMessage(content="Video without path")

        # Verify the error is about missing video_path
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("video_path",) for error in errors)


# =====================
# BaseMessage Tests
# =====================

class TestBaseMessage:
    """Test suite for BaseMessage model."""

    def test_base_message_accepts_valid_roles(self):
        """Test that base message accepts all valid role types."""
        # Arrange
        valid_roles = ["user", "assistant", "image", "video"]

        # Act & Assert
        for role in valid_roles:
            message = BaseMessage(role=role, content="Test")  # type: ignore
            assert message.role == role

    def test_base_message_rejects_invalid_role(self):
        """Test that base message rejects invalid role values."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            BaseMessage(role="invalid_role", content="Test")  # type: ignore

        # Verify validation error
        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert "role" in str(errors[0])

    def test_base_message_timestamp_is_optional(self):
        """Test that timestamp field is optional."""
        # Arrange & Act
        message = BaseMessage(role="user", content="Test")  # type: ignore

        # Assert
        assert message.timestamp is None

    def test_base_message_with_custom_timestamp(self):
        """Test creating base message with custom timestamp."""
        # Arrange
        custom_time = datetime(2026, 1, 20, 15, 30, 0)

        # Act
        message = BaseMessage(
            role="user",  # type: ignore
            content="Test",
            timestamp=custom_time
        )

        # Assert
        assert message.timestamp == custom_time


# =====================
# Edge Cases & Integration Tests
# =====================

class TestMessageEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_message_with_very_long_content(self):
        """Test message with very long content string."""
        # Arrange
        long_content = "A" * 100000  # 100k characters

        # Act
        message = UserMessage(content=long_content)

        # Assert
        assert len(message.content) == 100000
        assert message.role == "user"

    def test_message_with_unicode_content(self):
        """Test message with unicode characters."""
        # Arrange
        unicode_content = "Hello World 🌍 مرحبا"

        # Act
        message = UserMessage(content=unicode_content)

        # Assert
        assert message.content == unicode_content

    def test_message_with_newlines_and_special_characters(self):
        """Test message with newlines and special characters."""
        # Arrange
        special_content = "Line 1\nLine 2\tTabbed\r\nWindows line"

        # Act
        message = UserMessage(content=special_content)

        # Assert
        assert "\n" in message.content
        assert "\t" in message.content

    def test_multipart_content_with_empty_list(self):
        """Test message with empty multipart content list."""
        # Arrange & Act
        message = UserMessage(content=[])

        # Assert
        assert message.content == []
        assert isinstance(message.content, list)

    def test_message_serialization_and_deserialization(self):
        """Test that messages can be serialized and deserialized."""
        # Arrange
        original = UserMessage(
            content="Test message",
            id="msg_456",
            timestamp=datetime(2026, 1, 20, 16, 0, 0)
        )

        # Act - Serialize to dict
        serialized = original.to_dict()

        # Act - Deserialize back to object
        deserialized = UserMessage(**serialized)

        # Assert
        assert deserialized.content == original.content
        assert deserialized.id == original.id
        assert deserialized.timestamp == original.timestamp
        assert deserialized.role == original.role


# =====================
# Parametrized Tests
# =====================

class TestMessageParametrized:
    """Demonstrate parametrized tests for testing multiple scenarios."""

    @pytest.mark.parametrize("content,expected_length", [
        ("Short", 5),
        ("Medium length message", 21),
        ("", 0),
        ("A" * 1000, 1000),
    ])
    def test_message_content_length(self, content, expected_length):
        """Test message content length for various inputs."""
        # Arrange & Act
        message = UserMessage(content=content)

        # Assert
        assert len(message.content) == expected_length

    @pytest.mark.parametrize("message_class,expected_role", [
        (UserMessage, "user"),
        (AssistantMessage, "assistant"),
        (ImageMessage, "image"),
        (VideoMessage, "video"),
    ])
    def test_message_roles_are_correct(self, message_class, expected_role):
        """Test that each message class has the correct role."""
        # Arrange
        kwargs = {"content": "Test"}
        if message_class == ImageMessage:
            kwargs["image_path"] = "/path/to/image.png"
        elif message_class == VideoMessage:
            kwargs["video_path"] = "/path/to/video.mp4"

        # Act
        message = message_class(**kwargs)

        # Assert
        assert message.role == expected_role
