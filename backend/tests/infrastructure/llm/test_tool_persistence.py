"""
Integration tests for tool context persistence.

Tests the end-to-end flow of saving and restoring tool calls and tool results
across server restarts.
"""

import pytest
import json
import tempfile
import shutil
import os
from pathlib import Path
from datetime import datetime
from backend.domain.models.messages import AssistantMessage, UserMessage
from backend.domain.models.message_factory import message_factory
from backend.shared.utils.helpers import save_assistant_message, save_tool_result_message
from backend.infrastructure.storage.session_manager import (
    save_history, load_all_message_history, HISTORY_BASE_DIR
)


@pytest.fixture
def temp_session_dir():
    """Create temporary session directory for testing"""
    temp_dir = tempfile.mkdtemp()
    original_base_dir = HISTORY_BASE_DIR

    # Mock the session data directory
    import backend.infrastructure.storage.session_manager as sm
    sm.HISTORY_BASE_DIR = temp_dir

    yield temp_dir

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)
    sm.HISTORY_BASE_DIR = original_base_dir


class TestToolPersistence:
    """Test cases for tool context persistence"""

    def test_save_and_load_tool_use_message(self, temp_session_dir):
        """Test that assistant messages with tool_use are correctly saved and loaded"""
        session_id = "test_session_001"

        # Create assistant message with tool_use
        tool_use_content = [
            {"type": "text", "text": "I'll read the file for you"},
            {
                "type": "tool_use",
                "id": "call_123",
                "name": "read_file",
                "input": {"file_path": "/path/to/file.py"}
            }
        ]

        # Save the message
        message_id = save_assistant_message(tool_use_content, session_id)
        assert message_id is not None

        # Load history and verify
        history = load_all_message_history(session_id)
        assert len(history) == 1

        loaded_msg = message_factory(history[0])
        assert loaded_msg.role == "assistant"
        assert isinstance(loaded_msg.content, list)
        assert len(loaded_msg.content) == 2

        # Verify text part
        assert loaded_msg.content[0]["type"] == "text"
        assert loaded_msg.content[0]["text"] == "I'll read the file for you"

        # Verify tool_use part
        assert loaded_msg.content[1]["type"] == "tool_use"
        assert loaded_msg.content[1]["id"] == "call_123"
        assert loaded_msg.content[1]["name"] == "read_file"
        assert loaded_msg.content[1]["input"]["file_path"] == "/path/to/file.py"

    def test_save_and_load_tool_result_message(self, temp_session_dir):
        """Test that tool results are correctly saved and loaded as user messages"""
        session_id = "test_session_002"

        # Create tool result in ToolResult format
        tool_result = {
            "status": "success",
            "message": "File read successfully",
            "llm_content": {
                "parts": [
                    {"type": "text", "text": "def hello():\n    print('Hello, World!')"}
                ]
            },
            "data": {"file_path": "/path/to/file.py"}
        }

        # Save the tool result
        message_id = save_tool_result_message(
            tool_call_id="call_123",
            tool_name="read_file",
            tool_result=tool_result,
            session_id=session_id
        )
        assert message_id is not None

        # Load history and verify
        history = load_all_message_history(session_id)
        assert len(history) == 1

        loaded_msg = message_factory(history[0])
        assert loaded_msg.role == "user"
        assert isinstance(loaded_msg.content, list)
        assert len(loaded_msg.content) == 1

        # Verify tool_result structure
        tool_result_block = loaded_msg.content[0]
        assert tool_result_block["type"] == "tool_result"
        assert tool_result_block["tool_use_id"] == "call_123"
        assert tool_result_block["tool_name"] == "read_file"
        assert tool_result_block["is_error"] is False

        # Verify content is preserved
        content = tool_result_block["content"]
        assert "parts" in content
        assert len(content["parts"]) == 1
        assert content["parts"][0]["type"] == "text"
        assert "def hello():" in content["parts"][0]["text"]

    def test_complete_tool_call_cycle(self, temp_session_dir):
        """Test complete cycle: user message -> tool call -> tool result -> assistant response"""
        session_id = "test_session_003"

        # Step 1: User message
        user_msg = UserMessage(
            content=[{"text": "Read the file example.py"}],
            timestamp=datetime.now()
        )
        save_history(session_id, [user_msg])

        # Step 2: Assistant message with tool_use
        tool_use_content = [
            {"type": "text", "text": "I'll read that file for you"},
            {
                "type": "tool_use",
                "id": "call_456",
                "name": "read_file",
                "input": {"file_path": "example.py"}
            }
        ]
        save_assistant_message(tool_use_content, session_id)

        # Step 3: Tool result
        tool_result = {
            "status": "success",
            "message": "File read successfully",
            "llm_content": {
                "parts": [
                    {"type": "text", "text": "print('Example code')"}
                ]
            }
        }
        save_tool_result_message("call_456", "read_file", tool_result, session_id)

        # Step 4: Final assistant response
        final_content = [
            {"type": "text", "text": "The file contains a simple print statement."}
        ]
        save_assistant_message(final_content, session_id)

        # Verify complete history
        history = load_all_message_history(session_id)
        assert len(history) == 4

        # Verify message roles
        msg_0 = message_factory(history[0])
        msg_1 = message_factory(history[1])
        msg_2 = message_factory(history[2])
        msg_3 = message_factory(history[3])

        assert msg_0.role == "user"
        assert msg_1.role == "assistant"
        assert msg_2.role == "user"  # tool_result saved as user message
        assert msg_3.role == "assistant"

        # Verify tool_use in assistant message
        assert any(block.get("type") == "tool_use" for block in msg_1.content)

        # Verify tool_result in user message
        assert any(block.get("type") == "tool_result" for block in msg_2.content)

    def test_multimodal_tool_result(self, temp_session_dir):
        """Test tool results with multimodal content (text + images)"""
        session_id = "test_session_004"

        # Tool result with both text and inline_data
        tool_result = {
            "status": "success",
            "message": "Screenshot captured",
            "llm_content": {
                "parts": [
                    {"type": "text", "text": "Screenshot captured successfully"},
                    {
                        "type": "inline_data",
                        "mime_type": "image/png",
                        "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
                    }
                ]
            }
        }

        # Save the tool result
        save_tool_result_message("call_789", "take_screenshot", tool_result, session_id)

        # Load and verify
        history = load_all_message_history(session_id)
        assert len(history) == 1

        loaded_msg = message_factory(history[0])
        tool_result_block = loaded_msg.content[0]

        # Verify multimodal content is preserved
        content_parts = tool_result_block["content"]["parts"]
        assert len(content_parts) == 2
        assert content_parts[0]["type"] == "text"
        assert content_parts[1]["type"] == "inline_data"
        assert content_parts[1]["mime_type"] == "image/png"

    def test_error_tool_result(self, temp_session_dir):
        """Test that error tool results are correctly flagged"""
        session_id = "test_session_005"

        # Tool result with error status
        tool_result = {
            "status": "error",
            "message": "File not found",
            "llm_content": {
                "parts": [
                    {"type": "text", "text": "Error: The file 'nonexistent.py' does not exist"}
                ]
            }
        }

        # Save the tool result
        save_tool_result_message("call_error", "read_file", tool_result, session_id)

        # Load and verify
        history = load_all_message_history(session_id)
        loaded_msg = message_factory(history[0])
        tool_result_block = loaded_msg.content[0]

        # Verify error flag is set
        assert tool_result_block["is_error"] is True
        assert "Error:" in tool_result_block["content"]["parts"][0]["text"]

    def test_multiple_tool_calls_in_parallel(self, temp_session_dir):
        """Test saving multiple tool calls and results from parallel execution"""
        session_id = "test_session_006"

        # Assistant message with multiple tool calls
        tool_use_content = [
            {"type": "text", "text": "I'll check both files"},
            {
                "type": "tool_use",
                "id": "call_1",
                "name": "read_file",
                "input": {"file_path": "file1.py"}
            },
            {
                "type": "tool_use",
                "id": "call_2",
                "name": "read_file",
                "input": {"file_path": "file2.py"}
            }
        ]
        save_assistant_message(tool_use_content, session_id)

        # Save results for both tools
        tool_result_1 = {
            "status": "success",
            "message": "File 1 read",
            "llm_content": {"parts": [{"type": "text", "text": "Content 1"}]}
        }
        tool_result_2 = {
            "status": "success",
            "message": "File 2 read",
            "llm_content": {"parts": [{"type": "text", "text": "Content 2"}]}
        }

        save_tool_result_message("call_1", "read_file", tool_result_1, session_id)
        save_tool_result_message("call_2", "read_file", tool_result_2, session_id)

        # Verify history
        history = load_all_message_history(session_id)
        assert len(history) == 3  # 1 assistant + 2 tool results

        # Verify assistant message has both tool_use blocks
        assistant_msg = message_factory(history[0])
        tool_uses = [block for block in assistant_msg.content if block.get("type") == "tool_use"]
        assert len(tool_uses) == 2

        # Verify both tool results are saved
        result_msg_1 = message_factory(history[1])
        result_msg_2 = message_factory(history[2])
        assert result_msg_1.content[0]["tool_use_id"] == "call_1"
        assert result_msg_2.content[0]["tool_use_id"] == "call_2"


