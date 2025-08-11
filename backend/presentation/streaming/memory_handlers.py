"""
Memory-aware request handlers with automatic context injection.

This module extends the base handlers to integrate automatic memory
injection into the LLM conversation flow.
"""

import json
import logging
from typing import Dict, Any, List, AsyncGenerator, Optional
from backend.infrastructure.llm import LLMClientBase
from backend.domain.models.messages import BaseMessage
from backend.infrastructure.tts.base import BaseTTS
from backend.infrastructure.memory import (
    MemoryInjectionMiddleware,
    MemoryPerformanceGuard
)
from backend.presentation.streaming.handlers import handle_llm_response as base_handle_llm_response
from backend.presentation.models.websocket_messages import create_status_message

logger = logging.getLogger(__name__)

# Global memory injection middleware instance
_memory_middleware: Optional[MemoryInjectionMiddleware] = None


def get_memory_middleware() -> MemoryInjectionMiddleware:
    """
    Get or create the global memory injection middleware.
    
    Returns:
        MemoryInjectionMiddleware instance
    """
    global _memory_middleware
    if _memory_middleware is None:
        _memory_middleware = MemoryInjectionMiddleware(
            enable_injection=True  # Can be configured from settings
        )
    return _memory_middleware


async def handle_llm_response(
    recent_msgs: List[BaseMessage],
    session_id: str,
    llm_client: LLMClientBase,
    tts_engine: BaseTTS,
    user_id: str = "default",
    enable_memory: bool = True
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Memory-aware LLM response handler with automatic context injection.
    
    This handler wraps the base handler and adds memory context injection
    before passing messages to the LLM. It maintains full compatibility
    with the existing streaming architecture.
    
    Args:
        recent_msgs: Recent conversation messages
        session_id: Current session ID
        llm_client: LLM client instance
        tts_engine: TTS engine instance
        user_id: User identifier for memory retrieval
        enable_memory: Flag to enable/disable memory injection
    
    Yields:
        Streaming response chunks with memory status updates
    """
    
    # Convert BaseMessage objects to dict format for injection
    messages_dict = []
    for msg in recent_msgs:
        if hasattr(msg, 'to_dict'):
            messages_dict.append(msg.to_dict())
        else:
            # Fallback for messages without to_dict method
            messages_dict.append({
                "role": getattr(msg, "role", "user"),
                "content": getattr(msg, "content", "")
            })
    
    # Perform memory injection if enabled
    injected_msgs = messages_dict
    injection_result = None
    
    if enable_memory:
        try:
            # Send status update about memory retrieval
            memory_status = create_status_message(
                status="retrieving_memories",
                message="Retrieving relevant memories...",
                session_id=session_id
            )
            yield f"data: {json.dumps(memory_status)}\n\n"
            
            # Get memory middleware
            middleware = get_memory_middleware()
            
            # Inject memory context with performance guard
            injected_msgs, injection_result = await MemoryPerformanceGuard.safe_inject_memory(
                middleware=middleware,
                messages=messages_dict,
                session_id=session_id,
                user_id=user_id
            )
            
            # Send injection result status
            if injection_result.success:
                memory_complete = create_status_message(
                    status="memory_injected",
                    message=f"Injected {injection_result.injected_count} relevant memories",
                    session_id=session_id,
                    details={
                        "injected_count": injection_result.injected_count,
                        "injection_time_ms": injection_result.injection_time_ms,
                        "context_tokens": injection_result.context_tokens
                    }
                )
            else:
                memory_complete = create_status_message(
                    status="memory_injection_skipped",
                    message=injection_result.error or "No relevant memories found",
                    session_id=session_id
                )
            
            yield f"data: {json.dumps(memory_complete)}\n\n"
            
        except Exception as e:
            logger.warning(f"Memory injection failed: {e}")
            # Continue without memory on failure
            error_status = create_status_message(
                status="memory_error",
                message="Memory retrieval failed, continuing without context",
                session_id=session_id,
                details={"error": str(e)}
            )
            yield f"data: {json.dumps(error_status)}\n\n"
    
    # Convert injected messages back to BaseMessage objects
    injected_base_msgs = []
    for msg in injected_msgs:
        # Skip system memory context messages when converting back
        if msg.get("metadata", {}).get("type") == "memory_context":
            # Keep memory context as a system message
            from backend.domain.models.messages import SystemMessage
            injected_base_msgs.append(SystemMessage(
                content=msg["content"],
                metadata=msg.get("metadata", {})
            ))
        else:
            # Convert regular messages
            from backend.domain.models.message_factory import message_factory
            if isinstance(msg, dict):
                injected_base_msgs.append(message_factory(msg))
            else:
                injected_base_msgs.append(msg)
    
    # Pass to base handler with memory-injected messages
    async for chunk in base_handle_llm_response(
        recent_msgs=injected_base_msgs,
        session_id=session_id,
        llm_client=llm_client,
        tts_engine=tts_engine
    ):
        yield chunk
    
    # After successful response, save conversation to memory
    if enable_memory and injection_result and injection_result.success:
        try:
            # Extract last user message and assistant response
            user_msg = None
            assistant_msg = None
            
            for msg in reversed(recent_msgs):
                if not user_msg and getattr(msg, "role", None) == "user":
                    user_msg = getattr(msg, "content", "")
                elif not assistant_msg and getattr(msg, "role", None) == "assistant":
                    assistant_msg = getattr(msg, "content", "")
                
                if user_msg and assistant_msg:
                    break
            
            # Save to memory if we have both messages
            if user_msg and assistant_msg:
                middleware = get_memory_middleware()
                await middleware.save_conversation_turn(
                    user_message=user_msg,
                    assistant_response=assistant_msg,
                    session_id=session_id,
                    user_id=user_id
                )
                
        except Exception as e:
            logger.warning(f"Failed to save conversation to memory: {e}")
            # Non-critical error, don't fail the response


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
        action: Action to perform (list, delete, update, etc.)
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