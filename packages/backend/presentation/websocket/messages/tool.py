"""
Tool execution and confirmation message schemas.

This module defines WebSocket messages for tool usage notifications,
user confirmation requests, and interrupt controls.
"""
from typing import Optional
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
        message_id: (inherited from base) ID of the message containing this tool call
        tool_call_id: Tool call ID (combined with message_id for matching)
        tool_name: Name of the tool requiring confirmation (bash, edit, write)
        command: Command/operation to be executed
        description: Optional human-readable description
        confirmation_type: Type of confirmation ('edit', 'exec', 'info')
        file_name: For edit type - name of the file being modified
        file_path: For edit type - full path to the file
        file_diff: For edit type - unified diff content showing changes
        original_content: For edit type - original file content (empty for new files)
        new_content: For edit type - new content to be written

    Note:
        message_id is inherited from BaseWebSocketMessage and should be provided
        when creating this message for proper tool call identification.
    """
    type: MessageType = MessageType.TOOL_CONFIRMATION_REQUEST
    # message_id is inherited from base class - should be provided for tool call identification
    tool_call_id: str  # Tool call ID (combined with message_id for matching)
    tool_name: str
    command: str
    description: Optional[str] = None
    # New fields for edit confirmation with diff display
    confirmation_type: Optional[str] = None  # 'edit', 'exec', 'info'
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    file_diff: Optional[str] = None
    original_content: Optional[str] = None
    new_content: Optional[str] = None


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
