"""
Background process notification message schemas.

This module defines WebSocket messages for real-time background process monitoring,
enabling frontend to display bash command execution status and output.
"""
from typing import Optional, List
from backend.presentation.websocket.messages.base import BaseWebSocketMessage
from backend.presentation.websocket.messages.types import MessageType


class BackgroundProcessNotification(BaseWebSocketMessage):
    """
    Background process notification message schema for frontend display.

    Provides real-time updates about background bash processes with recent output
    for user monitoring. Designed to show command name and last 5 lines of output
    in a compact UI panel.

    Used with different message types:
    - BACKGROUND_PROCESS_STARTED: Process launched
    - BACKGROUND_PROCESS_OUTPUT_UPDATE: New output available
    - BACKGROUND_PROCESS_COMPLETED: Process finished successfully
    - BACKGROUND_PROCESS_KILLED: Process terminated

    Attributes:
        type: Notification type (STARTED/OUTPUT_UPDATE/COMPLETED/KILLED)
        process_id: Unique process identifier for tracking
        command: Shell command being executed
        description: Optional human-readable command description
        status: Process status ("running", "completed", "killed")
        recent_output: Last 5 lines of output for display
        has_more_output: Whether more output is available beyond recent_output
        runtime_seconds: Process runtime in seconds
        exit_code: Process exit code when completed/killed (None if still running)
    """
    type: MessageType
    process_id: str
    command: str
    description: Optional[str] = None
    status: str  # "running", "completed", "killed"

    # Recent output for display (last 5 lines)
    recent_output: List[str] = []
    has_more_output: bool = False

    # Statistics
    runtime_seconds: float = 0
    exit_code: Optional[int] = None
