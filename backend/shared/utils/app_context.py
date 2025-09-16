"""
Application context utilities for global access to FastAPI app instance.

This module provides a clean way to access the FastAPI app instance and its state
from anywhere in the application without parameter passing.
"""

from typing import Optional
from fastapi import FastAPI


# Global app instance
_app_instance: Optional[FastAPI] = None


def get_app() -> Optional[FastAPI]:
    """
    Get the global FastAPI app instance.

    Returns:
        Optional[FastAPI]: FastAPI app instance, None if not set
    """
    return _app_instance


def set_app(app: FastAPI) -> None:
    """
    Set the global FastAPI app instance.

    Args:
        app: FastAPI application instance
    """
    global _app_instance
    _app_instance = app


def get_tts_engine():
    """
    Get TTS engine from app state.

    Returns:
        BaseTTS: TTS engine instance from app state

    Raises:
        RuntimeError: If app is not initialized or TTS engine not found
    """
    app = get_app()
    if not app:
        raise RuntimeError("FastAPI app not initialized")

    if not hasattr(app.state, 'tts_engine'):
        raise RuntimeError("TTS engine not found in app state")

    return app.state.tts_engine


def get_llm_client():
    """
    Get LLM client from app state.

    Returns:
        LLMClientBase: LLM client instance from app state

    Raises:
        RuntimeError: If app is not initialized or LLM client not found
    """
    app = get_app()
    if not app:
        raise RuntimeError("FastAPI app not initialized")

    if not hasattr(app.state, 'llm_client'):
        raise RuntimeError("LLM client not found in app state")

    return app.state.llm_client


def get_llm_client_dependency(request=None):
    """
    FastAPI dependency function for LLM client.

    This is a wrapper around get_llm_client() for FastAPI dependency injection.
    The request parameter is accepted for compatibility but not used since we
    access the app instance globally.

    Args:
        request: FastAPI request object (unused, for compatibility)

    Returns:
        LLMClientBase: LLM client instance from app state
    """
    return get_llm_client()


def get_tts_engine_dependency(request=None):
    """
    FastAPI dependency function for TTS engine.

    This is a wrapper around get_tts_engine() for FastAPI dependency injection.
    The request parameter is accepted for compatibility but not used since we
    access the app instance globally.

    Args:
        request: FastAPI request object (unused, for compatibility)

    Returns:
        BaseTTS: TTS engine instance from app state
    """
    return get_tts_engine()


def get_mcp_client():
    """
    Get MCP client from app state.

    Returns:
        Client: MCP client instance from app state

    Raises:
        RuntimeError: If app is not initialized or MCP client not found
    """
    app = get_app()
    if not app:
        raise RuntimeError("FastAPI app not initialized")

    if not hasattr(app.state, 'mcp_client'):
        raise RuntimeError("MCP client not found in app state")

    return app.state.mcp_client


def get_mcp_server():
    """
    Get MCP server from app state.

    Returns:
        FastMCP: MCP server instance from app state

    Raises:
        RuntimeError: If app is not initialized or MCP server not found
    """
    app = get_app()
    if not app:
        raise RuntimeError("FastAPI app not initialized")

    if not hasattr(app.state, 'mcp'):
        raise RuntimeError("MCP server not found in app state")

    return app.state.mcp