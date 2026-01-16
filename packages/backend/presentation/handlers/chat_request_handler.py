"""
Chat Request Handler - WebSocket entry point for chat request processing.

This handler serves as the primary entry point for WebSocket chat requests,
coordinating the complete request lifecycle:
- Request initialization and deduplication
- WebSocket status notifications (sent/read/error)
- Application service orchestration (Agent.execute(), ContentProcessor, Memory)
- Error handling and user interruption management

As a presentation layer component, it bridges WebSocket-specific concerns
(status updates, error notifications) with application layer business logic.
"""

import uuid
import logging
from backend.application.services.chat_service import PreparedUserMessage
from backend.application.services.contents.content_processor import process_content_pipeline
from backend.application.services.memory_service import save_session_conversation_memory
from backend.application.services.notifications import get_message_status_service
from backend.application.services.request_manager import request_manager
from backend.shared.exceptions import UserRejectionInterruption

logger = logging.getLogger(__name__)


async def process_chat_request(prepared_message: PreparedUserMessage) -> None:
    """
    Complete chat request processing pipeline.

    Handles the entire chat request lifecycle:
    1. Status notifications (sent/read/error)
    2. Agent execution with explicit instruction passing
    3. Content processing pipeline
    4. Memory persistence after successful completion
    5. Comprehensive error handling

    Args:
        prepared_message: PreparedUserMessage containing instruction and configuration

    Returns:
        None - All output is sent via WebSocket
    """
    session_id = prepared_message.session_id
    user_message_id = prepared_message.message_id

    # ========== PHASE 1: Request initialization and deduplication ==========
    request_id = f"REQ_{str(uuid.uuid4())[:8]}"

    # Use elegant request context manager for automatic lifecycle management
    async with request_manager.request_context(session_id, request_id, user_message_id):

        # ========== PHASE 1.5: Status notifications ==========
        status_service = get_message_status_service()
        if status_service and user_message_id:
            await status_service.notify_sent(session_id, user_message_id)

        try:
            # ========== PHASE 2: Get LLM response using AgentService ==========
            from backend.shared.utils.app_context import get_llm_client
            llm_client = get_llm_client()

            from backend.application.services.agent_service import AgentService
            agent_service = AgentService(llm_client)

            # Send WebSocket read status just before LLM processing starts
            if status_service and user_message_id:
                await status_service.notify_read(session_id, user_message_id)

            # Execute conversation turn via AgentService with explicit instruction
            # Agent is now responsible for message persistence
            result = await agent_service.process_chat(
                session_id=session_id,
                instruction=prepared_message.instruction,
                agent_profile=prepared_message.agent_profile,
                enable_memory=prepared_message.enable_memory,
            )

            # ========== PHASE 3: Content processing pipeline ==========
            if result.status == "success" and result.message:
                await process_content_pipeline(
                    result.message, session_id, message_id=result.message_id
                )

            # ========== PHASE 4: Memory persistence ==========
            # Note: Title generation happens in Agent.execute() (Application layer)
            if prepared_message.enable_memory:
                await save_session_conversation_memory(session_id)

        except UserRejectionInterruption as interruption:
            # User rejected tool execution - this is NOT an error
            print(f"[INFO] Request interrupted by user rejection in session {session_id}: {interruption.rejected_tools}")
            return

        except Exception as e:
            print(f"[ERROR] Streaming request {request_id} failed: {e}")
            import traceback
            traceback.print_exc()

            if user_message_id and status_service:
                await status_service.notify_error(session_id, user_message_id, str(e))

        # Request cleanup automatically handled by request_manager context
