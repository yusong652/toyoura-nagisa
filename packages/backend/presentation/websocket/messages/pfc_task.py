"""
PFC task notification message schemas.

This module defines WebSocket messages for real-time PFC task monitoring,
enabling frontend to display simulation execution status and output.
"""
from typing import Optional, List
from backend.presentation.websocket.messages.base import BaseWebSocketMessage
from backend.presentation.websocket.messages.types import MessageType


class PfcTaskNotification(BaseWebSocketMessage):
    """
    PFC task notification message schema for frontend display.

    Provides real-time updates about the current PFC background task with
    recent output for user monitoring.

    Note: PFC only supports single-task execution, so this represents
    the one active task at a time.

    Attributes:
        type: Message type (PFC_TASK_UPDATE)
        task_id: Unique task identifier (8-char hex)
        session_id: Session that owns this task
        script_name: Name of the script file (e.g., "main.py")
        entry_script: Absolute path to entry script
        description: Human-readable task description from agent
        status: Task status ("running", "completed", "failed", "interrupted")
        source: Task source ("agent" or "user_console")
        git_commit: Git commit hash for version tracking (agent tasks only)
        start_time: Task start timestamp (Unix epoch)
        elapsed_time: Task elapsed time in seconds
        recent_output: Last N lines of output for display
        has_more_output: Whether more output is available
        error: Error message if task failed
    """
    type: MessageType = MessageType.PFC_TASK_UPDATE
    task_id: str
    session_id: str
    script_name: str
    entry_script: str = ""
    description: str = ""
    status: str  # "running", "completed", "failed", "interrupted"
    source: str = "agent"
    git_commit: Optional[str] = None

    # Timing
    start_time: Optional[float] = None
    elapsed_time: float = 0

    # Output for display
    recent_output: List[str] = []
    has_more_output: bool = False

    # Error info
    error: Optional[str] = None
