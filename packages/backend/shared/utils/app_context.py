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
    Get default LLM client using cached factory and default configuration.

    This function should be used ONLY when session context is not available
    (e.g., app initialization, system checks). 
    
    For session-specific operations, use factory.create_client_with_config 
    with session_llm_config.

    Returns:
        LLMClientBase: Configured LLM client instance

    Raises:
        RuntimeError: If app is not initialized or LLM client not configured
    """
    factory = get_llm_factory()
    
    # Import here to avoid circular dependencies
    from backend.infrastructure.storage.llm_config_manager import get_default_llm_config
    
    default_config = get_default_llm_config()
    if not default_config:
        raise RuntimeError(
            "Primary LLM client not configured. "
            "Please configure your API key in the settings page or .env file."
        )
        
    return factory.create_client_with_config(
        provider=default_config["provider"],
        model=default_config["model"],
        app=get_app()
    )


def get_secondary_llm_client():
    """
    Get secondary LLM client using cached factory and default configuration.
    
    Falls back to primary client if secondary is not configured.

    Returns:
        LLMClientBase: Secondary LLM client instance

    Raises:
        RuntimeError: If app is not initialized or no LLM client is configured
    """
    factory = get_llm_factory()
    
    # Import here to avoid circular dependencies
    from backend.infrastructure.storage.llm_config_manager import get_default_llm_config
    
    default_config = get_default_llm_config()
    if not default_config:
        raise RuntimeError("No default LLM configuration found")
        
    # Use secondary_model if specified, otherwise use primary model
    model = default_config.get("secondary_model") or default_config["model"]
    
    return factory.create_client_with_config(
        provider=default_config["provider"],
        model=model,
        app=get_app()
    )


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
