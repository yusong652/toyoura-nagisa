"""
Tool Result Persistence.

Handles database persistence for tool results.
"""

from typing import Dict, Sequence

from backend.application.session.message_service import MessageService


class ToolResultPersistence:
    """Persists tool results to the database."""

    def __init__(self, session_id: str, message_service: MessageService | None = None) -> None:
        self.session_id = session_id
        self.message_service = message_service or MessageService()

    async def save_results(self, tool_calls: Sequence[Dict], results: Sequence[Dict]) -> None:
        """Save tool results to database in original order."""
        for tool_call, result in zip(tool_calls, results, strict=False):
            try:
                self.message_service.save_tool_result_message(
                    tool_call_id=tool_call["id"],
                    tool_name=tool_call["name"],
                    tool_result=result,
                    session_id=self.session_id,
                )
            except Exception as exc:
                print(f"[ToolResultPersistence] Failed to save result: {exc}")
