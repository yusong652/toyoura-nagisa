"""
Session-scoped LLM Client Provider.

This module provides a unified way to retrieve the correct LLM client for a given session.
It enforces the rule that every session must have its own determined LLM configuration.
"""

import logging
from typing import Optional
from backend.infrastructure.llm.base.client import LLMClientBase

logger = logging.getLogger(__name__)

def get_session_llm_client(session_id: str) -> LLMClientBase:
    """
    Get the LLM client configured for a specific session.
    
    This is the standard way to obtain an LLM client in the application.
    It resolves the session's specific configuration (provider/model) and 
    creates/retrieves a cached client instance.
    
    Args:
        session_id: The session identifier
        
    Returns:
        LLMClientBase: Configured LLM client
        
    Raises:
        ValueError: If no configuration can be found for the session
    """
    from backend.infrastructure.storage.session_manager import get_session_llm_config
    from backend.infrastructure.storage.llm_config_manager import get_default_llm_config
    from backend.shared.utils.app_context import get_llm_factory, get_app
    
    # 1. Try to get session-specific configuration
    config = get_session_llm_config(session_id)
    
    # 2. Fallback logic (Safety net for legacy/broken sessions)
    # Even though "every session must have a client", if data is missing, 
    # we fallback to system default to allow the session to recover/function.
    if not config:
        logger.warning(f"Session {session_id} missing LLM config, falling back to system default.")
        default_config = get_default_llm_config()
        if default_config:
            config = {
                "provider": default_config["provider"],
                "model": default_config["model"]
            }
            
    if not config:
        raise ValueError(f"Could not determine LLM configuration for session {session_id}")
        
    # 3. Create client using factory (which handles caching)
    return get_llm_factory().create_client_with_config(
        provider=config["provider"],
        model=config["model"],
        app=get_app()
    )
