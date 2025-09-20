"""
LLM response handler for coordinating streaming responses.

This module provides the main LLM response coordination,
managing request lifecycle, client validation, and pipeline orchestration.
"""

import json
import uuid
import asyncio
import logging
from typing import Dict, Optional
from backend.infrastructure.llm import LLMClientBase
from backend.domain.models.messages import BaseMessage
from backend.domain.models.message_factory import message_factory
from backend.infrastructure.storage.session_manager import load_all_message_history, update_session_title
from backend.shared.utils.helpers import should_generate_title, generate_title_for_session
from backend.presentation.websocket.message_types import (
    create_error_message, create_tool_use_message, create_message, MessageType
)
from backend.presentation.streaming.content_processor import process_content_pipeline

logger = logging.getLogger(__name__)

# Global request state management
ACTIVE_REQUESTS: Dict[str, str] = {}  # session_id -> request_id
ACTIVE_REQUESTS_LOCK = asyncio.Lock()


async def send_title_update_notification(session_id: str, new_title: str) -> None:
    """
    Send title update notification via WebSocket.

    Args:
        session_id: Session ID for which the title was updated
        new_title: The new title for the session
    """
    try:
        # Get WebSocket connection manager directly
        from backend.infrastructure.websocket.connection_manager import get_connection_manager

        connection_manager = get_connection_manager()
        if not connection_manager:
            logger.warning(f"No connection manager available for title update notification")
            return

        # Create title update message
        title_update_msg = create_message(
            MessageType.TITLE_UPDATE,
            session_id=session_id,
            payload={
                "session_id": session_id,
                "title": new_title
            }
        )

        # Send via WebSocket
        await connection_manager.send_json(
            session_id,
            title_update_msg.model_dump()
        )

        logger.info(f"Title update notification sent for session {session_id}: {new_title}")

    except Exception as e:
        logger.error(f"Failed to send title update notification: {e}")
        # Don't re-raise - this is a non-critical notification


async def handle_llm_response(
    session_id: str,
    agent_profile: str = "general",
    enable_memory: bool = True,
    user_message_id: Optional[str] = None
) -> None:
    """
    Enhanced LLM Response Handler - Real-time streaming architecture.

    Modern real-time streaming design optimized for immediate tool call notifications:
    1. Real-time tool call notifications - Immediate status push during tool execution
    2. Streaming response processing - Maintains existing TTS and content processing logic
    3. State isolation - Anti-duplication mechanism separated from business logic
    4. Error propagation - Unified error handling and recovery
    5. Observability - Complete execution tracking and monitoring

    Args:
        session_id: Current session ID for loading conversation history
        agent_profile: Agent profile type for tool filtering and prompt customization
        enable_memory: Whether to enable memory injection (controlled by frontend toggle)
        user_message_id: Optional message ID for WebSocket status updates

    Returns:
        None - All output is sent via WebSocket
    """
    # ========== PHASE 1: Request initialization and deduplication ==========
    request_id = f"REQ_{str(uuid.uuid4())[:8]}"

    # Get LLM client from app state
    from backend.shared.utils.app_context import get_llm_client
    llm_client = get_llm_client()
    
    # Optimized anti-duplication mechanism - reduce lock contention
    async with ACTIVE_REQUESTS_LOCK:
        if session_id in ACTIVE_REQUESTS:
            existing_request = ACTIVE_REQUESTS[session_id]
            error_msg = f"Duplicate request detected. Session {session_id} already has active request {existing_request}"

            # Send error status via WebSocket if message ID is available
            if user_message_id:
                from backend.application.services.notifications import get_message_status_service
                status_service = get_message_status_service()
                if status_service:
                    await status_service.notify_error(session_id, user_message_id, error_msg)

            return
        ACTIVE_REQUESTS[session_id] = request_id

    try:
        # ========== PHASE 2: Load conversation history ==========
        # Load conversation history without images for LLM processing
        from backend.infrastructure.storage.session_manager import load_history
        from backend.domain.models.message_factory import message_factory_no_thinking
        from backend.config import get_llm_settings

        recent_history = load_history(session_id)
        # Create messages without thinking blocks
        recent_msgs = [message_factory_no_thinking(msg) if isinstance(msg, dict) else msg for msg in recent_history]
        recent_messages_length = get_llm_settings().recent_messages_length
        recent_msgs = recent_msgs[-recent_messages_length:]

        final_message = None
        execution_metadata = None

        # Use new streaming method - Real-time tool call notifications
        # Pass enhanced system prompt if available
        get_response_kwargs = {
            "session_id": session_id,
            "agent_profile": agent_profile,
            "enable_memory": enable_memory
        }

        async for item in llm_client.get_response(
            recent_msgs,
            **get_response_kwargs
        ):
            if isinstance(item, tuple):
                # Final result: (final_message, execution_metadata)
                final_message, execution_metadata = item
                break
            elif isinstance(item, dict):
                # Skip dict notifications - WebSocket handles all status updates
                continue
        
        # ========== PHASE 4: Content processing pipeline ==========
        if final_message:
            # Process content via WebSocket - no longer yields SSE chunks
            await process_content_pipeline(
                final_message, session_id, request_id, execution_metadata
            )
        
        # ========== PHASE 5: Post-processing pipeline ==========
        if execution_metadata:
            # Post-processing no longer yields - handled via WebSocket
            await process_post_pipeline(session_id, request_id)
        
    except Exception as e:
        print(f"[ERROR] Streaming request {request_id} failed: {e}")
        import traceback
        traceback.print_exc()

        # Send error status via WebSocket if message ID is available
        if user_message_id:
            from backend.application.services.notifications import get_message_status_service
            status_service = get_message_status_service()
            if status_service:
                await status_service.notify_error(session_id, user_message_id, str(e))

        # Send error notifications via WebSocket - no SSE yields needed
        
    finally:
        # ========== PHASE 6: Cleanup and release ==========
        async with ACTIVE_REQUESTS_LOCK:
            if session_id in ACTIVE_REQUESTS and ACTIVE_REQUESTS[session_id] == request_id:
                del ACTIVE_REQUESTS[session_id]
                # Streaming request completed


async def process_post_pipeline(
    session_id: str,
    request_id: str
) -> None:
    """
    Post-processing pipeline - Handle title generation and other background tasks.

    Non-blocking background processing that doesn't affect the main flow.

    Args:
        session_id: Current session ID
        request_id: Request ID for debugging

    Returns:
        None - Title updates sent via WebSocket
    """
    try:
        # Get LLM client from app state
        from backend.shared.utils.app_context import get_llm_client
        llm_client = get_llm_client()

        loaded_history = load_all_message_history(session_id)
        history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in loaded_history]

        if should_generate_title(session_id, history_msgs):
            new_title = await generate_title_for_session(session_id, llm_client)
            if new_title:
                update_success = update_session_title(session_id, new_title)
                if update_success:
                    # Send title update via WebSocket
                    await send_title_update_notification(session_id, new_title)
                    print(f"[INFO] Title updated for session {session_id}: {new_title}")
    except Exception as e:
        # Post-processing failures should not affect the main flow, just log
        print(f"[WARNING] Post-processing failed for request {request_id}: {e}")