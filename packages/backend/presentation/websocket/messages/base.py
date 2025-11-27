"""
Base WebSocket message schema.

This module defines the base message structure that all WebSocket messages inherit from.
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel

from backend.presentation.websocket.messages.types import MessageType


class BaseWebSocketMessage(BaseModel):
    """Base WebSocket message schema"""
    type: MessageType
    session_id: Optional[str] = None
    timestamp: str = datetime.now().isoformat()
    message_id: Optional[str] = None
