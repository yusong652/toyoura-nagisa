"""
Memory injection handler for enhanced LLM context.

This module provides clean, decoupled memory injection functionality
that can be integrated into the main streaming pipeline using the
new SessionMemoryContextManager approach.
"""

import logging
from typing import Optional, Dict, Any
from backend.domain.models.messages import BaseMessage
from backend.shared.utils.memory_logging import log_memory_injection_result
from backend.shared.utils.performance import measure_time
from backend.shared.utils.memory_factory import get_memory_middleware

logger = logging.getLogger(__name__)



async def get_system_prompt_with_memory_context(
    session_id: str,
    user_message: BaseMessage,
    base_system_prompt: str,
    user_id: str = "default"
) -> str:
    """
    Get system prompt with integrated memory context for a session.
    
    This approach integrates memory context directly into the system prompt
    rather than injecting system messages into the conversation.
    
    Args:
        session_id: Current session ID
        user_message: User's message object
        base_system_prompt: Base system prompt
        user_id: User identifier
        
    Returns:
        str: Enhanced system prompt with memory context
    """
    try:
        # Define memory retrieval operation
        @measure_time
        async def get_memory_enhanced_prompt():
            # Get memory middleware (uses SessionMemoryContextManager internally)
            middleware = get_memory_middleware()
            
            # Get system prompt with memory context
            return await middleware.get_enhanced_system_prompt(
                base_system_prompt=base_system_prompt,
                user_message=user_message,
                session_id=session_id,
                user_id=user_id
            )
        
        # Execute with timing
        (system_prompt_with_memory, injection_result), total_retrieval_time_ms = await get_memory_enhanced_prompt()
        
        # Log memory injection results
        log_memory_injection_result(injection_result, total_retrieval_time_ms)
        
        return system_prompt_with_memory
        
    except Exception as e:
        logger.warning(f"Memory-enhanced system prompt failed: {e}")
        return base_system_prompt




# Old inject_memory_context method removed - use get_system_prompt_with_memory_context instead


async def save_conversation_memory(
    user_message: BaseMessage,
    assistant_response: str,
    session_id: str,
    user_id: str = "default"
) -> bool:
    """
    Save conversation turn to memory after successful response.
    
    Uses the new SessionMemoryContextManager for consistent memory handling.
    
    Args:
        user_message: The user's message object
        assistant_response: The assistant's response
        session_id: Current session ID
        user_id: User identifier
    
    Returns:
        bool: True if save successful, False otherwise
    """
    try:
        # Convert user message to format suitable for Mem0
        user_msg_for_memory = None
        if user_message and getattr(user_message, "role", None) == "user":
            content = getattr(user_message, "content", "")
            
            if isinstance(content, list):
                # Multimodal content - convert to proper Mem0 format
                # Mem0 expects OpenAI-compatible format with proper structure
                formatted_content = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            formatted_content.append({
                                "type": "text",
                                "text": item.get("text", "")
                            })
                        elif item.get("type") == "image_url":
                            formatted_content.append({
                                "type": "image_url",
                                "image_url": item.get("image_url", {})
                            })
                        # Handle legacy format where 'text' is direct key
                        elif "text" in item and "type" not in item:
                            formatted_content.append({
                                "type": "text", 
                                "text": item["text"]
                            })
                
                user_msg_for_memory = {
                    "role": "user",
                    "content": formatted_content
                }
            else:
                # Simple string content
                user_msg_for_memory = {
                    "role": "user", 
                    "content": str(content)
                }
        
        # Save to memory if we have user message - use middleware for consistency
        if user_msg_for_memory and assistant_response:
            middleware = get_memory_middleware()
            await middleware.save_conversation_turn(
                user_message=user_msg_for_memory,  # Pass dict for multimodal or str for text
                assistant_response=assistant_response,
                session_id=session_id,
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
    user_id: str = "default",
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
                limit=limit,
                session_id=params.get("session_only") and session_id
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