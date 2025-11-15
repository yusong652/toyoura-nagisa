"""
LLM response handler for coordinating streaming responses.

This module provides the main LLM response coordination,
managing request lifecycle, client validation, and pipeline orchestration.
"""

import uuid
import logging
from typing import Optional
from backend.presentation.streaming.content_processor import process_content_pipeline
from backend.application.services.memory_service import save_session_conversation_memory
from backend.application.services.notifications import get_message_status_service
from backend.application.services.request_manager import request_manager
from backend.shared.exceptions import UserRejectionInterruption

logger = logging.getLogger(__name__)


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
            # ========== PHASE 2: Get LLM response using ChatOrchestrator ==========
            # Get LLM client from app state
            from backend.shared.utils.app_context import get_llm_client
            llm_client = get_llm_client()

            # Create ChatOrchestrator with LLM client
            from backend.application.services.conversation import ChatOrchestrator
            orchestrator = ChatOrchestrator(llm_client)

            # Send WebSocket read status just before LLM processing starts
            if status_service and user_message_id:
                await status_service.notify_read(session_id, user_message_id)

            # Execute conversation turn via ChatOrchestrator (Application layer)
            # Business logic now properly separated from infrastructure
            final_message, streaming_message_id = await orchestrator.execute_conversation_turn(session_id)

            # ========== PHASE 3: Content processing pipeline ==========
            if final_message:
                # Process content via WebSocket
                # Note: keyword extraction is handled in content_processor
                # Pass streaming_message_id to avoid duplicate message creation
                await process_content_pipeline(
                    final_message, session_id, message_id=streaming_message_id
                )

            # ========== PHASE 4: Memory persistence ==========
            # Note: Title generation now happens in ChatOrchestrator (Application layer)
            # This maintains proper architecture: Application layer services can call each other
            # Save conversation to memory after successful response
            # Get enable_memory from the session's context manager
            context_manager = llm_client.get_or_create_context_manager(session_id)
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