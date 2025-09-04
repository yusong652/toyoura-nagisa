"""
Memory context integration for prompt system.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def build_memory_section(memory_context: str) -> str:
    """
    Build memory context section for system prompt.
    
    Args:
        memory_context: Formatted memory context string
        
    Returns:
        Memory section with proper formatting
    """
    if not memory_context or not memory_context.strip():
        return ""
    
    return f"## Relevant Context from Memory\n\n{memory_context.strip()}"


async def save_conversation_to_memory(
    user_message: Any,  # BaseMessage type
    assistant_message: Any,  # BaseMessage type
    session_id: str,
    user_id: str = "default",
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Save conversation turn to memory.
    
    This function provides a centralized way to save conversations to memory
    from the prompt builder context.
    
    Args:
        user_message: User's BaseMessage object
        assistant_message: Assistant's BaseMessage object
        session_id: Session ID
        user_id: User ID
        metadata: Additional metadata
    """
    try:
        from backend.infrastructure.memory.memory_injection import MemoryInjectionMiddleware
        from backend.config.memory import MemoryConfig
        
        memory_config = MemoryConfig()
        
        # Skip if memory saving is disabled
        if not memory_config.should_save_memory():
            return
        
        memory_middleware = MemoryInjectionMiddleware(config=memory_config)
        
        await memory_middleware.save_conversation_turn(
            user_message=user_message,
            assistant_message=assistant_message,
            session_id=session_id,
            user_id=user_id,
            metadata=metadata
        )
        
    except Exception as e:
        logger.error(f"Failed to save conversation to memory: {e}")