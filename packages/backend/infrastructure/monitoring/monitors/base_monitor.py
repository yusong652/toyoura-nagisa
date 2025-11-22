"""
Base Monitor - Abstract base class for all specialized monitors.

Defines the common interface for monitoring different system components.
"""

from abc import ABC, abstractmethod
from typing import List


class BaseMonitor(ABC):
    """
    Abstract base class for specialized monitors.

    Each monitor is responsible for tracking a specific type of system state
    and generating system-reminder blocks for LLM context injection.
    """

    def __init__(self, session_id: str):
        """
        Initialize monitor for a session.

        Args:
            session_id: Session ID for scoped monitoring
        """
        self.session_id = session_id

    @abstractmethod
    async def get_reminders(self) -> List[str]:
        """
        Get system reminders for this monitor's domain.

        Returns:
            List[str]: System reminder blocks (wrapped in <system-reminder> tags)
        """
        pass
