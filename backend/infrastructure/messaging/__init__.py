"""
Message passing infrastructure for aiNagisa.

This module provides message queue management and processing capabilities
for handling concurrent user messages and ensuring sequential processing.
"""

from backend.infrastructure.messaging.session_queue_manager import (
    SessionQueueManager,
    get_queue_manager,
    set_queue_manager,
)

__all__ = [
    "SessionQueueManager",
    "get_queue_manager",
    "set_queue_manager",
]
