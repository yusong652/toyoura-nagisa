"""
Content processing pipeline for LLM responses.

This module handles the processing of final LLM responses,
including message saving, keyword extraction, and TTS preparation.
"""

import json
from typing import Dict, Any, AsyncGenerator, Optional, List, Union
from backend.domain.models.messages import BaseMessage
from backend.domain.models.message_factory import message_factory
from backend.application.services.message_service import MessageService
from backend.presentation.websocket.message_types import MessageType, create_message
# Import will be resolved at runtime - avoid circular import
# from backend.presentation.streaming.tts_processor import process_tts_pipeline


async def process_content_pipeline(
    final_message: BaseMessage,  # AssistantMessage with List content
    session_id: str,
    message_id: Optional[str] = None  # Optional: use existing message ID from streaming
) -> None:
    """
    Content processing pipeline for final LLM responses.

    This pipeline handles:
    1. Content extraction from structured messages
    2. Message persistence to conversation history
    3. Keyword extraction for emotional expressions
    4. TTS processing coordination via WebSocket

    Args:
        final_message: Final LLM response message
        session_id: Current session ID
        message_id: Optional existing message ID (from streaming), if None creates new message

    Returns:
        None: All processing is handled via WebSocket communication
    """
    # Type assertion: AssistantMessage always has List content at this point
    # after being formatted by response processor
    content = final_message.content

    # Ensure content is List[Dict[str, Any]] for type safety
    if not isinstance(content, list):
        raise TypeError(f"Expected List content, got {type(content)}")

    content_list: List[Dict[str, Any]] = content  # Type-safe assignment

    # Extract text content for keyword parsing and TTS (excluding thinking blocks)
    text_content = ""
    for item in content_list:
        if isinstance(item, dict) and item.get('type') == 'text':
            text_content += item.get('text', '')

    # Extract emotional keywords from text content
    from backend.shared.utils.text_parser import parse_llm_output
    parsed_result = parse_llm_output(text_content)
    extracted_keyword = parsed_result['keyword']

    # Save or update message in conversation history
    if message_id:
        # Update existing message (created during streaming)
        MessageService.update_assistant_message(message_id, content_list, session_id)
        ai_msg_id = message_id
    else:
        # Create new message (non-streaming path)
        ai_msg_id = MessageService.save_assistant_message(
            content_list,  # Content is guaranteed to be List[Dict[str, Any]]
            session_id
        )
    
    # Send emotional keywords via WebSocket if available
    if extracted_keyword:
        from backend.application.services.notifications import get_emotion_notification_service
        emotion_service = get_emotion_notification_service()
        if emotion_service:
            await emotion_service.notify_emotion_keyword(session_id, extracted_keyword, ai_msg_id)
    
    # Process TTS pipeline if clean text content is available
    if parsed_result['text'].strip():
        # Send MESSAGE_CREATE only if message was not created during streaming
        if not message_id:
            await send_message_create_via_websocket(session_id, ai_msg_id)

        # Get TTS engine from app state
        from backend.shared.utils.app_context import get_tts_engine
        tts_engine = get_tts_engine()

        # Dynamic import to avoid circular dependency
        from backend.presentation.streaming.tts_processor import process_tts_pipeline
        # Use cleaned text without keyword markers for TTS
        async for chunk in process_tts_pipeline(parsed_result['text'], tts_engine):
            # Send TTS chunks via WebSocket
            # For streaming messages: audio-only (text already displayed)
            # For non-streaming messages: text+audio (for incremental text display)
            is_streaming = bool(message_id)
            await send_tts_chunk_via_websocket(session_id, chunk, ai_msg_id, is_streaming)
    else:
        # Send MESSAGE_CREATE only if message was not created during streaming
        if not message_id:
            await send_message_create_via_websocket(session_id, ai_msg_id)

        # Send empty text chunk for consistency when only keywords are present
        empty_chunk_data = {'text': '', 'audio': None, 'index': 0}
        empty_sse_chunk = f"data: {json.dumps(empty_chunk_data)}\n\n"
        is_streaming = bool(message_id)
        await send_tts_chunk_via_websocket(session_id, empty_sse_chunk, ai_msg_id, is_streaming)


async def send_message_create_via_websocket(session_id: str, message_id: str):
    """
    Send MESSAGE_CREATE event via WebSocket to create a new bot message.

    Notifies frontend to create a new bot message with the specified ID
    before TTS chunks are processed.

    Args:
        session_id: WebSocket session ID
        message_id: ID for the new message to create
    """
    try:
        # Get WebSocket connection manager
        from backend.infrastructure.websocket.connection_manager import get_connection_manager
        connection_manager = get_connection_manager()

        if not connection_manager or not connection_manager.is_connected_sync(session_id):
            return  # No WebSocket connection available

        # Create MESSAGE_CREATE message
        from backend.presentation.websocket.message_types import MessageType, create_message
        create_message_msg = create_message(
            MessageType.MESSAGE_CREATE,
            session_id=session_id,
            message_id=message_id,
            role="assistant",
            initial_text="",
            streaming=True
        )

        # Send to WebSocket client
        await connection_manager.send_json(session_id, create_message_msg.model_dump())

    except Exception as e:
        # Don't break the main flow if WebSocket sending fails
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to send MESSAGE_CREATE via WebSocket to session {session_id}: {e}")


async def send_tts_chunk_via_websocket(
    session_id: str,
    sse_chunk: str,
    message_id: Optional[str] = None,
    is_streaming: bool = False
):
    """
    Send TTS chunk data via WebSocket to frontend.

    Parses SSE formatted chunk and sends as structured WebSocket TTS_CHUNK message
    for frontend text-audio queue processing.

    Args:
        session_id: WebSocket session ID
        sse_chunk: SSE formatted chunk from TTS processor
        message_id: Optional message ID for association
        is_streaming: If True, only send audio (text already displayed via streaming)
    """
    try:
        # Get WebSocket connection manager
        from backend.infrastructure.websocket.connection_manager import get_connection_manager
        connection_manager = get_connection_manager()

        if not connection_manager or not connection_manager.is_connected_sync(session_id):
            return  # No WebSocket connection available

        # Parse SSE chunk data
        if not sse_chunk.startswith('data: '):
            return

        json_str = sse_chunk.replace('data: ', '').strip()
        if not json_str or json_str == '\n\n':
            return

        chunk_data = json.loads(json_str)

        # For streaming messages: clear text field (audio-only)
        # For non-streaming messages: keep text field (incremental display)
        text_content = '' if is_streaming else chunk_data.get('text', '')

        # Create WebSocket TTS chunk message
        tts_message = create_message(
            MessageType.TTS_CHUNK,
            session_id=session_id,
            message_id=message_id,
            text=text_content,
            audio=chunk_data.get('audio'),
            index=chunk_data.get('index', 0),
            processing_time=chunk_data.get('processing_time'),
            engine_status=chunk_data.get('engine_status', 'success'),
            error=chunk_data.get('error'),
            is_final=chunk_data.get('failed', False) or chunk_data.get('pipeline_failed', False)
        )

        # Send to WebSocket client
        await connection_manager.send_json(session_id, tts_message.model_dump())

    except Exception as e:
        # Don't break the main flow if WebSocket sending fails
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to send TTS chunk via WebSocket to session {session_id}: {e}")