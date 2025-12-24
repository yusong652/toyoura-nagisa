"""
PFC Monitor - PFC simulation task tracking.

Monitors PFC simulation tasks with intelligent notification tracking.
"""

import asyncio
import logging
from typing import List
from .base_monitor import BaseMonitor

logger = logging.getLogger(__name__)


class PfcMonitor(BaseMonitor):
    """
    Monitor for PFC simulation tasks.

    Implements persistent notification tracking:
    1. Unnotified completed/failed tasks → One-time completion notification + mark as notified
    2. Running tasks → Continuous status reminders
    3. Already notified completed/failed tasks → Excluded (no reminder)

    Note: This monitor requires agent_profile for profile-based filtering.
    """

    async def get_reminders(self, agent_profile: str = "general") -> List[str]:
        """
        Get reminders for PFC simulation tasks.

        Only queries PFC if agent_profile is 'pfc', to avoid unnecessary
        connection attempts for other profiles.

        Args:
            agent_profile: Agent profile type. Only 'pfc' profile will query PFC server.

        Returns:
            List[str]: PFC task reminders (completion alerts + running task status)
        """
        # Skip PFC query if not in PFC profile
        if agent_profile != 'pfc':
            return []

        try:
            from backend.infrastructure.pfc import get_pfc_client
            from backend.infrastructure.mcp.utils.time_utils import format_time_range

            # Get WebSocket client (auto-connects if needed)
            client = await get_pfc_client()

            # Query recent tasks (all sessions, limit=3)
            result = await client.list_tasks(
                session_id=None,  # No filter - see all tasks
                offset=0,
                limit=3
            )

            if result.get("status") != "success":
                return []

            tasks = result.get("data", [])
            if not tasks:
                return []

            wrapped_reminders = []
            completion_notifications = []
            tasks_to_mark = []  # Track tasks that need to be marked as notified

            # Step 1: Separate tasks by status and notification state
            for task in tasks:
                task_id = task.get("task_id", "unknown")
                status = task.get("status", "unknown")
                notified = task.get("notified", False)
                description = task.get("description", "No description")
                script_path = task.get("script_path", task.get("name", "unknown"))
                start_time = task.get("start_time")
                end_time = task.get("end_time")
                task_session_id = task.get("session_id", "unknown")

                # Format time range
                time_info = format_time_range(start_time, end_time)

                # Build session marker
                task_session_display = task_session_id[:8] if task_session_id != "unknown" else "unknown"
                if task_session_id == self.session_id:
                    session_marker = " (your task)"
                else:
                    session_marker = f" (session: {task_session_display})"

                # Handle completed/failed/interrupted tasks
                if status in ["completed", "failed", "interrupted"]:
                    if not notified:
                        # Generate one-time completion notification
                        notification = (
                            f"PFC Task {task_id}{session_marker} {status}: "
                            f"{script_path}, {time_info} - {description}. "
                            f"Use pfc_check_task_status('{task_id}') to see results."
                        )
                        completion_notifications.append(notification)
                        tasks_to_mark.append(task_id)
                    # else: already notified, skip (no reminder)

                # Handle running tasks
                elif status == "running":
                    reminder = (
                        f"PFC Task {task_id}{session_marker}: "
                        f"status=running, script={script_path}, {time_info}. "
                        f"Description: {description}"
                    )
                    wrapped_reminders.append(f"<system-reminder>\n{reminder}\n</system-reminder>")

            # Step 2: Wrap completion notifications and add them first (higher priority)
            if completion_notifications:
                wrapped_reminders = [
                    f"<system-reminder>\n{notification}\n</system-reminder>"
                    for notification in completion_notifications
                ] + wrapped_reminders

            # Step 3: Mark tasks as notified in PFC server (async, fire-and-forget)
            for task_id in tasks_to_mark:
                try:
                    asyncio.create_task(client.mark_task_notified(task_id))
                except Exception as e:
                    logger.warning(f"Failed to mark task {task_id} as notified: {e}")

            # Add tool usage hint once at the end (not repeated for each task)
            if wrapped_reminders:
                tool_hint = "<system-reminder>\nYou can check detailed output using pfc_check_task_status tool.\n</system-reminder>"
                wrapped_reminders.append(tool_hint)

            return wrapped_reminders

        except Exception as e:
            # PFC server may not be available or not running
            logger.debug(f"Failed to get PFC reminders: {e}")
            return []
