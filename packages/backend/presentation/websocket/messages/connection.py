"""
Connection management message schemas.

This module defines WebSocket messages for connection lifecycle and health monitoring.
"""
from backend.presentation.websocket.messages.base import BaseWebSocketMessage
from backend.presentation.websocket.messages.types import MessageType


class HeartbeatMessage(BaseWebSocketMessage):
    """
    Heartbeat message schema for connection health monitoring.

    Sent periodically by backend to verify WebSocket connection is alive.
    Frontend responds with HEARTBEAT_ACK to maintain connection.
    """
    type: MessageType = MessageType.HEARTBEAT
