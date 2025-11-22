"""
Queue Monitor - Queue message handling during tool recursion.

Monitors and formats queue messages sent by users during tool execution.
"""

import logging
from typing import List
from .base_monitor import BaseMonitor

logger = logging.getLogger(__name__)


class QueueMonitor(BaseMonitor):
    """
    Monitor for queue messages.

    Handles messages sent by users during tool recursion,
    converting them to system-reminder blocks.
    """

    def __init__(self, session_id: str):
        """
        Initialize queue monitor.

        Args:
            session_id: Session ID for scoped monitoring
        """
        super().__init__(session_id)
        # Flag to control whether queue checking is enabled
        self.check_queue: bool = False

    async def get_reminders(self) -> List[str]:
        """
        Get queue messages as reminder blocks.

        This method is called when generating tool results (inject_reminders=True).
        It extracts all waiting messages from the queue, merges them using the
        same strategy as external scenarios, and formats them as system-reminder blocks.

        Returns:
            List[str]: Formatted system-reminder blocks
        """
        if not self.check_queue:
            return []

        try:
            from backend.infrastructure.messaging.session_queue_manager import get_queue_manager

            queue_manager = get_queue_manager()

            # Drain queue and get all messages
            messages = await queue_manager.drain_queue_for_reminders(self.session_id)

            if not messages:
                return []

            # Use the same merge strategy as external scenarios
            merged_message = queue_manager._merge_messages(messages)
            merged_text = merged_message.get('message', '')

            # Format as reminder text
            reminder_text = (
                f"The user sent the following message:\n{merged_text}\n\n"
                "Please address this message and continue with your tasks."
            )

            # Wrap in system-reminder block
            reminder_block = f"<system-reminder>\n{reminder_text}\n</system-reminder>"

            logger.info(
                f"Converted {len(messages)} queue message(s) to 1 reminder block"
            )

            return [reminder_block]

        except Exception as e:
            logger.error(f"Failed to get queue message blocks: {e}")
            return []
