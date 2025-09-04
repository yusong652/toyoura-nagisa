"""
Memory context integration for prompt system.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

async def build_memory_section_from_session(session_id: str, user_id: Optional[str] = None) -> Optional[str]:
    """
    Retrieve and format relevant memories from session history.
    
    This function extracts the latest user message from session history and uses it
    to search for relevant memories, then returns the formatted memory content.
    
    Args:
        session_id: Session ID for loading message history
        user_id: User ID for memory operations (uses config default if None)
        
    Returns:
        Formatted memory content string, or None if no memories found
    """
    try:
        from backend.infrastructure.storage.session_manager import load_history
        from backend.shared.utils.memory_factory import get_memory_middleware
        from backend.config.memory import MemoryConfig
        from backend.domain.models.memory_context import MemoryContext
        
        # Check if memory injection is enabled
        memory_config = MemoryConfig()
        if not memory_config.should_inject_memory():
            return None
        
        # Load session history and extract latest user message text
        recent_history = load_history(session_id)
        
        if not recent_history:
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
            return None
        
        # Determine effective user_id (Mem0 requires user or agent id)
        effective_user_id = user_id or memory_config.mem0_user_id
        
        # Initialize/reuse singleton memory middleware
        memory_middleware = get_memory_middleware()
        
        # Create memory context
        memory_context = MemoryContext(
            session_id=session_id,
            query=latest_user_text,
            top_k=memory_config.max_memories_to_inject,
            exclude_recent_minutes=memory_config.get_time_filter_minutes(),
            memory_types=None,
            relevance_threshold=memory_config.memory_relevance_threshold
        )
        
        # Search for relevant memories across all sessions (cross-session memory retrieval)
        print(f"[DEBUG] Cross-session memory search: user_id={effective_user_id}, query='{latest_user_text}', session_id=None")
        memories = await memory_middleware.memory_manager.get_relevant_memories_for_context(
            query_text=latest_user_text,
            session_id=None,  # Search all user memories across all sessions
            top_k=memory_context.top_k,
            exclude_recent_minutes=memory_context.exclude_recent_minutes,
            memory_types=memory_context.memory_types,
            user_id=effective_user_id
        )
        
        print(f"[DEBUG] Found {len(memories)} memories for cross-session search")
        if memories:
            for i, memory in enumerate(memories):
                print(f"[DEBUG] Memory {i}: {memory}")
        
        if not memories:
            print(f"[DEBUG] No memories found for user_id={effective_user_id} with query='{latest_user_text}'")
            return None
        
        # Format memories for injection
        memory_context.memories = memories
        formatted_context = memory_context.format_for_injection()
        
        if not formatted_context or not formatted_context.strip():
            return None
        
        # Return raw memory content, let caller format as section
        return formatted_context
        
    except Exception as e:
        logger.error(f"Failed to build memory section: {e}")
        return None
