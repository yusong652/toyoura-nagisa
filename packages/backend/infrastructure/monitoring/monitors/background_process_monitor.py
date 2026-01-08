"""
Background Process Monitor - Agent background process monitoring.

Tracks background processes spawned by the agent's bash tool
and generates status reminders.
"""

import logging
from typing import List
from .base_monitor import BaseMonitor

logger = logging.getLogger(__name__)


class BackgroundProcessMonitor(BaseMonitor):
    """
    Monitor for agent background processes.

    Queries the background process manager for running processes
    and generates system reminders.
    """

    async def get_reminders(self) -> List[str]:
        """
        Get reminders for background processes.

        Returns:
            List[str]: Background process reminder blocks (with system-reminder tags)
        """
        try:
            from backend.infrastructure.shell.background_process_manager import get_process_manager

            process_manager = get_process_manager()
            process_reminders = process_manager.get_system_reminders(self.session_id)

            # Wrap each reminder in system-reminder tags
            return [
                f"<system-reminder>\n{reminder}\n</system-reminder>"
                for reminder in process_reminders
            ]

        except Exception:
            # Process manager may not be available or no processes running
            return []
