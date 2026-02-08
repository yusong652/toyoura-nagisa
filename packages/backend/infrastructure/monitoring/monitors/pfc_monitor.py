"""
PFC Monitor - PFC simulation task tracking.

Monitors PFC simulation tasks via local PfcTaskManager.
No direct PFC server communication needed.
"""

import logging
from typing import List
from .base_monitor import BaseMonitor

logger = logging.getLogger(__name__)


class PfcMonitor(BaseMonitor):
    """
    Monitor for PFC simulation tasks.

    Uses local PfcTaskManager for task state, avoiding
    direct WebSocket communication with pfc-bridge.
    """

    async def get_reminders(self, agent_profile = "pfc_expert") -> List[str]:
        """
        Get reminders for PFC simulation tasks.

        Only queries if agent_profile starts with 'pfc'.

        Args:
            agent_profile: Agent profile type.

        Returns:
            List[str]: PFC task reminders
        """
        if not agent_profile.startswith("pfc"):
            return []

        try:
            from backend.infrastructure.pfc.task_manager import get_pfc_task_manager

            task_manager = get_pfc_task_manager()
            reminders = task_manager.get_system_reminders(self.session_id)

            if not reminders:
                return []

            wrapped = [
                f"<system-reminder>\n{reminder}\n</system-reminder>"
                for reminder in reminders
            ]

            wrapped.append(
                "<system-reminder>\n"
                "You can check detailed output using pfc_check_task_status tool.\n"
                "</system-reminder>"
            )

            return wrapped

        except Exception as e:
            logger.debug(f"Failed to get PFC reminders: {e}")
            return []
