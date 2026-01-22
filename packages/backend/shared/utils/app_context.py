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
        RuntimeError: If app is not initialized or LLM client not configured
    """
    app = get_app()
    if not app:
        raise RuntimeError("FastAPI app not initialized")

    if not hasattr(app.state, 'llm_client') or app.state.llm_client is None:
        raise RuntimeError(
            "Primary LLM client not configured. "
            "Please configure your API key in the settings page or .env file."
        )

    return app.state.llm_client


def get_secondary_llm_client():
    """
    Get secondary LLM client from app state (for SubAgents).
    
    Falls back to primary client if secondary is not configured.

    Returns:
        LLMClientBase: Secondary LLM client instance from app state

    Raises:
        RuntimeError: If app is not initialized or no LLM client is configured
    """
    app = get_app()
    if not app:
        raise RuntimeError("FastAPI app not initialized")

    # Try secondary first
    if hasattr(app.state, 'secondary_llm_client') and app.state.secondary_llm_client is not None:
        return app.state.secondary_llm_client
    
    # Fall back to primary
    return get_llm_client()


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


def get_llm_factory():
    """
    Get LLM factory from app state.

    The factory is used to create custom LLM clients based on
    runtime configuration (provider and model selection).

    Returns:
        LLMFactory: LLM factory instance from app state

    Raises:
        RuntimeError: If app is not initialized or LLM factory not found
    """
    app = get_app()
    if not app:
        raise RuntimeError("FastAPI app not initialized")

    if not hasattr(app.state, 'llm_factory'):
        raise RuntimeError("LLM factory not found in app state")

    return app.state.llm_factory
