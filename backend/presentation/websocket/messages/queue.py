"""
Message queue management message schemas.

This module defines WebSocket messages for session-based message queue status,
enabling frontend to track message processing state and queue position.
"""
from typing import Dict, Any
from backend.presentation.websocket.messages.base import BaseWebSocketMessage
from backend.presentation.websocket.messages.types import MessageType


class QueueUpdateMessage(BaseWebSocketMessage):
    """
    Queue update message for notifying frontend about message queue status.

    Provides real-time updates about the session's message queue, including
    number of pending messages and processing state. Sent when queue state
    changes (messages added, processing started/completed).

    Attributes:
        payload: Queue status information
            - queue_size: Number of messages waiting in queue
            - is_processing: Whether session is currently processing
            - timestamp: Update timestamp
    """
    type: MessageType = MessageType.QUEUE_UPDATE
    payload: Dict[str, Any]


class ProcessingStartMessage(BaseWebSocketMessage):
    """
    Processing start message for notifying frontend when message processing begins.

    Sent when a message is taken from the queue and processing starts,
    allowing frontend to show "processing" status and update UI accordingly.

    Attributes:
        payload: Processing information
            - remaining_in_queue: Number of messages still waiting
            - timestamp: Processing start timestamp
    """
    type: MessageType = MessageType.PROCESSING_START
    payload: Dict[str, Any]


class MessageQueuedMessage(BaseWebSocketMessage):
    """
    Message queued notification for frontend confirmation.

    Sent immediately after a user message is successfully added to the queue,
    providing feedback that the message was received and will be processed.
    This ensures users know their message was accepted even if processing
    is delayed due to queue backlog.

    Attributes:
        payload: Queue information
            - position: Position in queue (0 = processing now, 1+ = waiting)
            - queue_size: Total queue size
            - timestamp: Queued timestamp
    """
    type: MessageType = MessageType.MESSAGE_QUEUED
    payload: Dict[str, Any]