class TestGeminiMessageFormatterIntegration:
    """Test that GeminiMessageFormatter can process persisted tool context"""

    def test_format_persisted_tool_use(self, temp_session_dir):
        """Test that persisted tool_use messages can be formatted for API"""
        from backend.infrastructure.llm.providers.gemini.message_formatter import GeminiMessageFormatter

        session_id = "test_session_007"

        # Save a tool_use message
        tool_use_content = [
            {"type": "text", "text": "Reading file"},
            {
                "type": "tool_use",
                "id": "call_abc",
                "name": "read_file",
                "input": {"file_path": "test.py"}
            }
        ]
        save_assistant_message(tool_use_content, session_id)

        # Load and format for API
        history = load_all_message_history(session_id)
        messages = [message_factory(msg) for msg in history]
        formatted = GeminiMessageFormatter.format_messages(messages)

        # Verify Gemini API format
        assert len(formatted) == 1
        assert formatted[0]["role"] == "model"

        parts = formatted[0]["parts"]
        # Should have both text and function_call parts
        text_parts = [p for p in parts if hasattr(p, 'text') and p.text]
        function_calls = [p for p in parts if hasattr(p, 'function_call') and p.function_call]

        assert len(text_parts) == 1
        assert text_parts[0].text == "Reading file"
        assert len(function_calls) == 1
        assert function_calls[0].function_call.name == "read_file"

    def test_format_persisted_tool_result(self, temp_session_dir):
        """Test that persisted tool_result messages can be formatted for API"""
        from backend.infrastructure.llm.providers.gemini.message_formatter import GeminiMessageFormatter

        session_id = "test_session_008"

        # Save a tool_result message
        tool_result = {
            "status": "success",
            "message": "Success",
            "llm_content": {
                "parts": [{"type": "text", "text": "File content here"}]
            }
        }
        save_tool_result_message("call_xyz", "read_file", tool_result, session_id)

        # Load and format for API
        history = load_all_message_history(session_id)
        messages = [message_factory(msg) for msg in history]
        formatted = GeminiMessageFormatter.format_messages(messages)

        # Verify Gemini API format
        assert len(formatted) == 1
        assert formatted[0]["role"] == "user"

        parts = formatted[0]["parts"]
        # Should have function_response part (tool_result converted)
        function_responses = [p for p in parts if hasattr(p, 'function_response')]
        assert len(function_responses) == 1
        assert function_responses[0].function_response.name == "read_file"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
