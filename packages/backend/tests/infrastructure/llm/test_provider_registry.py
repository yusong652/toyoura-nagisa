import sys
from types import ModuleType

import pytest

from backend.infrastructure.llm.shared.utils import provider_registry


def _register_dummy(monkeypatch, module_path: str, class_name: str):
    module = ModuleType(module_path)
    dummy_class = type(class_name, (), {})
    setattr(module, class_name, dummy_class)
    monkeypatch.setitem(sys.modules, module_path, module)
    return dummy_class


def test_get_message_formatter_class_returns_registered_class(monkeypatch):
    dummy_class = _register_dummy(
        monkeypatch,
        "backend.infrastructure.llm.providers.google.message_formatter",
        "GoogleMessageFormatter",
    )

    assert provider_registry.get_message_formatter_class("google") is dummy_class


def test_get_context_manager_class_returns_registered_class(monkeypatch):
    dummy_class = _register_dummy(
        monkeypatch,
        "backend.infrastructure.llm.providers.openai.context_manager",
        "OpenAIContextManager",
    )

    assert provider_registry.get_context_manager_class("openai") is dummy_class


def test_get_tool_manager_class_returns_registered_class(monkeypatch):
    dummy_class = _register_dummy(
        monkeypatch,
        "backend.infrastructure.llm.providers.openai.tool_manager",
        "OpenAIToolManager",
    )

    assert provider_registry.get_tool_manager_class("openai") is dummy_class


def test_get_message_formatter_class_raises_for_unknown_provider():
    with pytest.raises(ValueError, match="Unsupported provider"):
        provider_registry.get_message_formatter_class("unknown")


def test_is_provider_supported_checks_registry():
    assert provider_registry.is_provider_supported("openai") is True
    assert provider_registry.is_provider_supported("unknown") is False
