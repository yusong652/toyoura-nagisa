"""
WebSocket message type system for aiNagisa.

This package provides a modular structure for WebSocket message definitions,
organized by functional domain for better maintainability.

Architecture Overview:
- Frontend sends JSON strings via WebSocket: ws.send(JSON.stringify(message))
- Backend receives as event.data (string) or pre-parsed dict (framework-dependent)
- parse_incoming_websocket_message() handles both formats
- Only specific message types are accepted from frontend (INCOMING_MESSAGE_SCHEMAS)
- Backend-to-frontend messages use create_message() for consistent formatting
"""

# Core types and base classes
from backend.presentation.websocket.messages.types import MessageType
from backend.presentation.websocket.messages.base import BaseWebSocketMessage

# Connection management
from backend.presentation.websocket.messages.connection import HeartbeatMessage

# Location services
from backend.presentation.websocket.messages.location import (
    LocationRequestMessage,
    LocationResponseMessage
)

# Emotion and animation
from backend.presentation.websocket.messages.emotion import EmotionKeywordMessage

# Text-to-Speech
from backend.presentation.websocket.messages.tts import TTSChunk

# System messages
from backend.presentation.websocket.messages.system import (
    ErrorMessage,
    StatusUpdate,
    TitleUpdateMessage
)

# Message queue management
from backend.presentation.websocket.messages.queue import (
    QueueUpdateMessage,
    ProcessingStartMessage,
    MessageQueuedMessage
)

# Background process notifications
from backend.presentation.websocket.messages.background_process import BackgroundProcessNotification

# Tool execution and confirmation
from backend.presentation.websocket.messages.tool import (
    ToolUseNotification,
    ToolConfirmationRequestMessage,
    ToolConfirmationResponseMessage,
    UserInterruptMessage
)

# Chat and streaming
from backend.presentation.websocket.messages.chat import (
    ChatMessageRequest,
    ChatStreamChunk,
    MessageCreateMessage,
    StreamingChunkMessage,
    StreamingUpdateMessage
)

# Factory functions and schemas (optional - can be imported from .factory directly)
from backend.presentation.websocket.messages.factory import (
    INCOMING_MESSAGE_SCHEMAS,
    OUTGOING_MESSAGE_SCHEMAS,
    create_message,
    parse_incoming_websocket_message,
    create_error_message,
    create_tool_confirmation_request,
    create_background_process_notification,
)

__all__ = [
    # Core types
    "MessageType",
    "BaseWebSocketMessage",
    # Connection management
    "HeartbeatMessage",
    # Location services
    "LocationRequestMessage",
    "LocationResponseMessage",
    # Emotion and animation
    "EmotionKeywordMessage",
    # Text-to-Speech
    "TTSChunk",
    # System messages
    "ErrorMessage",
    "StatusUpdate",
    "TitleUpdateMessage",
    # Message queue management
    "QueueUpdateMessage",
    "ProcessingStartMessage",
    "MessageQueuedMessage",
    # Background process notifications
    "BackgroundProcessNotification",
    # Tool execution and confirmation
    "ToolUseNotification",
    "ToolConfirmationRequestMessage",
    "ToolConfirmationResponseMessage",
    "UserInterruptMessage",
    # Chat and streaming
    "ChatMessageRequest",
    "ChatStreamChunk",
    "MessageCreateMessage",
    "StreamingChunkMessage",
    "StreamingUpdateMessage",
    # Factory functions and schemas
    "INCOMING_MESSAGE_SCHEMAS",
    "OUTGOING_MESSAGE_SCHEMAS",
    "create_message",
    "parse_incoming_websocket_message",
    "create_error_message",
    "create_tool_confirmation_request",
    "create_background_process_notification",
]
