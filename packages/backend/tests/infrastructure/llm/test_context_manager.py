import pytest
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock

from backend.domain.models.messages import UserMessage
from backend.infrastructure.llm.base.context_manager import BaseContextManager
import backend.infrastructure.llm.base.context_manager as context_module
import backend.infrastructure.storage.session_manager as session_manager
import backend.domain.models.message_factory as message_factory_module
import backend.infrastructure.monitoring as monitoring_module
import backend.application.reminder as reminder_module


class DummyTodoMonitor:
    def __init__(self) -> None:
        self.turns = 0

    def track_conversation_turn(self) -> None:
        self.turns += 1


class DummyStatusMonitor:
    def __init__(self, interrupted: bool = False) -> None:
        self._interrupted = interrupted
        self.todo_monitor = DummyTodoMonitor()
        self.interrupt_cleared = False

    def was_last_response_interrupted(self) -> bool:
        return self._interrupted

    def clear_interrupt_flag(self) -> None:
        self.interrupt_cleared = True


class DummyContextManager(BaseContextManager):
    def __init__(
        self,
        provider_name: Optional[str] = "dummy",
        session_id: str = "session-1",
        working_contents: Optional[List[Dict[str, Any]]] = None,
        status_monitor: Optional[DummyStatusMonitor] = None,
    ) -> None:
        self._provider_name = provider_name
        self.session_id = session_id
        self.working_contents = working_contents or []
        self._status_monitor = status_monitor or DummyStatusMonitor()
        self.agent_profile = "pfc_expert"
        self.enable_memory = True

    def add_response(self, response: Any) -> None:
        self.last_response = response

    async def add_tool_result(
        self,
        tool_call_id: str,
        tool_name: str,
        result: Any,
        inject_reminders: bool = False,
    ) -> None:
        self.last_tool_result = (tool_call_id, tool_name, result, inject_reminders)

    def _is_tool_call(self, msg: Dict[str, Any]) -> bool:
        return False

    def _is_tool_result(self, msg: Dict[str, Any]) -> bool:
        return False


@dataclass
class DummyHistoryMessage:
    role: str
    content: str


def test_initialize_from_messages_requires_provider_name():
    manager = DummyContextManager(provider_name=None)

    with pytest.raises(ValueError, match="Provider name"):
        manager.initialize_from_messages([UserMessage(content="hi")])


def test_initialize_from_messages_uses_formatter(monkeypatch):
    manager = DummyContextManager()

    class DummyFormatter:
        @staticmethod
        def format_messages(messages):
            return [{"role": "user", "content": "ok"}]

    get_formatter = Mock(return_value=DummyFormatter)
    monkeypatch.setattr(context_module, "get_message_formatter_class", get_formatter)

    manager.initialize_from_messages([UserMessage(content="hi")])

    assert manager.working_contents == [{"role": "user", "content": "ok"}]


@pytest.mark.asyncio
async def test_add_user_message_appends_when_not_interrupted(monkeypatch):
    status_monitor = DummyStatusMonitor(interrupted=False)
    manager = DummyContextManager(status_monitor=status_monitor)

    class DummyFormatter:
        @staticmethod
        def format_single_message(message):
            return {"role": message.role, "content": message.content}

    get_formatter = Mock(return_value=DummyFormatter)
    monkeypatch.setattr(context_module, "get_message_formatter_class", get_formatter)

    await manager.add_user_message(UserMessage(content="hello"))

    assert status_monitor.todo_monitor.turns == 1
    assert manager.working_contents == [{"role": "user", "content": "hello"}]


@pytest.mark.asyncio
async def test_add_user_message_merges_when_interrupted(monkeypatch):
    status_monitor = DummyStatusMonitor(interrupted=True)
    manager = DummyContextManager(
        status_monitor=status_monitor,
        working_contents=[{"role": "user", "content": "first"}],
    )

    history = [
        {"role": "user", "content": "first"},
        {"role": "user", "content": "second"},
    ]
    save_history = Mock()

    monkeypatch.setattr(session_manager, "load_all_message_history", Mock(return_value=history))
    monkeypatch.setattr(session_manager, "save_history", save_history)
    monkeypatch.setattr(
        message_factory_module,
        "message_factory",
        lambda data: DummyHistoryMessage(role=data["role"], content=data["content"]),
    )

    await manager.add_user_message(UserMessage(content="next"))

    assert len(manager.working_contents) == 1
    merged_content = manager.working_contents[0]["content"]
    assert "User sent another message" in merged_content
    assert "next" in merged_content
    save_history.assert_called_once()
    saved_messages = save_history.call_args.args[1]
    assert len(saved_messages) == 1
    assert "User sent another message" in saved_messages[0].content


def test_handle_interrupted_response_on_init_merges_and_clears(monkeypatch):
    status_monitor = DummyStatusMonitor(interrupted=True)
    manager = DummyContextManager(
        status_monitor=status_monitor,
        working_contents=[
            {"role": "user", "content": "first"},
            {"role": "user", "content": "second"},
        ],
    )

    history = [
        {"role": "user", "content": "first"},
        {"role": "user", "content": "second"},
    ]
    save_history = Mock()

    monkeypatch.setattr(session_manager, "load_all_message_history", Mock(return_value=history))
    monkeypatch.setattr(session_manager, "save_history", save_history)
    monkeypatch.setattr(
        message_factory_module,
        "message_factory",
        lambda data: DummyHistoryMessage(role=data["role"], content=data["content"]),
    )

    manager._handle_interrupted_response_on_init()

    assert len(manager.working_contents) == 1
    merged_content = manager.working_contents[0]["content"]
    assert "Previous response interrupted by user" in merged_content
    assert "second" in merged_content
    assert status_monitor.interrupt_cleared is True
    save_history.assert_called_once()


@pytest.mark.asyncio
async def test_inject_reminders_to_result_calls_injector(monkeypatch):
    manager = DummyContextManager()
    injector = Mock()
    injector.inject_to_tool_result = AsyncMock()
    monkeypatch.setattr(reminder_module, "ReminderInjector", Mock(return_value=injector))
    result = {"llm_content": {"parts": []}}

    await manager._inject_reminders_to_result(result)

    reminder_module.ReminderInjector.assert_called_once_with(manager.session_id, manager.agent_profile)
    injector.inject_to_tool_result.assert_awaited_once_with(result)


def test_clear_runtime_context_clears_and_resets_monitor(monkeypatch):
    manager = DummyContextManager(working_contents=[{"role": "user", "content": "hi"}])
    clear_monitor = Mock()
    monkeypatch.setattr(monitoring_module, "clear_status_monitor", clear_monitor)

    manager.clear_runtime_context()

    assert manager.working_contents == []
    clear_monitor.assert_called_once_with(manager.session_id)
