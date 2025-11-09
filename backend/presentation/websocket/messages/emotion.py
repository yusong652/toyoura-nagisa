"""
Emotion and animation message schemas.

This module defines WebSocket messages for Live2D character animation control
through emotion keyword triggers.
"""
from typing import Optional
from backend.presentation.websocket.messages.base import BaseWebSocketMessage
from backend.presentation.websocket.messages.types import MessageType


class EmotionKeywordMessage(BaseWebSocketMessage):
    """
    Emotion keyword message schema for Live2D animation triggers.

    Sent by backend to trigger specific Live2D character animations based on
    emotion keywords detected in the conversation. These keywords are extracted
    from AI responses and used to control character expressions and animations.

    Attributes:
        keyword: Emotion keyword to trigger animation (e.g., "happy", "sad", "surprised")
        message_id: Associated message ID for context tracking
    """
    type: MessageType = MessageType.EMOTION_KEYWORD
    keyword: str
    message_id: Optional[str] = None
