"""
Memory injection handler for enhanced LLM context.

This module provides clean, decoupled memory injection functionality
that can be integrated into the main streaming pipeline using the
new SessionMemoryContextManager approach.
"""

import logging
import time
from typing import Dict, Any, List, Tuple, Optional
from backend.domain.models.messages import BaseMessage
from backend.infrastructure.memory import (
    MemoryInjectionMiddleware
)
from backend.config.memory import MemoryConfig
from backend.presentation.models.websocket_messages import create_status_message

logger = logging.getLogger(__name__)

# Global memory injection middleware instance
_memory_middleware: Optional[MemoryInjectionMiddleware] = None


async def get_system_prompt_with_memory_context(
    session_id: str,
    user_query: str,
    base_system_prompt: str,
    user_id: str = "default",
    enable_memory: Optional[bool] = None
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Get system prompt with integrated memory context for a session.
    
    This approach integrates memory context directly into the system prompt
    rather than injecting system messages into the conversation.
    
    Args:
        session_id: Current session ID
        user_query: User's query text
        base_system_prompt: Base system prompt
        user_id: User identifier
        enable_memory: Flag to enable/disable memory injection (uses config default if None)
        
    Returns:
        Tuple of (system_prompt_with_memory, status_updates)
    """
    status_updates = []
    
    # Use config if enable_memory not explicitly provided
    if enable_memory is None:
        config = MemoryConfig()
        enable_memory = config.should_inject_memory()
    
    if not enable_memory:
        return base_system_prompt, status_updates
    
    try:
        # Start timing for memory retrieval
        retrieval_start_time = time.time()
        
        # Add status update about memory retrieval
        memory_status = create_status_message(
            status="retrieving_memories",
            session_id=session_id,
            details={"message": "Retrieving relevant memories...", "start_time": retrieval_start_time}
        )
        status_updates.append(memory_status)
        
        # Get memory middleware (uses SessionMemoryContextManager internally)
        middleware = get_memory_middleware()
        
        # Get system prompt with memory context
        system_prompt_with_memory, injection_result = await middleware.get_enhanced_system_prompt(
            base_system_prompt=base_system_prompt,
            user_query=user_query,
            session_id=session_id,
            user_id=user_id
        )
        
        # Calculate timing
        retrieval_end_time = time.time()
        total_retrieval_time_ms = (retrieval_end_time - retrieval_start_time) * 1000
        
        # Create success status based on injection result
        if injection_result.success and injection_result.injected_count > 0:
            memory_complete = create_status_message(
                status="memory_injected",
                session_id=session_id,
                details={
                    "injected_count": injection_result.injected_count,
                    "injection_time_ms": injection_result.injection_time_ms,
                    "total_retrieval_time_ms": total_retrieval_time_ms,
                    "context_tokens": injection_result.context_tokens,
                    "message": f"System prompt enhanced with {injection_result.injected_count} relevant memories in {total_retrieval_time_ms:.1f}ms"
                }
            )
        else:
            memory_complete = create_status_message(
                status="memory_injection_skipped",
                session_id=session_id,
                details={
                    "total_retrieval_time_ms": total_retrieval_time_ms,
                    "message": injection_result.error or "No relevant memories found"
                }
            )
        
        status_updates.append(memory_complete)
        return system_prompt_with_memory, status_updates
        
    except Exception as e:
        logger.warning(f"Memory-enhanced system prompt failed: {e}")
        error_status = create_status_message(
            status="memory_error",
            session_id=session_id,
            details={"message": "Memory retrieval failed, using base prompt", "error": str(e)}
        )
        status_updates.append(error_status)
        return base_system_prompt, status_updates


def get_memory_middleware() -> MemoryInjectionMiddleware:
    """
    Get or create the global memory injection middleware.
    
    Returns:
        MemoryInjectionMiddleware instance
    """
    global _memory_middleware
    if _memory_middleware is None:
        # Create with MemoryConfig from settings
        config = MemoryConfig()
        _memory_middleware = MemoryInjectionMiddleware(config=config)
    return _memory_middleware


# Old inject_memory_context method removed - use get_system_prompt_with_memory_context instead


async def save_conversation_memory(
    recent_msgs: List[BaseMessage],
    assistant_response: str,
    session_id: str,
    user_id: str = "default"
) -> bool:
    """
    Save conversation turn to memory after successful response.
    
    Uses the new SessionMemoryContextManager for consistent memory handling.
    
    Args:
        recent_msgs: Recent conversation messages
        assistant_response: The assistant's response
        session_id: Current session ID
        user_id: User identifier
    
    Returns:
        bool: True if save successful, False otherwise
    """
    try:
        # Extract last user message
        user_msg = None
        for msg in reversed(recent_msgs):
            if getattr(msg, "role", None) == "user":
                content = getattr(msg, "content", "")
                # Handle multimodal content (list format) or simple string content
                if isinstance(content, list):
                    # Extract text from list of content items
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict):
                            if "text" in item:
                                text_parts.append(item["text"])
                            elif item.get("type") == "text":
                                text_parts.append(item.get("text", ""))
                    user_msg = " ".join(text_parts)
                else:
                    # Simple string content
                    user_msg = str(content)
                break
        
        # Save to memory if we have user message - use middleware for consistency
        if user_msg and assistant_response:
            middleware = get_memory_middleware()
            await middleware.save_conversation_turn(
                user_message=user_msg,
                assistant_response=assistant_response,
                session_id=session_id,
                user_id=user_id
            )
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