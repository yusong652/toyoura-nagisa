"""
Content processing pipeline for LLM responses.

This module handles the processing of final LLM responses,
including message saving, keyword extraction, and TTS preparation.
"""

import json
from typing import Dict, Any, AsyncGenerator, Optional
from backend.domain.models.messages import BaseMessage
from backend.domain.models.message_factory import message_factory
from backend.infrastructure.storage.session_manager import load_all_message_history
from backend.shared.utils.helpers import process_assistant_text_message
from backend.presentation.websocket.message_types import MessageType, create_message
# Import will be resolved at runtime - avoid circular import
# from backend.presentation.streaming.tts_processor import process_tts_pipeline


async def process_content_pipeline(
    final_message: BaseMessage,
    session_id: str,
    request_id: str,
    execution_metadata: Optional[Dict[str, Any]] = None
) -> AsyncGenerator[str, None]:
    """
    Content processing pipeline for final LLM responses.

    This pipeline handles:
    1. Content extraction from structured messages
    2. Message persistence to conversation history
    3. Keyword extraction for emotional expressions
    4. TTS processing coordination

    Args:
        final_message: Final LLM response message
        session_id: Current session ID
        request_id: Request ID for debugging
        execution_metadata: Optional execution metadata with keywords

    Yields:
        Content processing results including message IDs, keywords, and TTS chunks
    """
    if not hasattr(final_message, 'content'):
        return
    
    content = final_message.content
    
    # Extract text content for TTS (excluding thinking blocks)
    text_content = ""
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get('type') == 'text':
                text_content += item.get('text', '')
            # thinking content is saved to history but not used for TTS
    else:
        text_content = str(content)
    
    # Load conversation history for message processing
    loaded_history = load_all_message_history(session_id)
    history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in loaded_history]
    
    # Extract keywords from metadata or parse from text
    extracted_keyword = None
    if execution_metadata and 'keyword' in execution_metadata:
        extracted_keyword = execution_metadata['keyword']
    else:
        # Fallback: parse emotional keywords from text content
        from backend.shared.utils.text_parser import parse_llm_output
        _, extracted_keyword = parse_llm_output(text_content)
    
    # Save complete content including thinking blocks to conversation history
    ai_msg_id, processed_content = process_assistant_text_message(
        content,  # Save complete content including thinking
        extracted_keyword,  # Use extracted keywords
        history_msgs,
        session_id
    )
    
    # Send message ID for client tracking
    yield f"data: {json.dumps({'message_id': ai_msg_id})}\n\n"
    
    # Send emotional keywords via WebSocket if available
    if extracted_keyword:
        from backend.presentation.websocket.status_notification_service import get_status_notification_service
        status_service = get_status_notification_service()
        if status_service:
            await status_service.notify_emotion_keyword(session_id, extracted_keyword, ai_msg_id)
    
    # Process TTS pipeline if text content is available
    if text_content.strip():
        # Get TTS engine from app state
        from backend.shared.utils.app_context import get_tts_engine
        tts_engine = get_tts_engine()

        # Dynamic import to avoid circular dependency
        from backend.presentation.streaming.tts_processor import process_tts_pipeline
        async for chunk in process_tts_pipeline(text_content, tts_engine):
            # Send TTS chunks only via WebSocket (no SSE for TTS)
            await send_tts_chunk_via_websocket(session_id, chunk)
    else:
        # Send empty text chunk for consistency when only keywords are present
        empty_chunk_data = {'text': '', 'audio': None, 'index': 0}
        empty_sse_chunk = f"data: {json.dumps(empty_chunk_data)}\n\n"
        await send_tts_chunk_via_websocket(session_id, empty_sse_chunk)


async def send_tts_chunk_via_websocket(session_id: str, sse_chunk: str):
    """
    Send TTS chunk data via WebSocket to frontend.

    Parses SSE formatted chunk and sends as structured WebSocket TTS_CHUNK message
    for frontend text-audio queue processing.

    Args:
        session_id: WebSocket session ID
        sse_chunk: SSE formatted chunk from TTS processor
    """
    try:
        # Get WebSocket connection manager
        from backend.presentation.websocket.connection import get_connection_manager
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

        # Create WebSocket TTS chunk message
        tts_message = create_message(
            MessageType.TTS_CHUNK,
            session_id=session_id,
            text=chunk_data.get('text', ''),
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