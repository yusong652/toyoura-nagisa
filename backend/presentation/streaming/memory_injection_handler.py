"""
Memory injection handler for enhanced LLM context.

This module provides clean, decoupled memory injection functionality
that can be integrated into the main streaming pipeline using the
new SessionMemoryContextManager approach.
"""

import logging
from typing import Optional, Dict, Any
from backend.domain.models.messages import BaseMessage
from backend.shared.utils.memory_factory import get_memory_middleware

logger = logging.getLogger(__name__)


async def save_conversation_memory(
    user_message: BaseMessage,
    assistant_response: str,
    user_id: Optional[str] = None
) -> bool:
    """
    Save conversation turn to memory after successful response.
    
    Uses the new memory system for consistent cross-session memory handling.
    
    Args:
        user_message: The user's message object
        assistant_response: The assistant's response
        user_id: User identifier
    
    Returns:
        bool: True if save successful, False otherwise
    """
    try:
        # Save to memory if we have user message - use middleware for consistency
        if user_message and assistant_response:
            # Create assistant message object from response string
            from backend.domain.models.message_factory import message_factory_no_thinking
            assistant_message = message_factory_no_thinking({
                "role": "assistant",
                "content": assistant_response
            })
            
            middleware = get_memory_middleware()
            await middleware.save_conversation_turn(
                user_message=user_message,
                assistant_message=assistant_message,
                user_id=user_id
            )
            # Memory saving handled by Mem0 manager with detailed output
            return True
            
    except Exception as e:
        logger.warning(f"Failed to save conversation to memory: {e}")
    
    return False


async def handle_memory_management(
    action: str,
    session_id: str,
    user_id: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Handle memory management operations.
    
    This provides an API for managing memories directly, useful for
    debugging and user-controlled memory operations.
    
    Args:
        action: Action to perform (list, delete, update, toggle, etc.)
        session_id: Session ID
        user_id: User ID
        params: Additional parameters for the action
    
    Returns:
        Result of the memory operation
    """
    middleware = get_memory_middleware()
    manager = middleware.memory_manager
    
    try:
        if action == "list":
            # List all memories for user/session
            memories = await manager.get_all_memories(
                user_id=user_id,
                session_id=params.get("session_only") and session_id
            )
            return {
                "success": True,
                "action": action,
                "memories": memories,
                "count": len(memories)
            }
        
        elif action == "search":
            # Search memories
            query = params.get("query", "")
            limit = params.get("limit", 5)
            
            memories = await manager.search_memories(
                query=query,
                user_id=user_id,
                limit=limit
            )
            return {
                "success": True,
                "action": action,
                "query": query,
                "memories": memories,
                "count": len(memories)
            }
        
        elif action == "delete":
            # Delete memories
            memory_id = params.get("memory_id")
            delete_all = params.get("delete_all", False)
            
            if memory_id:
                success = await manager.delete_memory(memory_id=memory_id)
            elif delete_all:
                success = await manager.delete_memory(user_id=user_id)
            else:
                success = await manager.delete_memory(session_id=session_id)
            
            return {
                "success": success,
                "action": action,
                "deleted": memory_id or "all" if delete_all else f"session_{session_id}"
            }
        
        elif action == "toggle":
            # Toggle memory injection on/off
            enable = params.get("enable", True)
            middleware.enable_injection = enable
            
            return {
                "success": True,
                "action": action,
                "memory_enabled": enable
            }
        
        else:
            return {
                "success": False,
                "error": f"Unknown action: {action}"
            }
            
    except Exception as e:
        return {
            "success": False,
            "action": action,
            "error": str(e)
        }