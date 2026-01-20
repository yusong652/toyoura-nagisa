"""
WebSocket message type system for toyoura-nagisa.

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

# System messages
from backend.presentation.websocket.messages.system import (
    ErrorMessage,
    StatusUpdate,
    TitleUpdateMessage,
    SessionModeUpdateMessage,
)

# Message queue management
from backend.presentation.websocket.messages.queue import (
    QueueUpdateMessage,
    ProcessingStartMessage,
    MessageQueuedMessage
)

# Background process notifications
from backend.presentation.websocket.messages.background_process import BackgroundProcessNotification

# PFC task notifications
from backend.presentation.websocket.messages.pfc_task import PfcTaskNotification

# Tool execution and confirmation
from backend.presentation.websocket.messages.tool import (
    ToolConfirmationRequestMessage,
    ToolConfirmationResponseMessage,
    UserInterruptMessage,
    MoveToBackgroundMessage,
)

# Chat and streaming
from backend.presentation.websocket.messages.chat import (
    ChatMessageRequest,
    MessageCreateMessage,
    StreamingUpdateMessage
)

# User shell commands
from backend.presentation.websocket.messages.user_shell import (
    UserShellExecuteMessage,
    UserShellResultMessage,
)

# User PFC console commands
from backend.presentation.websocket.messages.user_pfc_console import (
    UserPfcConsoleExecuteMessage,
    UserPfcConsoleResultMessage,
)

# Factory functions and schemas (optional - can be imported from .factory directly)
from backend.presentation.websocket.messages.factory import (
    INCOMING_MESSAGE_SCHEMAS,
    OUTGOING_MESSAGE_SCHEMAS,
    create_message,
    parse_incoming_websocket_message,
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
    # System messages
    "ErrorMessage",
    "StatusUpdate",
    "TitleUpdateMessage",
    "SessionModeUpdateMessage",
    # Message queue management
    "QueueUpdateMessage",
    "ProcessingStartMessage",
    "MessageQueuedMessage",
    # Background process notifications
    "BackgroundProcessNotification",
    # PFC task notifications
    "PfcTaskNotification",
    # Tool execution and confirmation
    "ToolConfirmationRequestMessage",
    "ToolConfirmationResponseMessage",
    "UserInterruptMessage",
    "MoveToBackgroundMessage",
    # Chat and streaming
    "ChatMessageRequest",
    "MessageCreateMessage",
    "StreamingUpdateMessage",
    # User shell commands
    "UserShellExecuteMessage",
    "UserShellResultMessage",
    # User PFC console commands
    "UserPfcConsoleExecuteMessage",
    "UserPfcConsoleResultMessage",
    # Factory functions and schemas
    "INCOMING_MESSAGE_SCHEMAS",
    "OUTGOING_MESSAGE_SCHEMAS",
    "create_message",
    "parse_incoming_websocket_message",
]
