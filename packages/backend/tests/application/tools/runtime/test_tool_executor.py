"""
Tests for ToolExecutor - tool runtime workflow.

Demonstrates:
1. Mocking external dependencies (tool_manager, WebSocket)
2. Testing async functions
3. Testing error handling
4. Testing business logic without infrastructure
"""

# pyright: reportOptionalSubscript=false
# pyright: reportArgumentType=false

import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import Any, Dict, List, cast

from backend.application.tools.runtime.executor import (
    ToolExecutor,
    ToolExecutionResult,
    ClassifiedTools,
)


# =====================
# ToolExecutor Basic Tests
# =====================


class TestToolExecutorInitialization:
    """Test ToolExecutor initialization and configuration."""

    def test_create_tool_executor_with_default_settings(self, mock_tool_manager, sample_session_id):
        """Test creating executor with default settings."""
        # Arrange & Act
        executor = ToolExecutor(tool_manager=mock_tool_manager, session_id=sample_session_id)

        # Assert
        assert executor.tool_manager == mock_tool_manager
        assert executor.session_id == sample_session_id
        assert executor.notification_session_id == sample_session_id  # Same as session_id
        assert executor.send_tool_result_notifications is True  # Default

    def test_create_tool_executor_with_different_notification_session(self, mock_tool_manager, sample_session_id):
        """Test creating executor with different notification session (SubAgent case)."""
        # Arrange
        parent_session_id = "parent_session_123"

        # Act
        executor = ToolExecutor(
            tool_manager=mock_tool_manager, session_id=sample_session_id, notification_session_id=parent_session_id
        )

        # Assert
        assert executor.session_id == sample_session_id
        assert executor.notification_session_id == parent_session_id

    def test_create_tool_executor_with_notifications_disabled(self, mock_tool_manager, sample_session_id):
        """Test creating executor with notifications disabled (SubAgent case)."""
        # Arrange & Act
        executor = ToolExecutor(
            tool_manager=mock_tool_manager, session_id=sample_session_id, send_tool_result_notifications=False
        )

        # Assert
        assert executor.send_tool_result_notifications is False


# =====================
# Tool Classification Tests
# =====================


class TestToolClassification:
    """Test tool classification by confirmation requirement."""

    def test_classify_non_confirmation_tool(self, mock_tool_manager, sample_session_id, sample_tool_call):
        """Test classifying a tool that doesn't require confirmation."""
        # Arrange
        executor = ToolExecutor(mock_tool_manager, sample_session_id)
        tool_calls = [sample_tool_call]  # 'read' tool doesn't need confirmation

        # Act
        classified = executor.classify_tools(tool_calls)

        # Assert
        assert len(classified.non_confirm) == 1
        assert len(classified.confirm) == 0
        assert classified.non_confirm[0][0] == 0  # Index
        assert classified.non_confirm[0][1] == sample_tool_call  # Tool call

    def test_classify_confirmation_tool(self, mock_tool_manager, sample_session_id, sample_bash_tool_call):
        """Test classifying a tool that requires confirmation."""
        # Arrange
        executor = ToolExecutor(mock_tool_manager, sample_session_id)
        tool_calls = [sample_bash_tool_call]  # 'bash' with dangerous command needs confirmation

        # Act
        classified = executor.classify_tools(tool_calls)

        # Assert
        assert len(classified.non_confirm) == 0
        assert len(classified.confirm) == 1
        assert classified.confirm[0][0] == 0  # Index
        assert classified.confirm[0][1] == sample_bash_tool_call

    def test_classify_mixed_tools(self, mock_tool_manager, sample_session_id, sample_tool_call, sample_bash_tool_call):
        """Test classifying a mix of confirmation and non-confirmation tools."""
        # Arrange
        executor = ToolExecutor(mock_tool_manager, sample_session_id)
        tool_calls = [sample_tool_call, sample_bash_tool_call]

        # Act
        classified = executor.classify_tools(tool_calls)

        # Assert
        assert len(classified.non_confirm) == 1
        assert len(classified.confirm) == 1
        assert classified.non_confirm[0][1]["name"] == "read"
        assert classified.confirm[0][1]["name"] == "bash"

    def test_classify_preserves_original_order(self, mock_tool_manager, sample_session_id):
        """Test that classification preserves original tool order indices."""
        # Arrange
        executor = ToolExecutor(mock_tool_manager, sample_session_id)
        tool_calls = [
            {"id": "call_1", "name": "read", "arguments": {"path": "/test"}},
            {"id": "call_2", "name": "bash", "arguments": {"command": "rm -rf /"}},
            {"id": "call_3", "name": "glob", "arguments": {"pattern": "*.py"}},
        ]

        # Act
        classified = executor.classify_tools(tool_calls)

        # Assert
        # Indices should match original positions
        assert classified.non_confirm[0][0] == 0  # read at index 0
        assert classified.confirm[0][0] == 1  # bash at index 1
        assert classified.non_confirm[1][0] == 2  # glob at index 2


# =====================
# Tool Execution Tests (with mocking)
# =====================


