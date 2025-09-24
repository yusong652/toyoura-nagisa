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
from backend.presentation.streaming.memory_injection_handler import save_session_conversation_memory
from backend.application.services.notifications import get_message_status_service
from backend.application.services.request_manager import request_manager
from backend.shared.exceptions import UserRejectionInterruption

logger = logging.getLogger(__name__)


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


async def process_chat_request(
    session_id: str,
    user_message_id: Optional[str] = None
) -> None:
    """
    Complete chat request processing pipeline using session-based approach.

    Handles the entire chat request lifecycle using simplified parameter passing:
    1. Status notifications (sent/read/error)
    2. LLM response processing with real-time tool notifications
    3. Memory persistence after successful completion
    4. Comprehensive error handling

    All configuration (agent_profile, enable_memory) is retrieved from the session's
    context manager, eliminating the need for complex parameter passing.

    Args:
        session_id: Current session ID for accessing context manager and configuration
        user_message_id: Optional message ID for WebSocket status updates

    Returns:
        None - All output is sent via WebSocket
    """
    # ========== PHASE 1: Request initialization and deduplication ==========
    request_id = f"REQ_{str(uuid.uuid4())[:8]}"

    # Use elegant request context manager for automatic lifecycle management
    async with request_manager.request_context(session_id, request_id, user_message_id):

        # ========== PHASE 1.5: Status notifications ==========
        # Send WebSocket status update if service is available and message ID provided
        status_service = get_message_status_service()
        if status_service and user_message_id:
            await status_service.notify_sent(session_id, user_message_id)

        try:
            # Send WebSocket read status just before LLM processing starts
            if status_service and user_message_id:
                await status_service.notify_read(session_id, user_message_id)

            # ========== PHASE 2: Get LLM response using session-based approach ==========
            # Get LLM client from app state
            from backend.shared.utils.app_context import get_llm_client
            llm_client = get_llm_client()

            # Use simplified session-based response method - All configuration retrieved from context manager
            final_message, execution_metadata = await llm_client.get_response_from_session(session_id)

            # ========== PHASE 3: Content processing pipeline ==========
            if final_message:
                # Process content via WebSocket
                await process_content_pipeline(
                    final_message, session_id, request_id, execution_metadata
                )

            # ========== PHASE 4: Post-processing pipeline ==========
            if execution_metadata:
                # Post-processing handled via WebSocket
                await process_post_pipeline(session_id, request_id)

            # ========== PHASE 5: Memory persistence ==========
            # Save conversation to memory after successful response
            # Get enable_memory from the session's context manager
            context_manager = llm_client.get_context_manager(session_id)
            if context_manager and getattr(context_manager, 'enable_memory', True):
                await save_session_conversation_memory(session_id)

        except UserRejectionInterruption as interruption:
            # User rejected tool execution - this is NOT an error
            print(f"[INFO] Request interrupted by user rejection in session {session_id}: {interruption.rejected_tools}")

            # Context already saved by tool calling loop
            # NO content processing (TTS, post-processing, etc.)
            # Simply return and wait for user's next input
            return

        except Exception as e:
            print(f"[ERROR] Streaming request {request_id} failed: {e}")
            import traceback
            traceback.print_exc()

            # Send error status via WebSocket if message ID is available
            if user_message_id:
                if status_service:
                    await status_service.notify_error(session_id, user_message_id, str(e))

        # Request cleanup automatically handled by request_manager context


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