"""
WebSocket message type definitions and schemas.

DEPRECATED: This module is deprecated. Please import from the modular structure:
- backend.presentation.websocket.messages for message classes
- backend.presentation.websocket.messages.factory for factory functions

This compatibility module re-exports everything from the new structure
to maintain backward compatibility with existing code.

Architecture Overview:
- Frontend sends JSON strings via WebSocket: ws.send(JSON.stringify(message))
- Backend receives as event.data (string) or pre-parsed dict (framework-dependent)
- parse_incoming_websocket_message() handles both formats
- Only specific message types are accepted from frontend (INCOMING_MESSAGE_SCHEMAS)
- Backend-to-frontend messages use create_message() for consistent formatting
"""

# Re-export all message types and classes
from backend.presentation.websocket.messages import (
    MessageType,
    BaseWebSocketMessage,
    # Connection management
    HeartbeatMessage,
    # Location services
    LocationRequestMessage,
    LocationResponseMessage,
    # Emotion and animation
    EmotionKeywordMessage,
    # Text-to-Speech
    TTSChunk,
    # System messages
    ErrorMessage,
    StatusUpdate,
    TitleUpdateMessage,
    # Message queue management
    QueueUpdateMessage,
    ProcessingStartMessage,
    MessageQueuedMessage,
    # Background process notifications
    BackgroundProcessNotification,
    # Tool execution and confirmation
    ToolUseNotification,
    ToolConfirmationRequestMessage,
    ToolConfirmationResponseMessage,
    UserInterruptMessage,
    # Chat and streaming
    ChatMessageRequest,
    MessageCreateMessage,
    StreamingUpdateMessage,
)

# Re-export factory functions and schemas
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
    "MessageCreateMessage",
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
