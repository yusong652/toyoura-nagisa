"""
Tool execution and confirmation message schemas.

This module defines WebSocket messages for tool usage notifications,
user confirmation requests, and interrupt controls.
"""
from typing import Optional, Dict, Any, List
from backend.presentation.websocket.messages.base import BaseWebSocketMessage
from backend.presentation.websocket.messages.types import MessageType


class ToolConfirmationRequestMessage(BaseWebSocketMessage):
    """
    Tool confirmation request message schema (for bash, edit, write, etc.).

    Sent by backend to request user confirmation before executing
    potentially sensitive operations like bash commands, file edits, or writes.
    Frontend should display confirmation UI and respond with
    ToolConfirmationResponseMessage.

    Attributes:
        tool_call_id: Unique ID to match request with response
        tool_name: Name of the tool requiring confirmation (bash, edit, write)
        command: Command/operation to be executed
        description: Optional human-readable description
    """
    type: MessageType = MessageType.TOOL_CONFIRMATION_REQUEST
    tool_call_id: str  # ID of the tool call to match with frontend ToolUseBlock
    tool_name: str
    command: str
    description: Optional[str] = None


class ToolConfirmationResponseMessage(BaseWebSocketMessage):
    """
    Tool confirmation response message schema.

    Sent by frontend in response to ToolConfirmationRequestMessage
    to approve or reject tool execution.

    Attributes:
        tool_call_id: ID matching the original request
        approved: Whether user approved the tool execution
        user_message: Optional message from user (e.g., modifications, cancellation reason)
    """
    type: MessageType = MessageType.TOOL_CONFIRMATION_RESPONSE
    tool_call_id: str  # ID of the tool call to match the request
    approved: bool
    user_message: Optional[str] = None


class UserInterruptMessage(BaseWebSocketMessage):
    """
    User interrupt message schema (ESC key pressed).

    Sent by frontend when user presses ESC to interrupt ongoing
    LLM reasoning or tool execution. Backend should gracefully
    stop the current operation.
    """
    type: MessageType = MessageType.USER_INTERRUPT
