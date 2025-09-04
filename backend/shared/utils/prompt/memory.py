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


async def build_memory_section_from_session(session_id: str, user_id: str = "default") -> Optional[str]:
    """
    Retrieve and format relevant memories from session history.
    
    This function extracts the latest user message from session history and uses it
    to search for relevant memories, then returns the formatted memory content.
    
    Args:
        session_id: Session ID for loading message history
        user_id: User ID for memory operations
        
    Returns:
        Formatted memory content string, or None if no memories found
    """
    try:
        from backend.infrastructure.storage.session_manager import load_history
        from backend.infrastructure.memory.memory_injection import MemoryInjectionMiddleware
        from backend.config.memory import MemoryConfig
        from backend.domain.models.memory_context import MemoryContext
        
        # Check if memory injection is enabled
        memory_config = MemoryConfig()
        if not memory_config.should_inject_memory():
            print("[DEBUG] Memory injection disabled, skipping memory section")
            return None
        
        # Load session history and extract latest user message text
        recent_history = load_history(session_id)
        print(f"[DEBUG] Loaded {len(recent_history) if recent_history else 0} messages for memory section")
        
        if not recent_history:
            print("[DEBUG] No session history found")
            return None
        
        # Find latest user message and extract text directly from history
        latest_user_text = None
        for msg in reversed(recent_history):
            if isinstance(msg, dict) and msg.get('role') == 'user':
                content = msg.get('content', [])
                if isinstance(content, list):
                    # Extract text from content array
                    for item in content:
                        if isinstance(item, dict) and 'text' in item:
                            latest_user_text = item['text']
                            break
                elif isinstance(content, str):
                    latest_user_text = content
                
                if latest_user_text:
                    break
        
        if not latest_user_text or not latest_user_text.strip():
            print("[DEBUG] No user message text found for memory search")
            return None
        
        print(f"[DEBUG] Using query text for memory search: {latest_user_text}")
        
        # Initialize memory middleware and search for relevant memories
        memory_middleware = MemoryInjectionMiddleware(config=memory_config)
        
        # Create memory context
        memory_context = MemoryContext(
            session_id=session_id,
            query=latest_user_text,
            top_k=memory_config.max_memories_to_inject,
            exclude_recent_minutes=memory_config.get_time_filter_minutes(),
            memory_types=None,
            relevance_threshold=memory_config.memory_relevance_threshold
        )
        
        # Search for relevant memories
        memories = await memory_middleware.memory_manager.get_relevant_memories_for_context(
            query_text=latest_user_text,
            session_id=None,  # Search all user memories
            top_k=memory_context.top_k,
            exclude_recent_minutes=memory_context.exclude_recent_minutes,
            memory_types=memory_context.memory_types,
            user_id=user_id
        )
        
        print(f"[DEBUG] Found {len(memories)} memories for memory section")
        
        if not memories:
            print("[DEBUG] No relevant memories found")
            return None
        
        # Format memories for injection
        memory_context.memories = memories
        formatted_context = memory_context.format_for_injection()
        
        if not formatted_context or not formatted_context.strip():
            print("[DEBUG] No formatted memory context generated")
            return None
        
        print(f"[DEBUG] Generated memory content with {len(formatted_context)} characters")
        
        # Return raw memory content, let caller format as section
        return formatted_context
        
    except Exception as e:
        logger.error(f"Failed to build memory section: {e}")
        print(f"[DEBUG] Memory section build failed: {e}")
        return None


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