import pytest
from typing import Any, Dict, List, Optional, cast
from unittest.mock import Mock

from backend.infrastructure.llm.base.client import LLMClientBase
from backend.infrastructure.llm.base.context_manager import BaseContextManager
from backend.infrastructure.llm.base.response_processor import BaseResponseProcessor, BaseStreamingProcessor
from backend.domain.models.streaming import StreamingChunk
import backend.infrastructure.llm.base.client as client_module


class DummyContextManager(BaseContextManager):
    def __init__(self, provider_name: str, session_id: str):
        self._provider_name = provider_name
        self.session_id = session_id
        self.cleared = False

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

    def clear_runtime_context(self) -> None:
        self.cleared = True


class DummyResponseProcessor(BaseResponseProcessor):
    @staticmethod
    def extract_text_content(response) -> str:
        return f"text:{response}"

    @staticmethod
    def extract_tool_calls(response) -> List[Dict[str, Any]]:
        return []

    @staticmethod
    def format_response_for_storage(response, tool_calls: Optional[List[Dict[str, Any]]] = None):
        return Mock()

    @staticmethod
    def create_streaming_processor() -> BaseStreamingProcessor:
        class DummyStreamingProcessor(BaseStreamingProcessor):
            def process_event(self, event: Any) -> List[Any]:
                return []

        return DummyStreamingProcessor()

    @staticmethod
    def construct_response_from_chunks(chunks: List[StreamingChunk]) -> Dict[str, Any]:
        return {"chunks": chunks}


class DummyClient(LLMClientBase):
    def __init__(self, processor: Optional[BaseResponseProcessor] = None):
        super().__init__()
        self.provider_name = "dummy"
        self._processor = processor or DummyResponseProcessor()

    async def call_api_with_context(
        self,
        context_contents: List[Dict[str, Any]],
        api_config: Dict[str, Any],
        **kwargs,
    ) -> Any:
        return {"status": "ok"}

    async def call_api_with_context_streaming(
        self,
        context_contents: List[Dict[str, Any]],
        api_config: Dict[str, Any],
        **kwargs,
    ):
        if False:
            yield

    def _get_response_processor(self) -> BaseResponseProcessor:
        return self._processor

    def _get_provider_config(self) -> Any:
        return {"debug": False}

    def _build_api_config(
        self,
        system_prompt: str,
        tool_schemas: Optional[List[Any]],
    ) -> Dict[str, Any]:
        return {"system_prompt": system_prompt, "tool_schemas": tool_schemas}

    def _get_context_manager_class(self):
        return DummyContextManager


def test_format_messages_uses_provider_formatter(monkeypatch):
    client = DummyClient()

    class DummyFormatter:
        @staticmethod
        def format_messages(messages):
            return [{"role": "user", "content": "ok"}]

    get_formatter = Mock(return_value=DummyFormatter)
    monkeypatch.setattr(client_module, "get_message_formatter_class", get_formatter)

    result = client.format_messages([Mock()])

    get_formatter.assert_called_once_with("dummy")
    assert result == [{"role": "user", "content": "ok"}]


def test_format_messages_requires_provider_name():
    client = DummyClient()
    client.provider_name = None

    with pytest.raises(ValueError, match="provider_name"):
        client.format_messages([Mock()])


def test_extract_text_delegates_to_response_processor():
    client = DummyClient()

    assert client.extract_text("response") == "text:response"


def test_extract_web_search_sources_returns_data_when_available():
    processor = DummyResponseProcessor()
    setattr(
        cast(Any, processor),
        "extract_web_search_sources",
        lambda response, debug=False: [{"title": "source"}],
    )
    client = DummyClient(processor=processor)

    assert client.extract_web_search_sources("response") == [{"title": "source"}]


def test_extract_web_search_sources_returns_empty_when_missing_method():
    processor = DummyResponseProcessor()
    setattr(cast(Any, processor), "extract_web_search_sources", None)
    client = DummyClient(processor=processor)

    assert client.extract_web_search_sources("response") == []


def test_get_or_create_context_manager_caches_instance():
    client = DummyClient()

    first = client.get_or_create_context_manager("session-1")
    second = client.get_or_create_context_manager("session-1")
    other = client.get_or_create_context_manager("session-2")

    assert first is second
    assert first is not other
    assert first.session_id == "session-1"
    assert first._provider_name == "dummy"


def test_clear_context_manager_forces_recreate():
    client = DummyClient()

    first = client.get_or_create_context_manager("session-1")
    client.clear_context_manager("session-1")
    second = client.get_or_create_context_manager("session-1")

    assert first is not second


def test_cleanup_session_context_clears_runtime_and_tool_tracking():
    client = DummyClient()
    client.tool_manager = Mock()
    client.tool_manager.clear_session_read_tracking = Mock()

    context_manager = client.get_or_create_context_manager("session-1")
    assert isinstance(context_manager, DummyContextManager)
    client.cleanup_session_context("session-1")

    assert context_manager.cleared is True
    assert "session-1" not in client._session_context_managers
    client.tool_manager.clear_session_read_tracking.assert_called_once_with("session-1")
