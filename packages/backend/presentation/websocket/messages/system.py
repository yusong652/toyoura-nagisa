"""
System message schemas.

This module defines WebSocket messages for system-level notifications,
errors, status updates, and session management.
"""
from typing import Optional, Dict, Any
from backend.presentation.websocket.messages.base import BaseWebSocketMessage
from backend.presentation.websocket.messages.types import MessageType


class ErrorMessage(BaseWebSocketMessage):
    """
    Error message schema for communicating errors to frontend.

    Sent by backend when errors occur during message processing, tool execution,
    or any other operation. Provides structured error information for frontend
    error handling and user notification.

    Attributes:
        error_code: Error code for categorization (e.g., "MESSAGE_PARSE_ERROR")
        error_message: Human-readable error description
        details: Additional error context and debugging information
    """
    type: MessageType = MessageType.ERROR
    error_code: str
    error_message: str
    details: Optional[Dict[str, Any]] = None


class StatusUpdate(BaseWebSocketMessage):
    """
    Status update message schema for system state notifications.

    Sent by backend to inform frontend about system status changes,
    processing states, or other operational updates.

    Attributes:
        status: Status indicator (e.g., "processing", "ready", "busy")
        data: Additional status-related data and context
    """
    type: MessageType = MessageType.STATUS_UPDATE
    status: str
    data: Optional[Dict[str, Any]] = None


class TitleUpdateMessage(BaseWebSocketMessage):
    """
    Title update message schema for session title changes.

    Sent by backend when a chat session's title is automatically generated
    or manually updated. Used to sync session titles with frontend display.

    Attributes:
        payload: Update payload containing session_id and new title
    """
    type: MessageType = MessageType.TITLE_UPDATE
    payload: Dict[str, Any]  # Contains session_id and title


class SessionModeUpdateMessage(BaseWebSocketMessage):
    """
    Session mode update message schema for plan/build changes.

    Attributes:
        payload: Update payload containing session_id and mode
    """
    type: MessageType = MessageType.SESSION_MODE_UPDATE
    payload: Dict[str, Any]  # Contains session_id and mode


class SessionLlmConfigUpdateMessage(BaseWebSocketMessage):
    """
    Session LLM config update message schema.

    Attributes:
        payload: Update payload containing session_id and llm_config
    """
    type: MessageType = MessageType.SESSION_LLM_CONFIG_UPDATE
    payload: Dict[str, Any]  # Contains session_id and llm_config