class TestToolExecution:
    """Test tool execution with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_execute_single_non_confirmation_tool(
        self, mock_tool_manager, sample_session_id, sample_tool_call, sample_message_id
    ):
        """Test executing a single tool that doesn't require confirmation."""
        # Arrange
        executor = ToolExecutor(mock_tool_manager, sample_session_id)
        mock_tool_manager.handle_function_call.return_value = {"status": "success", "result": "File content here"}

        # Act
        result = cast(Any, await executor.execute_all([sample_tool_call], sample_message_id))

        # Assert
        assert isinstance(result, ToolExecutionResult)
        assert len(result.results) == 1
        first_result: Dict[str, Any] = result.results[0]
        assert first_result["status"] == "success"
        assert result.user_rejected is False
        assert len(result.rejected_tools) == 0

        # Verify tool was executed
        mock_tool_manager.handle_function_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_multiple_non_confirmation_tools(
        self, mock_tool_manager, sample_session_id, sample_message_id
    ):
        """Test executing multiple non-confirmation tools."""
        # Arrange
        executor = ToolExecutor(mock_tool_manager, sample_session_id)
        tool_calls = [
            {"id": "call_1", "name": "read", "arguments": {"path": "/file1"}},
            {"id": "call_2", "name": "glob", "arguments": {"pattern": "*.py"}},
        ]
        mock_tool_manager.handle_function_call.return_value = {"status": "success"}

        # Act
        result = cast(Any, await executor.execute_all(tool_calls, sample_message_id))

        # Assert
        assert len(result.results) == 2
        non_null_results: List[Dict[str, Any]] = result.results
        assert len(non_null_results) == 2
        assert all(item["status"] == "success" for item in non_null_results)
        assert result.user_rejected is False

        # Verify both tools were executed
        assert mock_tool_manager.handle_function_call.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_tool_with_error(
        self, mock_tool_manager, sample_session_id, sample_tool_call, sample_message_id
    ):
        """Test handling tool execution errors."""
        # Arrange
        executor = ToolExecutor(mock_tool_manager, sample_session_id)
        mock_tool_manager.handle_function_call.return_value = {"status": "error", "error": "File not found"}

        # Act
        result = cast(Any, await executor.execute_all([sample_tool_call], sample_message_id))

        # Assert
        first_result: Dict[str, Any] = result.results[0]
        assert first_result["status"] == "error"
        assert first_result["error"] == "File not found"
        assert result.user_rejected is False

    @pytest.mark.asyncio
    async def test_execute_with_notifications_disabled(
        self, mock_tool_manager, sample_session_id, sample_tool_call, sample_message_id
    ):
        """Test that notifications are not sent when disabled."""
        # Arrange
        executor = ToolExecutor(mock_tool_manager, sample_session_id, send_tool_result_notifications=False)
        mock_tool_manager.handle_function_call.return_value = {"status": "success"}

        # Act
        with patch("backend.infrastructure.websocket.notification_service.WebSocketNotificationService") as mock_ws:
            result = cast(Any, await executor.execute_all([sample_tool_call], sample_message_id))

        # Assert
        # Notification service should not be called
        mock_ws.send_tool_result_update.assert_not_called()


# =====================
# User Rejection Tests
# =====================


class TestUserRejection:
    """Test user rejection handling and cascade blocking."""

    @pytest.mark.asyncio
    async def test_user_rejection_blocks_remaining_tools(self, mock_tool_manager, sample_session_id, sample_message_id):
        """Test that user rejection blocks remaining confirmation tools."""
        # Arrange
        executor = ToolExecutor(mock_tool_manager, sample_session_id)

        # Tool calls: bash (needs confirmation) + another bash (would be blocked)
        tool_calls = [
            {"id": "call_1", "name": "bash", "arguments": {"command": "rm file1"}},
            {"id": "call_2", "name": "bash", "arguments": {"command": "rm file2"}},
        ]

        # Mock confirmation to reject first tool
        with patch.object(
            executor.confirmation_strategy, "request_confirmation", new_callable=AsyncMock
        ) as mock_confirm:
            mock_confirm.return_value = Mock(outcome="reject", user_message="No thanks")

            # Act
            result = cast(Any, await executor.execute_all(tool_calls, sample_message_id))

        # Assert
        assert result.user_rejected is True
        assert len(result.rejected_tools) == 2  # Both tools rejected
        assert result.rejection_outcome == "reject"
        assert result.rejection_message == "No thanks"

        # Second tool should be cascade blocked
        second_result: Dict[str, Any] = result.results[1]
        assert "cascade_blocked" in str(second_result)

    @pytest.mark.asyncio
    async def test_reject_and_tell_continues_with_instruction(
        self, mock_tool_manager, sample_session_id, sample_message_id
    ):
        """Test that reject_and_tell doesn't stop execution but provides instruction."""
        # Arrange
        executor = ToolExecutor(mock_tool_manager, sample_session_id)
        tool_calls = [
            {"id": "call_1", "name": "bash", "arguments": {"command": "rm file1"}},
        ]

        # Mock confirmation to reject_and_tell
        with patch.object(
            executor.confirmation_strategy, "request_confirmation", new_callable=AsyncMock
        ) as mock_confirm:
            mock_confirm.return_value = Mock(outcome="reject_and_tell", user_message="Use safer approach")

            # Act
            result = cast(Any, await executor.execute_all(tool_calls, sample_message_id))

        # Assert
        assert result.user_rejected is True
        assert result.rejection_outcome == "reject_and_tell"
        assert result.rejection_message == "Use safer approach"

        # Result should indicate rejection but not cascade blocking
        first_result: Dict[str, Any] = result.results[0]
        assert first_result["user_rejected"] is True


