import pytest
from unittest.mock import AsyncMock, Mock

from backend.infrastructure.websocket.notification_service import WebSocketNotificationService
from backend.presentation.websocket.message_types import MessageType
import backend.infrastructure.websocket.connection_manager as connection_manager_module
import backend.infrastructure.websocket.notification_service as notification_module


def _setup_connection_manager(monkeypatch):
    connection_manager = Mock()
    connection_manager.send_json = AsyncMock(return_value=True)
    monkeypatch.setattr(
        connection_manager_module,
        "get_connection_manager",
        Mock(return_value=connection_manager),
    )
    return connection_manager


@pytest.mark.asyncio
async def test_send_streaming_update_sends_payload(monkeypatch):
    connection_manager = _setup_connection_manager(monkeypatch)
    content = [{"type": "text", "text": "hello"}]
    usage = {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
        "tokens_left": 100,
    }

    await WebSocketNotificationService.send_streaming_update(
        session_id="session-1",
        message_id="msg-1",
        content=content,
        streaming=False,
        interrupted=True,
        usage=usage,
    )

    call_args = connection_manager.send_json.call_args
    assert call_args.args[0] == "session-1"
    payload = call_args.args[1]
    assert payload["type"] == MessageType.STREAMING_UPDATE
    assert payload["message_id"] == "msg-1"
    assert payload["content"] == content
    assert payload["streaming"] is False
    assert payload["interrupted"] is True
    assert payload["usage"] == usage


@pytest.mark.asyncio
async def test_send_streaming_update_skips_when_no_connection_manager(monkeypatch):
    monkeypatch.setattr(
        connection_manager_module,
        "get_connection_manager",
        Mock(return_value=None),
    )

    await WebSocketNotificationService.send_streaming_update(
        session_id="session-1",
        message_id="msg-1",
        content=[],
    )


@pytest.mark.asyncio
async def test_send_message_create_sends_payload(monkeypatch):
    connection_manager = _setup_connection_manager(monkeypatch)

    await WebSocketNotificationService.send_message_create(
        session_id="session-1",
        message_id="msg-1",
        streaming=True,
        initial_text="Ready",
    )

    call_args = connection_manager.send_json.call_args
    assert call_args.args[0] == "session-1"
    payload = call_args.args[1]
    assert payload["type"] == MessageType.MESSAGE_CREATE
    assert payload["message_id"] == "msg-1"
    assert payload["role"] == "assistant"
    assert payload["initial_text"] == "Ready"
    assert payload["streaming"] is True


@pytest.mark.asyncio
async def test_send_title_update_sends_payload(monkeypatch):
    connection_manager = _setup_connection_manager(monkeypatch)

    await WebSocketNotificationService.send_title_update(
        session_id="session-1",
        new_title="New Title",
    )

    call_args = connection_manager.send_json.call_args
    assert call_args.args[0] == "session-1"
    payload = call_args.args[1]
    assert payload["type"] == MessageType.TITLE_UPDATE
    assert payload["payload"]["session_id"] == "session-1"
    assert payload["payload"]["title"] == "New Title"


@pytest.mark.asyncio
async def test_send_session_mode_update_sends_payload(monkeypatch):
    connection_manager = _setup_connection_manager(monkeypatch)

    await WebSocketNotificationService.send_session_mode_update(
        session_id="session-1",
        mode="plan",
    )

    call_args = connection_manager.send_json.call_args
    assert call_args.args[0] == "session-1"
    payload = call_args.args[1]
    assert payload["type"] == MessageType.SESSION_MODE_UPDATE
    assert payload["payload"]["session_id"] == "session-1"
    assert payload["payload"]["mode"] == "plan"


@pytest.mark.asyncio
async def test_send_session_llm_config_update_sends_payload(monkeypatch):
    connection_manager = _setup_connection_manager(monkeypatch)
    llm_config = {"provider": "openai", "model": "gpt-4"}

    await WebSocketNotificationService.send_session_llm_config_update(
        session_id="session-1",
        llm_config=llm_config,
    )

    call_args = connection_manager.send_json.call_args
    assert call_args.args[0] == "session-1"
    payload = call_args.args[1]
    assert payload["type"] == MessageType.SESSION_LLM_CONFIG_UPDATE
    assert payload["payload"]["session_id"] == "session-1"
    assert payload["payload"]["llm_config"] == llm_config


