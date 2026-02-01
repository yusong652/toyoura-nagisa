"""
Gemini CLI context manager.

Ensures tool call/response turns follow Code Assist requirements.
"""

from typing import Any, Dict

from backend.infrastructure.llm.providers.google.context_manager import GoogleContextManager
from backend.infrastructure.llm.providers.google_gemini_cli.message_formatter import (
    GoogleGeminiCliMessageFormatter,
)


class GoogleGeminiCliContextManager(GoogleContextManager):
    """Context manager aligned with gemini-cli tool call semantics."""

    def __init__(self, session_id: str, provider_name: str = "google-gemini-cli"):
        super().__init__(provider_name=provider_name, session_id=session_id)

    async def add_tool_result(
        self,
        tool_call_id: str,
        tool_name: str,
        result: Any,
        inject_reminders: bool = False,
    ) -> None:
        if inject_reminders:
            await self._inject_reminders_to_result(result)

        working_content = GoogleGeminiCliMessageFormatter.format_tool_result_for_context(
            tool_name,
            result,
            tool_call_id=tool_call_id,
        )

        if self.working_contents:
            last_content = self.working_contents[-1]
            if self._is_tool_result(last_content) and isinstance(last_content, dict):
                last_parts = last_content.get("parts")
                new_parts = working_content.get("parts") if isinstance(working_content, dict) else None
                if isinstance(last_parts, list) and isinstance(new_parts, list):
                    last_parts.extend(new_parts)
                    return

        self.working_contents.append(working_content)

    def _is_tool_call(self, msg: Dict[str, Any]) -> bool:
        parts = self._extract_parts(msg)
        if not parts:
            return False
        role = self._extract_role(msg)
        if role != "model":
            return False
        return all(self._part_has_function_call(part) for part in parts)

    def _is_tool_result(self, msg: Dict[str, Any]) -> bool:
        parts = self._extract_parts(msg)
        if not parts:
            return False
        role = self._extract_role(msg)
        if role != "user":
            return False
        return all(self._part_has_function_response(part) for part in parts)

    def _extract_role(self, msg: Any) -> str | None:
        if isinstance(msg, dict):
            return msg.get("role")
        return getattr(msg, "role", None)

    def _extract_parts(self, msg: Any) -> list[Any] | None:
        if isinstance(msg, dict):
            parts = msg.get("parts")
            return parts if isinstance(parts, list) else None
        parts = getattr(msg, "parts", None)
        return parts if isinstance(parts, list) else None

    def _part_has_function_call(self, part: Any) -> bool:
        if isinstance(part, dict):
            return "function_call" in part or "functionCall" in part
        return bool(getattr(part, "function_call", None))

    def _part_has_function_response(self, part: Any) -> bool:
        if isinstance(part, dict):
            return "function_response" in part or "functionResponse" in part
        return bool(getattr(part, "function_response", None))
