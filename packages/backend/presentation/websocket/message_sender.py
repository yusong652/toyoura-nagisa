"""
WebSocket message sender for outgoing messages to frontend.

This module provides utilities for sending WebSocket messages from backend to frontend,
including message creation notifications and TTS chunk delivery.

Responsibilities:
- Format and send MESSAGE_CREATE events
- Format and send TTS_CHUNK events
- Handle WebSocket connection state checks
- Provide error handling for message sending failures
"""

import json
import logging
from typing import Optional

from backend.infrastructure.websocket.connection_manager import get_connection_manager
from backend.presentation.websocket.message_types import MessageType, create_message

logger = logging.getLogger(__name__)


async def send_message_create(
    session_id: str,
    message_id: str
) -> None:
    """
    Send MESSAGE_CREATE event via WebSocket to create a new bot message.

    Notifies frontend to create a new bot message with the specified ID
    before TTS chunks are processed.

    Args:
        session_id: WebSocket session ID
        message_id: ID for the new message to create

    Returns:
        None: Silently fails if WebSocket is unavailable
    """
    try:
        connection_manager = get_connection_manager()

        if not connection_manager or not connection_manager.is_connected_sync(session_id):
            logger.debug(f"No WebSocket connection for session {session_id}, skipping MESSAGE_CREATE")
            return

        # Create MESSAGE_CREATE message
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
        logger.warning(f"Failed to send MESSAGE_CREATE via WebSocket to session {session_id}: {e}")


async def send_tts_chunk(
    session_id: str,
    sse_chunk: str,
    message_id: Optional[str] = None,
    is_streaming: bool = False
) -> None:
    """
    Send TTS chunk data via WebSocket to frontend.

    Parses SSE formatted chunk and sends as structured WebSocket TTS_CHUNK message
    for frontend text-audio queue processing.

    Args:
        session_id: WebSocket session ID
        sse_chunk: SSE formatted chunk from TTS processor
        message_id: Optional message ID for association
        is_streaming: If True, only send audio (text already displayed via streaming)

    Returns:
        None: Silently fails if WebSocket is unavailable or parsing fails
    """
    try:
        connection_manager = get_connection_manager()

        if not connection_manager or not connection_manager.is_connected_sync(session_id):
            logger.debug(f"No WebSocket connection for session {session_id}, skipping TTS chunk")
            return

        # Parse SSE chunk data
        if not sse_chunk.startswith('data: '):
            logger.debug(f"Invalid SSE chunk format, skipping")
            return

        json_str = sse_chunk.replace('data: ', '').strip()
        if not json_str or json_str == '\n\n':
            logger.debug(f"Empty SSE chunk, skipping")
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

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse TTS chunk JSON for session {session_id}: {e}")
    except Exception as e:
        # Don't break the main flow if WebSocket sending fails
        logger.warning(f"Failed to send TTS chunk via WebSocket to session {session_id}: {e}")
