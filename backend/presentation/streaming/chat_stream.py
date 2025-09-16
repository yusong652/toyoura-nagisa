"""
Chat stream orchestrator for the presentation layer.

This module provides the high-level chat streaming functionality,
orchestrating memory injection, LLM response handling, and conversation persistence.
"""

import uuid
import logging
from typing import AsyncGenerator, Optional
from backend.presentation.streaming.llm_response_handler import handle_llm_response
from backend.presentation.streaming.memory_injection_handler import (
    save_session_conversation_memory
)
from backend.presentation.websocket.status_notification_service import get_status_notification_service

logger = logging.getLogger(__name__)


async def generate_chat_stream(
    session_id: str,
    enable_memory: bool = True,
    agent_profile: str = "general",
    user_message_id: Optional[str] = None
) -> None:
    """
    Enhanced chat stream generator with memory injection.

    This function integrates the complete streaming pipeline with memory context:
    1. Generate LLM response with streaming (messages loaded internally)
    2. Save conversation to memory for future retrieval

    Args:
        session_id: Current session ID
        enable_memory: Whether to enable memory injection
        agent_profile: Agent profile type for tool selection
        user_message_id: Optional user message ID for status tracking

    Yields:
        SSE formatted response chunks
    """
    # Generate unique request ID for debugging
    request_id = str(uuid.uuid4())[:8]

    # Send WebSocket status update if service is available and message ID provided
    status_service = get_status_notification_service()
    if status_service and user_message_id:
        print(f"[STATUS] Sending 'sent' status for message {user_message_id} in session {session_id}")
        await status_service.notify_sent(session_id, user_message_id)
    elif user_message_id:
        print(f"[WARNING] Status service not available for session {session_id}")

    try:
        # Send WebSocket read status just before LLM processing starts
        if status_service and user_message_id:
            print(f"[STATUS] Sending 'read' status for message {user_message_id} in session {session_id}")
            await status_service.notify_read(session_id, user_message_id)
        elif user_message_id:
            print(f"[WARNING] Cannot send read status - service not available for session {session_id}")

        # Process LLM response (messages loaded internally)
        await handle_llm_response(session_id,
                                  agent_profile=agent_profile,
                                  enable_memory=enable_memory,
                                  user_message_id=user_message_id)
        # Save conversation to memory after successful response
        if enable_memory:
            await save_session_conversation_memory(session_id)
            
    except Exception as e:
        print(f"[ERROR] API Request {request_id} - Exception in generate(): {e}")
        
        # Send error status via WebSocket
        if status_service and user_message_id:
            await status_service.notify_error(session_id, user_message_id, str(e))
        raise e