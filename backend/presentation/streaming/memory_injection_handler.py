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


async def save_session_conversation_memory(session_id: str) -> bool:
    """
    Save latest conversation turn from session to memory.

    Automatically extracts the latest user and assistant messages from session history
    and saves them to memory for future context enhancement.

    Args:
        session_id: Session ID to extract conversation from

    Returns:
        bool: True if save successful, False otherwise
    """
    try:
        # Get latest user and assistant messages from session
        from backend.infrastructure.storage.session_manager import get_latest_user_message, get_latest_n_messages

        # Get latest user message
        latest_user_message = get_latest_user_message(session_id)
        if not latest_user_message:
            logger.warning(f"No user message found in session {session_id} for memory saving")
            return False

        # Get latest messages to find the most recent assistant response
        latest_messages = get_latest_n_messages(session_id, 3)  # Get last 3 to be safe
        latest_assistant_message = None

        for msg in reversed(latest_messages):
            if msg.role == 'assistant':
                latest_assistant_message = msg
                break

        if not latest_assistant_message:
            logger.warning(f"No assistant message found in session {session_id} for memory saving")
            return False

        # Extract text from assistant message
        from backend.domain.models.message_factory import extract_text_from_message
        assistant_text = extract_text_from_message(latest_assistant_message)

        if not assistant_text:
            logger.warning(f"No text content in assistant message for session {session_id}")
            return False

        # Save to memory using existing function
        return await save_conversation_memory(
            user_message=latest_user_message,
            assistant_response=assistant_text
        )

    except Exception as e:
        logger.error(f"Failed to save session conversation to memory: {e}")
        return False


async def save_conversation_memory(
    user_message: BaseMessage,
    assistant_response: str
) -> bool:
    """
    Save conversation turn to memory after successful response.

    Uses the new memory system for consistent cross-session memory handling.

    Args:
        user_message: The user's message object
        assistant_response: The assistant's response

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
                assistant_message=assistant_message
            )
            # Memory saving handled by Mem0 manager with detailed output
            return True
            
    except Exception as e:
        logger.warning(f"Failed to save conversation to memory: {e}")
    
    return False


async def handle_memory_management(
    action: str,
    session_id: str,
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Handle memory management operations.

    This provides an API for managing memories directly, useful for
    debugging and user-controlled memory operations.

    Args:
        action: Action to perform (list, delete, update, toggle, etc.)
        session_id: Session ID
        params: Additional parameters for the action

    Returns:
        Result of the memory operation
    """
    middleware = get_memory_middleware()
    manager = middleware.memory_manager

    # Use config default for user_id
    user_id = middleware.config.mem0_user_id

    try:
        if action == "list":
            # List all memories for user (cross-session)
            memories = await manager.get_all_memories(
                user_id=user_id
            )
            return {
                "success": True,
                "action": action,
                "memories": memories,
                "count": len(memories)
            }
        
        elif action == "search":
            # Search memories
            query = ""
            limit = 5
            if params:
                query = str(params.get("query", ""))
                limit = int(params.get("limit", 5))
            
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
            memory_id = None
            delete_all = False
            if params:
                memory_id = params.get("memory_id")
                delete_all = bool(params.get("delete_all", False))

            if memory_id:
                success = await manager.delete_memory(memory_id=str(memory_id))
            elif delete_all:
                success = await manager.delete_memory(user_id=user_id)
            else:
                # Default: delete all memories for user (since memory is cross-session)
                success = await manager.delete_memory(user_id=user_id)
            
            return {
                "success": success,
                "action": action,
                "deleted": memory_id or "all" if delete_all else f"session_{session_id}"
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