# =====================
# Result Persistence Tests
# =====================


class TestResultPersistence:
    """Test saving results to context and database."""

    @pytest.mark.asyncio
    async def test_save_results_to_context(self, mock_tool_manager, mock_context_manager, sample_session_id):
        """Test saving tool results to context manager."""
        # Arrange
        executor = ToolExecutor(mock_tool_manager, sample_session_id)
        tool_calls = [{"id": "call_1", "name": "read", "arguments": {}}]
        results: List[Dict[str, Any]] = [{"status": "success", "result": "File content"}]

        # Act
        await executor.save_results_to_context(  # type: ignore[arg-type]
            tool_calls,
            results,
            mock_context_manager,
            inject_reminders=True,
        )

        # Assert
        mock_context_manager.add_tool_result.assert_called_once_with(
            "call_1",
            "read",
            {"status": "success", "result": "File content"},
            inject_reminders=True,  # Last tool should inject reminders
        )

    @pytest.mark.asyncio
    async def test_save_multiple_results_with_reminder_on_last(
        self, mock_tool_manager, mock_context_manager, sample_session_id
    ):
        """Test that only the last tool result gets reminders."""
        # Arrange
        executor = ToolExecutor(mock_tool_manager, sample_session_id)
        tool_calls = [
            {"id": "call_1", "name": "read", "arguments": {}},
            {"id": "call_2", "name": "glob", "arguments": {}},
        ]
        results: List[Dict[str, Any]] = [{"status": "success"}, {"status": "success"}]

        # Act
        await executor.save_results_to_context(  # type: ignore[arg-type]
            tool_calls,
            results,
            mock_context_manager,
            inject_reminders=True,
        )

        # Assert
        assert mock_context_manager.add_tool_result.call_count == 2

        # First call should NOT inject reminders
        first_call = mock_context_manager.add_tool_result.call_args_list[0]
        assert first_call[1]["inject_reminders"] is False

        # Second call SHOULD inject reminders (last tool)
        second_call = mock_context_manager.add_tool_result.call_args_list[1]
        assert second_call[1]["inject_reminders"] is True

    @pytest.mark.asyncio
    async def test_subagent_disables_reminder_injection(
        self, mock_tool_manager, mock_context_manager, sample_session_id
    ):
        """Test that SubAgent disables reminder injection."""
        # Arrange
        executor = ToolExecutor(mock_tool_manager, sample_session_id)
        tool_calls = [{"id": "call_1", "name": "read", "arguments": {}}]
        results: List[Dict[str, Any]] = [{"status": "success"}]

        # Act - SubAgent sets inject_reminders=False
        await executor.save_results_to_context(  # type: ignore[arg-type]
            tool_calls,
            results,
            mock_context_manager,
            inject_reminders=False,  # SubAgent behavior
        )

        # Assert
        mock_context_manager.add_tool_result.assert_called_once()
        call_kwargs = mock_context_manager.add_tool_result.call_args[1]
        assert call_kwargs["inject_reminders"] is False


# =====================
# Edge Cases
# =====================


class TestToolExecutorEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_execute_empty_tool_list(self, mock_tool_manager, sample_session_id, sample_message_id):
        """Test executing empty tool list."""
        # Arrange
        executor = ToolExecutor(mock_tool_manager, sample_session_id)

        # Act
        result = cast(Any, await executor.execute_all([], sample_message_id))

        # Assert
        assert result.results == []
        assert result.user_rejected is False
        assert len(result.rejected_tools) == 0

    @pytest.mark.asyncio
    async def test_execute_with_none_result(
        self, mock_tool_manager, sample_session_id, sample_tool_call, sample_message_id
    ):
        """Test handling None result from tool execution."""
        # Arrange
        executor = ToolExecutor(mock_tool_manager, sample_session_id)
        mock_tool_manager.handle_function_call.return_value = None

        # Act
        result = cast(Any, await executor.execute_all([sample_tool_call], sample_message_id))

        # Assert
        first_result: Dict[str, Any] = result.results[0]
        assert first_result["status"] == "error"

    def test_create_cascade_blocked_result(self, mock_tool_manager, sample_session_id):
        """Test creating cascade blocked result message."""
        # Arrange
        executor = ToolExecutor(mock_tool_manager, sample_session_id)

        # Act
        result = executor._create_cascade_blocked_result("write", "bash")

        # Assert
        assert "cascade_blocked" in result
        assert result["cascade_blocked"] is True
        assert "bash was rejected" in result["message"]
        assert "write" in result["message"]
