"""
Pytest configuration and shared fixtures.

This file contains test fixtures that are available to all tests.
Fixtures provide reusable test data and mock objects.
"""

import importlib
import sys
from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock
import uuid

import pytest


def _ensure_backend_config_available() -> None:
    try:
        importlib.import_module("backend.config")
        return
    except ModuleNotFoundError:
        config_module = importlib.import_module("backend.config_example")
        sys.modules.setdefault("backend.config", config_module)
        for name in ("cors", "dev", "llm", "memory", "pfc"):
            sys.modules.setdefault(
                f"backend.config.{name}",
                importlib.import_module(f"backend.config_example.{name}"),
            )


_ensure_backend_config_available()


# =====================
# Domain Model Fixtures
# =====================


@pytest.fixture
def sample_user_message_dict() -> Dict[str, Any]:
    """Sample user message in dictionary format."""
    return {
        "role": "user",
        "content": "Hello, how are you?",
        "id": "msg_001",
        "timestamp": datetime(2026, 1, 20, 10, 30, 0),
    }


@pytest.fixture
def sample_assistant_message_dict() -> Dict[str, Any]:
    """Sample assistant message in dictionary format."""
    return {
        "role": "assistant",
        "content": "I'm doing well, thank you!",
        "id": "msg_002",
        "timestamp": datetime(2026, 1, 20, 10, 30, 5),
    }


@pytest.fixture
def sample_multipart_content() -> List[Dict[str, Any]]:
    """Sample multipart content (text + image)."""
    return [
        {"type": "text", "text": "Here's an image:"},
        {"type": "image_url", "image_url": {"url": "https://example.com/image.png"}},
    ]


# =====================
# Streaming Fixtures
# =====================


@pytest.fixture
def sample_thinking_chunk() -> Dict[str, Any]:
    """Sample thinking chunk data."""
    return {"chunk_type": "thinking", "content": "Let me analyze this step by step...", "metadata": {"thought": True}}


@pytest.fixture
def sample_text_chunk() -> Dict[str, Any]:
    """Sample text chunk data."""
    return {"chunk_type": "text", "content": "The answer is 42.", "metadata": {}}


@pytest.fixture
def sample_function_call_chunk() -> Dict[str, Any]:
    """Sample function call chunk data."""
    return {
        "chunk_type": "function_call",
        "content": "calculate",
        "metadata": {"args": {"expression": "2 + 2"}},
        "function_call": {"name": "calculate", "args": {"expression": "2 + 2"}},
    }


# =====================
# Mock LLM Client Fixtures
# =====================


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing without actual API calls."""
    client = Mock()
    client.get_or_create_context_manager = Mock()
    return client


@pytest.fixture
def mock_context_manager():
    """Mock context manager for LLM client."""
    ctx = Mock()
    ctx.agent_profile = "pfc_expert"
    ctx.enable_memory = True
    ctx.add_user_message = AsyncMock()
    ctx.add_assistant_message = AsyncMock()
    ctx.add_tool_result = AsyncMock()
    ctx.get_messages = Mock(return_value=[])
    return ctx


# =====================
# Tool Executor Fixtures
# =====================


@pytest.fixture
def mock_tool_manager():
    """Mock tool manager for testing tool execution."""
    manager = Mock()
    manager.handle_function_call = AsyncMock(return_value={"status": "success", "result": "Tool executed successfully"})

    # Mock confirmation check - only bash, edit, write, pfc_execute_task, invoke_agent require confirmation
    def mock_requires_confirmation(tool_name: str, tool_args: dict) -> bool:
        CONFIRMATION_REQUIRED_TOOLS = {"bash", "edit", "write", "pfc_execute_task", "invoke_agent"}
        return tool_name in CONFIRMATION_REQUIRED_TOOLS

    manager._requires_user_confirmation = Mock(side_effect=mock_requires_confirmation)

    # Mock diff generation methods (for confirmation info building)
    manager._generate_edit_diff = AsyncMock(return_value=None)
    manager._generate_write_diff = AsyncMock(return_value=None)

    return manager


@pytest.fixture
def sample_tool_call() -> Dict[str, Any]:
    """Sample tool call data."""
    return {"id": f"call_{uuid.uuid4().hex[:8]}", "name": "read", "arguments": {"file_path": "/path/to/file.txt"}}


@pytest.fixture
def sample_bash_tool_call() -> Dict[str, Any]:
    """Sample bash tool call (requires confirmation)."""
    return {
        "id": f"call_{uuid.uuid4().hex[:8]}",
        "name": "bash",
        "arguments": {"command": "rm -rf /", "description": "Delete everything"},
    }


# =====================
# Session Fixtures
# =====================


@pytest.fixture
def sample_session_id() -> str:
    """Sample session ID."""
    return f"session_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def sample_message_id() -> str:
    """Sample message ID."""
    return f"msg_{uuid.uuid4().hex[:8]}"


# =====================
# PFC Integration Fixtures
# =====================


@pytest.fixture
def sample_pfc_task_data() -> Dict[str, Any]:
    """Sample PFC task data."""
    return {
        "task_id": f"task_{uuid.uuid4().hex[:8]}",
        "script_path": "/workspace/simulation.py",
        "description": "Run ball simulation",
        "status": "pending",
        "git_commit": "abc123def456",
    }


@pytest.fixture
def mock_pfc_client():
    """Mock PFC WebSocket client."""
    client = AsyncMock()
    client.execute_task = AsyncMock(
        return_value={"status": "pending", "data": {"task_id": "task_001", "git_commit": "abc123"}}
    )
    client.check_task_status = AsyncMock(return_value={"status": "running", "output": ["Line 1", "Line 2"]})
    return client


# =====================
# WebSocket Fixtures
# =====================


@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection."""
    ws = AsyncMock()
    ws.send_text = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.receive_json = AsyncMock()
    return ws


# =====================
# Pytest Hooks
# =====================


def pytest_configure(config):
    """Configure pytest with custom settings."""
    # Add custom markers
    config.addinivalue_line("markers", "unit: Unit tests (fast, no external dependencies)")
    config.addinivalue_line("markers", "integration: Integration tests (may use database, external services)")
    config.addinivalue_line("markers", "e2e: End-to-end tests (full workflow)")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Auto-mark tests based on path
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
        else:
            # Default to unit test
            item.add_marker(pytest.mark.unit)
