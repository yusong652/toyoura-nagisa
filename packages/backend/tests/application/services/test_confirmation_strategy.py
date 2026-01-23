"""
Tests for ConfirmationStrategy - Tool confirmation logic.

Tests confirmation requirement checks and confirmation info building.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from backend.application.services.confirmation_strategy import (
    ConfirmationStrategy,
    ConfirmationInfo,
)


class TestConfirmationInfo:
    """Test ConfirmationInfo dataclass."""

    def test_create_confirmation_info(self):
        """Test creating ConfirmationInfo with required fields."""
        # Arrange & Act
        info = ConfirmationInfo(
            tool_name="bash",
            tool_id="call_123",
            command="ls -la",
            description="List files",
            confirmation_type="exec"
        )

        # Assert
        assert info.tool_name == "bash"
        assert info.tool_id == "call_123"
        assert info.command == "ls -la"
        assert info.description == "List files"
        assert info.confirmation_type == "exec"
        assert info.file_name is None
        assert info.file_path is None

    def test_create_confirmation_info_with_file_data(self):
        """Test creating ConfirmationInfo with file-related fields."""
        # Arrange & Act
        info = ConfirmationInfo(
            tool_name="edit",
            tool_id="call_456",
            command="Edit file: test.py",
            description="Update function",
            confirmation_type="edit",
            file_name="test.py",
            file_path="/path/to/test.py",
            file_diff="--- old\n+++ new"
        )

        # Assert
        assert info.tool_name == "edit"
        assert info.confirmation_type == "edit"
        assert info.file_name == "test.py"
        assert info.file_path == "/path/to/test.py"
        assert info.file_diff == "--- old\n+++ new"


class TestConfirmationStrategy:
    """Test ConfirmationStrategy class."""

    @pytest.fixture
    def mock_tool_manager(self):
        """Create mock tool manager for testing."""
        manager = Mock()
        # Mock confirmation check
        def mock_requires_confirmation(tool_name: str, tool_args: dict) -> bool:
            CONFIRMATION_REQUIRED = {"bash", "edit", "write", "pfc_execute_task", "invoke_agent"}
            return tool_name in CONFIRMATION_REQUIRED
        manager._requires_user_confirmation = Mock(side_effect=mock_requires_confirmation)
        manager._generate_edit_diff = AsyncMock(return_value=None)
        manager._generate_write_diff = AsyncMock(return_value=None)
        return manager

    def test_requires_confirmation_for_bash(self, mock_tool_manager):
        """Test that bash tools require confirmation."""
        # Arrange
        strategy = ConfirmationStrategy(mock_tool_manager)

        # Act
        requires = strategy.requires_confirmation("bash", {"command": "ls"})

        # Assert
        assert requires is True

    def test_requires_confirmation_for_edit(self, mock_tool_manager):
        """Test that edit tools require confirmation."""
        # Arrange
        strategy = ConfirmationStrategy(mock_tool_manager)

        # Act
        requires = strategy.requires_confirmation("edit", {"file_path": "test.py"})

        # Assert
        assert requires is True

    def test_requires_confirmation_for_write(self, mock_tool_manager):
        """Test that write tools require confirmation."""
        # Arrange
        strategy = ConfirmationStrategy(mock_tool_manager)

        # Act
        requires = strategy.requires_confirmation("write", {"file_path": "new.py"})

        # Assert
        assert requires is True

    def test_requires_confirmation_for_read(self, mock_tool_manager):
        """Test that read tools do NOT require confirmation."""
        # Arrange
        strategy = ConfirmationStrategy(mock_tool_manager)

        # Act
        requires = strategy.requires_confirmation("read", {"file_path": "test.py"})

        # Assert
        assert requires is False

    def test_build_bash_confirmation(self, mock_tool_manager):
        """Test building confirmation info for bash tool."""
        # Arrange
        strategy = ConfirmationStrategy(mock_tool_manager)
        tool_call = {
            "id": "call_123",
            "name": "bash",
            "arguments": {
                "command": "rm -rf /tmp/test",
                "description": "Clean test directory"
            }
        }

        # Act
        info = strategy._build_bash_confirmation(
            tool_call["id"],
            tool_call["name"],
            tool_call["arguments"]
        )

        # Assert
        assert info.tool_name == "bash"
        assert info.tool_id == "call_123"
        assert info.command == "rm -rf /tmp/test"
        assert info.description == "Clean test directory"
        assert info.confirmation_type == "exec"

    def test_build_bash_confirmation_without_description(self, mock_tool_manager):
        """Test building bash confirmation with auto-generated description."""
        # Arrange
        strategy = ConfirmationStrategy(mock_tool_manager)

        # Act
        info = strategy._build_bash_confirmation(
            "call_123",
            "bash",
            {"command": "ls -la"}
        )

        # Assert
        assert info.description == "Execute bash command: ls -la"

    @pytest.mark.asyncio
    async def test_build_edit_confirmation(self, mock_tool_manager):
        """Test building confirmation info for edit tool."""
        # Arrange
        strategy = ConfirmationStrategy(mock_tool_manager)
        mock_tool_manager._generate_edit_diff.return_value = {
            "diff": "--- a\n+++ b\n@@ content",
            "original": "old content",
            "new": "new content"
        }
        tool_call = {
            "id": "call_456",
            "name": "edit",
            "arguments": {
                "file_path": "/path/to/file.py",
                "description": "Fix bug"
            }
        }

        # Act
        info = await strategy._build_edit_confirmation(
            tool_call["id"],
            tool_call["name"],
            tool_call["arguments"]
        )

        # Assert
        assert info.tool_name == "edit"
        assert info.tool_id == "call_456"
        assert info.command == "Edit file: /path/to/file.py"
        assert info.description == "Fix bug"
        assert info.confirmation_type == "edit"
        assert info.file_path == "/path/to/file.py"
        assert info.file_name == "file.py"
        assert info.file_diff == "--- a\n+++ b\n@@ content"
        assert info.original_content == "old content"
        assert info.new_content == "new content"

    @pytest.mark.asyncio
    async def test_build_write_confirmation(self, mock_tool_manager):
        """Test building confirmation info for write tool."""
        # Arrange
        strategy = ConfirmationStrategy(mock_tool_manager)
        mock_tool_manager._generate_write_diff.return_value = {
            "diff": "+++ new file\n@@ content",
            "original": "",
            "new": "file content"
        }
        tool_call = {
            "id": "call_789",
            "name": "write",
            "arguments": {
                "file_path": "/path/to/new.py",
                "description": "Create new file"
            }
        }

        # Act
        info = await strategy._build_write_confirmation(
            tool_call["id"],
            tool_call["name"],
            tool_call["arguments"]
        )

        # Assert
        assert info.tool_name == "write"
        assert info.confirmation_type == "edit"  # write uses "edit" type
        assert info.file_path == "/path/to/new.py"
        assert info.file_name == "new.py"

    def test_build_pfc_confirmation_background(self, mock_tool_manager):
        """Test building confirmation for PFC background task."""
        # Arrange
        strategy = ConfirmationStrategy(mock_tool_manager)
        tool_call = {
            "id": "call_pfc",
            "name": "pfc_execute_task",
            "arguments": {
                "entry_script": "simulation.py",
                "description": "Run DEM simulation",
                "run_in_background": True
            }
        }

        # Act
        info = strategy._build_pfc_confirmation(
            tool_call["id"],
            tool_call["name"],
            tool_call["arguments"]
        )

        # Assert
        assert info.tool_name == "pfc_execute_task"
        assert info.command == "Execute PFC task (background): simulation.py"
        assert info.description == "Run DEM simulation"
        assert info.confirmation_type == "exec"

    def test_build_pfc_confirmation_foreground(self, mock_tool_manager):
        """Test building confirmation for PFC foreground task."""
        # Arrange
        strategy = ConfirmationStrategy(mock_tool_manager)

        # Act
        info = strategy._build_pfc_confirmation(
            "call_pfc",
            "pfc_execute_task",
            {
                "entry_script": "test.py",
                "run_in_background": False
            }
        )

        # Assert
        assert info.command == "Execute PFC task (foreground): test.py"

    def test_build_invoke_agent_confirmation(self, mock_tool_manager):
        """Test building confirmation for SubAgent invocation."""
        # Arrange
        strategy = ConfirmationStrategy(mock_tool_manager)
        tool_call = {
            "id": "call_agent",
            "name": "invoke_agent",
            "arguments": {
                "subagent_type": "pfc_explorer",
                "prompt": "Search for command documentation",
                "description": "Find PFC command examples"
            }
        }

        # Act
        info = strategy._build_invoke_agent_confirmation(
            tool_call["id"],
            tool_call["name"],
            tool_call["arguments"]
        )

        # Assert
        assert info.tool_name == "invoke_agent"
        assert info.command == "Invoke SubAgent: pfc_explorer"
        assert info.description == "Task: Find PFC command examples"
        assert info.confirmation_type == "info"

    def test_build_invoke_agent_confirmation_long_prompt(self, mock_tool_manager):
        """Test that long prompts are truncated in confirmation."""
        # Arrange
        strategy = ConfirmationStrategy(mock_tool_manager)
        long_prompt = "a" * 150  # Create a 150-character prompt

        # Act
        info = strategy._build_invoke_agent_confirmation(
            "call_agent",
            "invoke_agent",
            {
                "subagent_type": "pfc_explorer",
                "prompt": long_prompt
            }
        )

        # Assert - should be truncated to 100 chars + "..." (+ "Prompt: " prefix = 111 total)
        assert len(info.description) <= 115  # Allow some margin
        assert "..." in info.description
        assert info.description.startswith("Prompt: ")

    def test_build_generic_confirmation(self, mock_tool_manager):
        """Test building confirmation for generic tool."""
        # Arrange
        strategy = ConfirmationStrategy(mock_tool_manager)

        # Act
        info = strategy._build_generic_confirmation(
            "call_123",
            "custom_tool",
            {"description": "Custom operation"}
        )

        # Assert
        assert info.tool_name == "custom_tool"
        assert info.command == "custom_tool operation"
        assert info.description == "Custom operation"
        assert info.confirmation_type == "info"
