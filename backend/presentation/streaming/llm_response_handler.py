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
from contextlib import asynccontextmanager
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

logger = logging.getLogger(__name__)


class RequestManager:
    """
    Elegant request state management with automatic lifecycle handling.

    Provides clean context manager interface for request deduplication
    and state cleanup, eliminating the need for manual lock management
    in business logic.
    """

    def __init__(self):
        self._active_requests: Dict[str, str] = {}  # session_id -> request_id
        self._lock = asyncio.Lock()

    async def try_start_request(self, session_id: str, request_id: str, user_message_id: Optional[str] = None) -> bool:
        """
        Attempt to start a new request, rejecting if session already has active request.

        Args:
            session_id: Session identifier
            request_id: Unique request identifier
            user_message_id: Optional message ID for error notifications

        Returns:
            bool: True if request started successfully, False if duplicate detected
        """
        async with self._lock:
            if session_id in self._active_requests:
                existing_request = self._active_requests[session_id]
                error_msg = f"Duplicate request detected. Session {session_id} already has active request {existing_request}"

                # Send error notification if message ID available
                if user_message_id:
                    status_service = get_message_status_service()
                    if status_service:
                        await status_service.notify_error(session_id, user_message_id, error_msg)

                return False

            self._active_requests[session_id] = request_id
            return True

    async def finish_request(self, session_id: str, request_id: str) -> None:
        """
        Complete request and clean up state.

        Args:
            session_id: Session identifier
            request_id: Request identifier (for verification)
        """
        async with self._lock:
            # Only remove if it's the same request (defensive programming)
            if (session_id in self._active_requests and
                self._active_requests[session_id] == request_id):
                del self._active_requests[session_id]

    @asynccontextmanager
    async def request_context(self, session_id: str, request_id: str, user_message_id: Optional[str] = None):
        """
        Context manager for automatic request lifecycle management.

        Args:
            session_id: Session identifier
            request_id: Unique request identifier
            user_message_id: Optional message ID for error notifications

        Raises:
            Exception: If duplicate request detected (via return from context)
        """
        if not await self.try_start_request(session_id, request_id, user_message_id):
            # Duplicate request detected, early return (no cleanup needed)
            return

        try:
            yield  # Execute the request
        finally:
            await self.finish_request(session_id, request_id)


# Global request manager instance
request_manager = RequestManager()


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
    agent_profile: str = "general",
    enable_memory: bool = True,
    user_message_id: Optional[str] = None
) -> None:
    """
    Complete chat request processing pipeline.

    Handles the entire chat request lifecycle:
    1. Status notifications (sent/read/error)
    2. LLM response processing with real-time tool notifications
    3. Memory persistence after successful completion
    4. Comprehensive error handling
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

            # ========== PHASE 5.5: Memory persistence ==========
            # Save conversation to memory after successful response
            if enable_memory:
                await save_session_conversation_memory(session_id)

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