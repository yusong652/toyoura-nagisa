"""
Tool Notification Service.

Handles WebSocket notifications and related side-effects for tool results.
"""

from typing import Dict


class ToolNotificationService:
    """Sends tool result notifications and related updates."""

    def __init__(self, notification_session_id: str, send_tool_result_notifications: bool = True) -> None:
        self.notification_session_id = notification_session_id
        self.send_tool_result_notifications = send_tool_result_notifications

    async def notify_result(self, tool_call: Dict, result: Dict, agent_profile: str) -> None:
        """Send WebSocket notifications and related updates for a tool result."""
        if not self.send_tool_result_notifications:
            return

        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService

        tool_name = tool_call.get("name", "unknown")

        try:
            await WebSocketNotificationService.send_tool_result_update(
                session_id=self.notification_session_id,
                message_id=tool_call["id"],
                tool_call_id=tool_call["id"],
                tool_name=tool_name,
                tool_result=result,
            )
        except Exception as exc:
            print(f"[ToolNotificationService] Failed to send notification: {exc}")

        if tool_name == "todo_write":
            try:
                from backend.application.todo.service import get_todo_service

                todo_service = get_todo_service()
                current_todo = await todo_service.get_current_todo(agent_profile, self.notification_session_id)
                await WebSocketNotificationService.send_todo_update(self.notification_session_id, current_todo)
            except Exception as exc:
                print(f"[ToolNotificationService] Failed to send todo update: {exc}")

        if tool_name == "pfc_execute_task":
            if result.get("status") == "success":
                try:
                    from backend.application.notifications.pfc_task_notification_service import (
                        get_pfc_task_notification_service,
                    )

                    service = get_pfc_task_notification_service()
                    if service:
                        await service.start_polling(self.notification_session_id)
                except Exception as exc:
                    print(f"[ToolNotificationService] Failed to start PFC task polling: {exc}")