@pytest.mark.asyncio
async def test_send_todo_update_sends_payload(monkeypatch):
    connection_manager = _setup_connection_manager(monkeypatch)
    todo = {
        "todo_id": "todo-1",
        "content": "Run tests",
        "activeForm": "Running tests",
        "status": "in_progress",
    }

    await WebSocketNotificationService.send_todo_update(
        session_id="session-1",
        todo=todo,
    )

    call_args = connection_manager.send_json.call_args
    assert call_args.args[0] == "session-1"
    payload = call_args.args[1]
    assert payload == {
        "type": "TODO_UPDATE",
        "session_id": "session-1",
        "todo": todo,
    }


@pytest.mark.asyncio
async def test_send_tool_result_update_filters_and_sends_payload(monkeypatch):
    connection_manager = _setup_connection_manager(monkeypatch)
    filtered_content = [
        {
            "type": "tool_result",
            "tool_use_id": "tool-call",
            "tool_name": "read",
            "content": {"parts": [{"type": "text", "text": "clean"}]},
            "is_error": False,
            "data": {"diff": "ok"},
        }
    ]
    monkeypatch.setattr(
        notification_module,
        "filter_message_content",
        Mock(return_value=filtered_content),
    )

    await WebSocketNotificationService.send_tool_result_update(
        session_id="session-1",
        message_id="msg-1",
        tool_call_id="tool-call",
        tool_name="read",
        tool_result={
            "status": "success",
            "llm_content": {"parts": [{"type": "text", "text": "<system-reminder>raw</system-reminder>"}]},
            "data": {"diff": "ok"},
        },
    )

    call_args = connection_manager.send_json.call_args
    assert call_args.args[0] == "session-1"
    payload = call_args.args[1]
    assert payload["type"] == "TOOL_RESULT_UPDATE"
    assert payload["message_id"] == "msg-1"
    assert payload["session_id"] == "session-1"
    assert payload["content"] == filtered_content


@pytest.mark.asyncio
async def test_send_tool_result_update_skips_when_session_id_missing(monkeypatch):
    connection_manager = _setup_connection_manager(monkeypatch)

    await WebSocketNotificationService.send_tool_result_update(
        session_id="",
        message_id="msg-1",
        tool_call_id="tool-call",
        tool_name="read",
        tool_result={"status": "success", "llm_content": {}},
    )

    connection_manager.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_send_subagent_tool_use_sends_payload(monkeypatch):
    connection_manager = _setup_connection_manager(monkeypatch)

    await WebSocketNotificationService.send_subagent_tool_use(
        session_id="session-1",
        parent_tool_call_id="parent",
        tool_call_id="tool",
        tool_name="bash",
        tool_input={"command": "date"},
    )

    call_args = connection_manager.send_json.call_args
    assert call_args.args[0] == "session-1"
    payload = call_args.args[1]
    assert payload == {
        "type": "SUBAGENT_TOOL_USE",
        "session_id": "session-1",
        "parent_tool_call_id": "parent",
        "tool_call_id": "tool",
        "tool_name": "bash",
        "tool_input": {"command": "date"},
    }


@pytest.mark.asyncio
async def test_send_subagent_tool_result_sends_payload(monkeypatch):
    connection_manager = _setup_connection_manager(monkeypatch)

    await WebSocketNotificationService.send_subagent_tool_result(
        session_id="session-1",
        parent_tool_call_id="parent",
        tool_call_id="tool",
        tool_name="bash",
        is_error=True,
    )

    call_args = connection_manager.send_json.call_args
    assert call_args.args[0] == "session-1"
    payload = call_args.args[1]
    assert payload == {
        "type": "SUBAGENT_TOOL_RESULT",
        "session_id": "session-1",
        "parent_tool_call_id": "parent",
        "tool_call_id": "tool",
        "tool_name": "bash",
        "is_error": True,
    }
