"""
Bash Monitor - Background bash process monitoring.

Tracks background bash processes and generates status reminders.
"""

import logging
from typing import List
from .base_monitor import BaseMonitor

logger = logging.getLogger(__name__)


class BashMonitor(BaseMonitor):
    """
    Monitor for bash background processes.

    Queries the background process manager for running processes
    and generates system reminders.
    """

    async def get_reminders(self) -> List[str]:
        """
        Get reminders for bash background processes.

        Returns:
            List[str]: Bash process reminder blocks (with system-reminder tags)
        """
        try:
            from backend.infrastructure.mcp.tools.coding.utils.background_process_manager import get_process_manager

            process_manager = get_process_manager()
            bash_reminders = process_manager.get_system_reminders(self.session_id)

            # Wrap each reminder in system-reminder tags
            return [
                f"<system-reminder>\n{reminder}\n</system-reminder>"
                for reminder in bash_reminders
            ]

        except Exception:
            # Process manager may not be available or no processes running
            return []
