"""
Todo Monitor - Placeholder for todo monitoring.

Currently returns no reminders, as todos are managed entirely through
the TodoWrite tool. Completed todos remain visible in the current session
until auto-cleared when all todos are completed.

This monitor is kept for future extensibility (e.g., stale todo warnings).
"""

import logging
from typing import List
from .base_monitor import BaseMonitor

logger = logging.getLogger(__name__)


class TodoMonitor(BaseMonitor):
    """
    Monitor for todo items.

    Currently inactive - todos are managed via TodoWrite tool.
    Kept for future extensibility.
    """

    async def get_reminders(self) -> List[str]:
        """
        Get reminders for todo items.

        Currently returns empty list - todos are managed via TodoWrite tool.

        Returns:
            List[str]: Empty list (no reminders)
        """
        # No reminders - todos are fully managed by TodoWrite tool
        # Completed todos remain visible until auto-cleared
        return []
