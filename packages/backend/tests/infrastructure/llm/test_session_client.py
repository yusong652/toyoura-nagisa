import pytest
from unittest.mock import Mock

from backend.infrastructure.llm.session_client import get_session_llm_client
import backend.infrastructure.storage.session_manager as session_manager
import backend.infrastructure.storage.llm_config_manager as llm_config_manager
import backend.shared.utils.app_context as app_context


def _setup_factory(monkeypatch):
    factory = Mock()
    factory.create_client_with_config = Mock(return_value="client")
    monkeypatch.setattr(app_context, "get_llm_factory", Mock(return_value=factory))
    monkeypatch.setattr(app_context, "get_app", Mock(return_value="app"))
    return factory


def test_get_session_llm_client_uses_session_config(monkeypatch):
    monkeypatch.setattr(
        session_manager,
        "get_session_llm_config",
        Mock(return_value={"provider": "openai", "model": "gpt-4"}),
    )
    monkeypatch.setattr(
        llm_config_manager,
        "get_default_llm_config",
        Mock(return_value={"provider": "anthropic", "model": "claude"}),
    )
    factory = _setup_factory(monkeypatch)

    client = get_session_llm_client("session-1")

    assert client == "client"
    factory.create_client_with_config.assert_called_once_with(
        provider="openai",
        model="gpt-4",
        app="app",
    )


def test_get_session_llm_client_falls_back_to_default(monkeypatch):
    monkeypatch.setattr(
        session_manager,
        "get_session_llm_config",
        Mock(return_value=None),
    )
    monkeypatch.setattr(
        llm_config_manager,
        "get_default_llm_config",
        Mock(return_value={"provider": "anthropic", "model": "claude"}),
    )
    factory = _setup_factory(monkeypatch)

    client = get_session_llm_client("session-2")

    assert client == "client"
    factory.create_client_with_config.assert_called_once_with(
        provider="anthropic",
        model="claude",
        app="app",
    )


def test_get_session_llm_client_raises_when_missing_config(monkeypatch):
    monkeypatch.setattr(
        session_manager,
        "get_session_llm_config",
        Mock(return_value=None),
    )
    monkeypatch.setattr(
        llm_config_manager,
        "get_default_llm_config",
        Mock(return_value=None),
    )
    _setup_factory(monkeypatch)

    with pytest.raises(ValueError, match="Could not determine LLM configuration"):
        get_session_llm_client("session-3")
