"""
User shell command message schemas.

This module defines WebSocket messages for user shell command execution
(CLI `!` prefix commands). Provides request/response patterns for shell
command execution via WebSocket instead of REST API.
"""
from typing import Optional
from backend.presentation.websocket.messages.base import BaseWebSocketMessage
from backend.presentation.websocket.messages.types import MessageType
from backend.domain.models.agent_types import AgentProfileLiteral, DEFAULT_AGENT_PROFILE


class UserShellExecuteMessage(BaseWebSocketMessage):
    """
    User shell command execution request.

    Sent by frontend when user executes a shell command with `!` prefix.
    Backend executes the command and returns result via USER_SHELL_RESULT.

    Attributes:
        command: Shell command to execute
        agent_profile: Agent profile for workspace resolution
        timeout_ms: Optional execution timeout in milliseconds
    """
    type: MessageType = MessageType.USER_SHELL_EXECUTE
    command: str
    agent_profile: AgentProfileLiteral = DEFAULT_AGENT_PROFILE
    timeout_ms: Optional[int] = None


class UserShellResultMessage(BaseWebSocketMessage):
    """
    User shell command execution result.

    Sent by backend after executing a user shell command. Contains
    command output, exit code, and updated working directory.

    Attributes:
        stdout: Standard output from command
        stderr: Standard error from command
        exit_code: Command exit code (0 = success)
        cwd: Current working directory after command execution
        context: LLM context string with caveat formatting
        success: Whether execution completed without infrastructure errors
        error_message: Error message if execution failed
        backgrounded: Whether command was moved to background via Ctrl+B
        process_id: Background process ID if backgrounded
    """
    type: MessageType = MessageType.USER_SHELL_RESULT
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    cwd: str = ""
    context: str = ""
    success: bool = True
    error_message: Optional[str] = None
    backgrounded: bool = False
    process_id: Optional[str] = None
