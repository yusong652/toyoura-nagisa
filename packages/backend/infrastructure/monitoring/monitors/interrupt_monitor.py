"""
Interrupt Monitor - User interrupt status tracking.

Manages user interrupt state (ESC key) for both immediate detection
and persistent cross-turn notification.
"""

import logging
from typing import List
from .base_monitor import BaseMonitor

logger = logging.getLogger(__name__)


class InterruptMonitor(BaseMonitor):
    """
    Monitor for user interrupt status.

    Tracks when users interrupt responses (ESC key) and manages
    notification state across conversation turns.
    """

    def __init__(self, session_id: str):
        """
        Initialize interrupt monitor.

        Loads interrupt state from runtime_state storage on initialization.

        Args:
            session_id: Session ID for scoped monitoring
        """
        super().__init__(session_id)

        # Immediate interrupt flag (in-memory only)
        self.user_interrupted: bool = False

        # Persistent interrupt flag (loaded from storage)
        self._last_response_interrupted: bool = False
        self._load_interrupt_state()

    def _load_interrupt_state(self) -> None:
        """
        Load interrupt state from runtime_state storage.

        Called during initialization to restore interrupt flag from persistent storage.
        """
        try:
            from backend.infrastructure.storage.session_manager import load_runtime_state

            runtime_state = load_runtime_state(self.session_id)
            self._last_response_interrupted = runtime_state.get("last_response_interrupted", False)

            if self._last_response_interrupted:
                logger.info(f"Loaded interrupt state for session {self.session_id[:8]}: interrupted=True")

        except Exception as e:
            logger.warning(f"Failed to load interrupt state: {e}")
            self._last_response_interrupted = False

    def was_last_response_interrupted(self) -> bool:
        """
        Check if the last response was interrupted by the user.

        Returns:
            bool: True if last response was interrupted
        """
        return self._last_response_interrupted

    def set_user_interrupted(self) -> None:
        """
        Set the immediate user interrupt flag.

        Called by UserInterruptHandler when user presses ESC.
        """
        self.user_interrupted = True
        logger.info(f"Set user_interrupted flag for session {self.session_id[:8]}")

    def reset_user_interrupted(self) -> None:
        """
        Reset the immediate user interrupt flag.

        Called at the start of each new conversation turn.
        """
        self.user_interrupted = False

    def is_user_interrupted(self) -> bool:
        """
        Check if user has interrupted the current streaming response.

        Returns:
            bool: True if user pressed ESC to interrupt current response
        """
        return self.user_interrupted

    def set_interrupt_flag(self) -> None:
        """
        Set the persistent interrupt flag in both memory and storage.

        Called by Agent after handling an interrupted response.
        """
        try:
            self._last_response_interrupted = True

            from backend.infrastructure.storage.session_manager import update_runtime_state
            update_runtime_state(self.session_id, "last_response_interrupted", True)

            logger.info(f"Set last_response_interrupted flag for session {self.session_id[:8]}")

        except Exception as e:
            logger.warning(f"Failed to set interrupt flag: {e}")
            self._last_response_interrupted = True

    def clear_interrupt_flag(self) -> None:
        """
        Clear the interrupt flag in both memory and persistent storage.

        Called by ContextManager after handling interrupted response merge.
        """
        try:
            self._last_response_interrupted = False

            from backend.infrastructure.storage.session_manager import update_runtime_state
            update_runtime_state(self.session_id, "last_response_interrupted", False)

            logger.debug(f"Cleared interrupt flag for session {self.session_id[:8]}")

        except Exception as e:
            logger.warning(f"Failed to clear interrupt flag: {e}")
            self._last_response_interrupted = False

    async def get_reminders(self) -> List[str]:
        """
        Get reminder for user interrupt status.

        Checks if the last response was interrupted. If so, generates a reminder
        and clears the interrupt flag.

        Returns:
            List[str]: Interrupt reminder block if flag is set, empty list otherwise
        """
        if not self._last_response_interrupted:
            return []

        try:
            # Clear interrupt flag in memory
            self._last_response_interrupted = False

            # Clear interrupt flag in persistent storage
            from backend.infrastructure.storage.session_manager import update_runtime_state
            update_runtime_state(self.session_id, "last_response_interrupted", False)

            # Generate reminder
            reminder_text = "Previous response interrupted by user."
            reminder_block = f"<system-reminder>\n{reminder_text}\n</system-reminder>"

            logger.info(f"Generated interrupt reminder for session {self.session_id[:8]}")

            return [reminder_block]

        except Exception as e:
            logger.error(f"Failed to generate interrupt reminder: {e}")
            # Still clear memory flag to avoid infinite loop
            self._last_response_interrupted = False
            return []
