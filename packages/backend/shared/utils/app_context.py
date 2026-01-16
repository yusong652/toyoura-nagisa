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


def get_secondary_llm_client():
    """
    Get secondary LLM client from app state (for SubAgents).

    The secondary client uses a lighter/cheaper model (e.g., gemini-2.5-flash)
    to reduce RPM consumption on the primary model.

    Falls back to primary client if secondary is not configured.

    Returns:
        LLMClientBase: Secondary LLM client instance from app state

    Raises:
        RuntimeError: If app is not initialized
    """
    app = get_app()
    if not app:
        raise RuntimeError("FastAPI app not initialized")

    # Fall back to primary client if secondary not available
    if not hasattr(app.state, 'secondary_llm_client'):
        return get_llm_client()

    return app.state.secondary_llm_client


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
