"""
Session Mode Monitor - plan/build mode reminders.

Injects the current session mode into system reminders so the LLM
can respect plan/build behavior.
"""

from typing import List

from .base_monitor import BaseMonitor
from backend.infrastructure.storage.session_manager import get_session_mode


class SessionModeMonitor(BaseMonitor):
    """Monitor for session plan/build mode reminders."""

    async def get_reminders(self) -> List[str]:
        mode = get_session_mode(self.session_id)

        if mode == "plan":
            reminder_text = (
                "Your operational mode is PLAN.\n"
                "You are in read-only mode.\n"
                "File edits, shell commands, and execution tools are disabled."
            )
        else:
            reminder_text = (
                "Your operational mode is BUILD.\n"
                "You are not in read-only mode.\n"
                "File edits, shell commands, and tool execution are allowed."
            )

        reminder_block = f"<system-reminder>\n{reminder_text}\n</system-reminder>"
        return [reminder_block]
