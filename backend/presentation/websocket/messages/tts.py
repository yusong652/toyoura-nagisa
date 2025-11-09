"""
Text-to-Speech (TTS) message schemas.

This module defines WebSocket messages for real-time audio streaming,
enabling TTS chunk delivery from backend to frontend.
"""
from typing import Optional
from backend.presentation.websocket.messages.base import BaseWebSocketMessage
from backend.presentation.websocket.messages.types import MessageType


class TTSChunk(BaseWebSocketMessage):
    """
    TTS chunk message schema for real-time audio streaming.

    Sent by backend to stream TTS audio chunks to frontend for progressive
    audio playback. Each chunk contains text, audio data, and processing
    metadata for monitoring and synchronization.

    Attributes:
        text: Text content being converted to speech
        audio: Base64 encoded audio data (WAV, MP3, etc.)
        index: Chunk sequence number for ordering
        processing_time: Time taken to generate this chunk (seconds)
        engine_status: Current TTS engine status
        error: Error message if TTS generation failed
        is_final: Whether this is the last chunk in the stream
    """
    type: MessageType = MessageType.TTS_CHUNK
    text: str
    audio: Optional[str] = None  # Base64 encoded audio data
    index: int
    processing_time: Optional[float] = None
    engine_status: Optional[str] = None
    error: Optional[str] = None
    is_final: bool = False
