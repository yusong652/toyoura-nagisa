"""
Chat stream orchestrator for the presentation layer.

This module provides the high-level chat streaming functionality,
orchestrating memory injection, LLM response handling, and conversation persistence.
"""

import uuid
import logging
from typing import AsyncGenerator, Optional
from backend.presentation.streaming.llm_response_handler import process_chat_request
from backend.presentation.streaming.memory_injection_handler import (
    save_session_conversation_memory
)
from backend.application.services.notifications import get_message_status_service

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
    # Process complete chat request (all logic now handled internally)
    await process_chat_request(session_id,
                              agent_profile=agent_profile,
                              enable_memory=enable_memory,
                              user_message_id=user_message_id)