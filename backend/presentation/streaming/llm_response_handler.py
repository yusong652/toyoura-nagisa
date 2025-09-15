"""
LLM response handler for coordinating streaming responses.

This module provides the main LLM response coordination,
managing request lifecycle, client validation, and pipeline orchestration.
"""

import json
import uuid
import asyncio
import logging
from typing import Dict, Any, List, AsyncGenerator, Optional
from backend.infrastructure.llm import LLMClientBase
from backend.domain.models.messages import BaseMessage
from backend.domain.models.message_factory import message_factory
from backend.infrastructure.storage.session_manager import load_all_message_history, update_session_title
from backend.shared.utils.helpers import should_generate_title, generate_title_for_session
from backend.presentation.models.websocket_messages import (
    create_error_message, create_tool_use_message
)
from backend.presentation.streaming.content_processor import process_content_pipeline

logger = logging.getLogger(__name__)

# Global request state management
ACTIVE_REQUESTS: Dict[str, str] = {}  # session_id -> request_id
ACTIVE_REQUESTS_LOCK = asyncio.Lock()


async def handle_llm_response(
    recent_msgs: List[BaseMessage],
    session_id: str,
    llm_client: LLMClientBase,
    tts_engine,
    agent_profile: str = "general",
    enable_memory: bool = True,
    user_message_id: Optional[str] = None
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Enhanced LLM Response Handler - Real-time streaming architecture.
    
    Modern real-time streaming design optimized for immediate tool call notifications:
    1. Real-time tool call notifications - Immediate status push during tool execution
    2. Streaming response processing - Maintains existing TTS and content processing logic
    3. State isolation - Anti-duplication mechanism separated from business logic
    4. Error propagation - Unified error handling and recovery
    5. Observability - Complete execution tracking and monitoring
    
    Args:
        recent_msgs: Recent conversation messages
        session_id: Current session ID
        llm_client: LLM client instance
        tts_engine: TTS engine instance
        agent_profile: Agent profile type for tool filtering and prompt customization
        enable_memory: Whether to enable memory injection (controlled by frontend toggle)
        user_message_id: Optional message ID for WebSocket status updates
    
    Yields:
        Streaming response chunks in SSE format
    """
    # ========== PHASE 1: Request initialization and deduplication ==========
    request_id = f"REQ_{str(uuid.uuid4())[:8]}"
    
    # Optimized anti-duplication mechanism - reduce lock contention
    async with ACTIVE_REQUESTS_LOCK:
        if session_id in ACTIVE_REQUESTS:
            existing_request = ACTIVE_REQUESTS[session_id]
            error_msg = f"Duplicate request detected. Session {session_id} already has active request {existing_request}"

            # Send error status via WebSocket if message ID is available
            if user_message_id:
                from backend.presentation.websocket.status_notification_service import get_status_notification_service
                status_service = get_status_notification_service()
                if status_service:
                    await status_service.notify_error(session_id, user_message_id, error_msg)

            error_data = create_error_message(
                error=error_msg,
                session_id=session_id,
                recoverable=False
            )
            yield f"data: {json.dumps(error_data)}\n\n"
            return
        ACTIVE_REQUESTS[session_id] = request_id

    try:
        final_message = None
        execution_metadata = None
        
        # Use new streaming method - Real-time tool call notifications
        # Pass enhanced system prompt if available
        get_response_kwargs = {
            "session_id": session_id,
            "agent_profile": agent_profile,
            "enable_memory": enable_memory
        }
        
        print(f"[DEBUG] handle_llm_response: calling llm_client.get_response with agent_profile={agent_profile}, session_id={session_id}, enable_memory={enable_memory}")
        
        async for item in llm_client.get_response(
            recent_msgs, 
            **get_response_kwargs
        ):
            if isinstance(item, tuple):
                # Final result: (final_message, execution_metadata)
                final_message, execution_metadata = item
                break
            elif isinstance(item, dict):
                # Real-time notification: tool call status updates
                yield f"data: {json.dumps(item)}\n\n"
        
        # ========== PHASE 4: Content processing pipeline ==========
        if final_message:
            async for chunk in process_content_pipeline(
                final_message, session_id, tts_engine, request_id, execution_metadata
            ):
                yield chunk
        
        # ========== PHASE 5: Post-processing pipeline ==========
        if execution_metadata:
            async for chunk in process_post_pipeline(session_id, llm_client, request_id):
                yield chunk
        
    except Exception as e:
        print(f"[ERROR] Streaming request {request_id} failed: {e}")
        import traceback
        traceback.print_exc()

        # Send error status via WebSocket if message ID is available
        if user_message_id:
            from backend.presentation.websocket.status_notification_service import get_status_notification_service
            status_service = get_status_notification_service()
            if status_service:
                await status_service.notify_error(session_id, user_message_id, str(e))

        # Ensure tool use end signal is sent
        tool_end_msg = create_tool_use_message(is_using=False, session_id=session_id)
        yield f"data: {json.dumps(tool_end_msg)}\n\n"

        error_data = create_error_message(
            error=f"Request processing failed: {str(e)}",
            session_id=session_id,
            details={"request_id": request_id, "traceback": traceback.format_exc()}
        )
        yield f"data: {json.dumps(error_data)}\n\n"
        
    finally:
        # ========== PHASE 6: Cleanup and release ==========
        async with ACTIVE_REQUESTS_LOCK:
            if session_id in ACTIVE_REQUESTS and ACTIVE_REQUESTS[session_id] == request_id:
                del ACTIVE_REQUESTS[session_id]
                # Streaming request completed


async def process_post_pipeline(
    session_id: str,
    llm_client: LLMClientBase,
    request_id: str
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Post-processing pipeline - Handle title generation and other background tasks.
    
    Non-blocking background processing that doesn't affect the main flow.
    
    Args:
        session_id: Current session ID
        llm_client: LLM client instance
        request_id: Request ID for debugging
    
    Yields:
        Post-processing results like title updates
    """
    try:
        loaded_history = load_all_message_history(session_id)
        history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in loaded_history]
        
        if should_generate_title(session_id, history_msgs):
            new_title = await generate_title_for_session(session_id, llm_client)
            if new_title:
                update_success = update_session_title(session_id, new_title)
                if update_success:
                    title_update_data = {
                        'type': 'TITLE_UPDATE',
                        'payload': {
                            'session_id': session_id,
                            'title': new_title
                        }
                    }
                    yield f"data: {json.dumps(title_update_data)}\n\n"
    except Exception as e:
        # Post-processing failures should not affect the main flow, just log
        print(f"[WARNING] Post-processing failed for request {request_id}: {e}")