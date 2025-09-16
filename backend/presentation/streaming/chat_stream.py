"""
Chat stream orchestrator for the presentation layer.

This module provides the high-level chat streaming functionality,
orchestrating memory injection, LLM response handling, and conversation persistence.
"""

import json
import uuid
from typing import List, AsyncGenerator, Optional
from backend.infrastructure.llm import LLMClientBase
from backend.domain.models.messages import BaseMessage
from backend.domain.models.message_factory import message_factory_no_thinking
from backend.infrastructure.storage.session_manager import load_history
from backend.infrastructure.tts.base import BaseTTS
from backend.config import get_llm_settings
from backend.presentation.streaming.llm_response_handler import handle_llm_response
from backend.presentation.streaming.memory_injection_handler import (
    save_conversation_memory
)
from backend.presentation.websocket.status_notification_service import get_status_notification_service


async def generate_chat_stream(
    session_id: str,
    recent_msgs: List[BaseMessage],
    llm_client: LLMClientBase,
    enable_memory: bool = True,
    agent_profile: str = "general",
    user_message_id: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """
    Enhanced chat stream generator with memory injection.

    This function integrates the complete streaming pipeline with memory context:
    1. Load conversation history
    2. Inject relevant memory context
    3. Generate LLM response with streaming
    4. Save conversation to memory for future retrieval

    Args:
        session_id: Current session ID
        recent_msgs: Recent conversation messages (unused, loaded from history)
        llm_client: LLM client instance
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
        await status_service.notify_sent(session_id, user_message_id)

    try:
        # Load conversation history without images
        recent_history = load_history(session_id)
        # Create messages without thinking blocks
        recent_msgs = [message_factory_no_thinking(msg) if isinstance(msg, dict) else msg for msg in recent_history]
        recent_messages_length = get_llm_settings().recent_messages_length
        recent_msgs = recent_msgs[-recent_messages_length:]
        
        # Extract latest user message for memory saving
        latest_user_message = None
        for msg in reversed(recent_msgs):
            if hasattr(msg, 'role') and msg.role == 'user':
                latest_user_message = msg
                break
        
        # Memory injection is now handled internally by LLM clients
        # based on agent_profile, session_id, and enable_memory flag

        # Send WebSocket read status just before LLM processing starts
        if status_service and user_message_id:
            await status_service.notify_read(session_id, user_message_id)

        # Process LLM response with messages and enhanced system prompt
        assistant_response = None
        async for chunk in handle_llm_response(
            recent_msgs,
            session_id,
            llm_client,
            agent_profile=agent_profile,
            enable_memory=enable_memory,
            user_message_id=user_message_id
        ):
            # Capture assistant response for memory saving
            if isinstance(chunk, str) and 'data:' in chunk:
                try:
                    # Parse the chunk to extract content
                    json_str = chunk.replace('data: ', '').strip()
                    if json_str:
                        data = json.loads(json_str)
                        if 'text' in data and data['text']:
                            if assistant_response is None:
                                assistant_response = ""
                            assistant_response += data['text']
                except:
                    pass
            
            yield chunk
        
        # Save conversation to memory after successful response
        if enable_memory and assistant_response and latest_user_message:
            await save_conversation_memory(
                user_message=latest_user_message,  # Use already extracted user message
                assistant_response=assistant_response
            )
            
    except Exception as e:
        print(f"[ERROR] API Request {request_id} - Exception in generate(): {e}")
        
        # Send error status via WebSocket
        if status_service and user_message_id:
            await status_service.notify_error(session_id, user_message_id, str(e))
        
        yield f"data: {json.dumps({'type': 'NAGISA_TOOL_USE_CONCLUDED'})}\n\n"
        error_data = {
            'type': 'error',
            'error': str(e)
        }
        yield f"data: {json.dumps(error_data)}\n\n"
        raise e