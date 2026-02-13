"""
User PFC console command message schemas.

This module defines WebSocket messages for user PFC Python console command
execution (CLI `>` prefix commands). Provides request/response patterns for
PFC Python code execution via WebSocket instead of REST API.

Supports Ctrl+B backgrounding similar to user shell commands.
"""
from typing import Optional, Any
from backend.presentation.websocket.messages.base import BaseWebSocketMessage
from backend.presentation.websocket.messages.types import MessageType
from backend.domain.models.agent_types import AgentProfileLiteral, DEFAULT_AGENT_PROFILE


class UserPfcConsoleExecuteMessage(BaseWebSocketMessage):
    """
    User PFC console command execution request.

    Sent by frontend when user executes a PFC Python command with `>` prefix.
    Backend executes the code via PFC server and returns result via
    USER_PFC_CONSOLE_RESULT.

    Attributes:
        code: Python code to execute in PFC environment
        agent_profile: Agent profile for workspace resolution
        timeout_ms: Optional execution timeout in milliseconds
    """
    type: MessageType = MessageType.USER_PFC_CONSOLE_EXECUTE
    code: str
    agent_profile: AgentProfileLiteral = DEFAULT_AGENT_PROFILE
    timeout_ms: Optional[int] = None


class UserPfcConsoleResultMessage(BaseWebSocketMessage):
    """
    User PFC console command execution result.

    Sent by backend after executing a user PFC Python command. Contains
    execution output, error details, and task information.

    Attributes:
        task_id: Task identifier for tracking
        script_name: Generated script file name
        script_path: Full path to generated script file
        code_preview: Preview of executed code
        output: Standard output from execution
        error: Error traceback if execution failed
        result: Script execution result value
        elapsed_time: Execution time in seconds
        context: LLM context string for injection
        connected: Whether PFC server is connected
        success: Whether execution completed without infrastructure errors
        error_message: Error message if execution failed
        backgrounded: Whether command was moved to background via Ctrl+B
    """
    type: MessageType = MessageType.USER_PFC_CONSOLE_RESULT
    task_id: Optional[str] = None
    script_name: Optional[str] = None
    script_path: Optional[str] = None
    code_preview: Optional[str] = None
    output: str = ""
    error: Optional[str] = None
    result: Optional[Any] = None
    elapsed_time: Optional[float] = None
    context: str = ""
    connected: bool = True
    success: bool = True
    error_message: Optional[str] = None
    backgrounded: bool = False
