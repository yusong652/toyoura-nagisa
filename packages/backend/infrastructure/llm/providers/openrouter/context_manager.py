"""
OpenRouter Context Manager

Manages conversation context and message history for OpenRouter API calls.
Handles ChatCompletion responses (using OpenAI Chat Completions API format).
"""

from typing import Any, Dict
from backend.infrastructure.llm.base.context_manager import BaseContextManager
from .message_formatter import OpenRouterMessageFormatter


class OpenRouterContextManager(BaseContextManager):
    """
    OpenRouter-specific context manager for handling conversation state.

    OpenRouter uses Chat Completions API which returns ChatCompletion objects.
    """

    def __init__(self, session_id: str, provider_name: str = "openrouter"):
        """Initialize OpenRouter context manager"""
        super().__init__(provider_name=provider_name, session_id=session_id)

    def add_response(self, response) -> None:
        """
        Add OpenRouter API response to context.

        Args:
            response: ChatCompletion object from OpenRouter API
        """
        from .response_processor import OpenRouterResponseProcessor

        # Delegate formatting to response processor for separation of concerns
        message_dict = OpenRouterResponseProcessor.format_response_for_context(response)
        if message_dict:
            self.working_contents.append(message_dict)

    async def add_tool_result(
        self,
        tool_call_id: str,
        tool_name: str,  # noqa: ARG002 - required by base class interface
        result: Any,
        inject_reminders: bool = False
    ) -> None:
        """
        Add tool execution result to context (async).

        Args:
            tool_call_id: Tool call identifier
            tool_name: Name of the executed tool (required by base class interface)
            result: Tool execution result (can contain inline_data for images)
            inject_reminders: Whether to inject system reminders into this result
        """
        # Inject system reminders to result content if needed (async)
        if inject_reminders:
            await self._inject_reminders_to_result(result)

        # Format tool result content using message formatter
        content = OpenRouterMessageFormatter._format_tool_result(result)

        # Add tool result in Chat Completions format (role: "tool")
        tool_result_message = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content
        }

        self.working_contents.append(tool_result_message)

    def _is_tool_call(self, msg: Dict[str, Any]) -> bool:
        """
        Check if message contains tool calls (Chat Completions format).

        OpenRouter tool calls are included as tool_calls field in assistant messages,
        same as OpenAI Chat Completions API.

        Args:
            msg: Message to check

        Returns:
            bool: True if message contains tool calls
        """
        if not isinstance(msg, dict):
            return False

        # Check if it's an assistant role with tool_calls
        return (msg.get('role') == 'assistant' and
                'tool_calls' in msg and
                msg['tool_calls'] and
                len(msg['tool_calls']) > 0)

    def _is_tool_result(self, msg: Dict[str, Any]) -> bool:
        """
        Check if message is a tool result (Chat Completions format).

        OpenRouter tool results have role 'tool' and contain tool_call_id,
        same as OpenAI Chat Completions API.

        Args:
            msg: Message to check

        Returns:
            bool: True if message is a tool result
        """
        if not isinstance(msg, dict):
            return False

        # Check if it's a tool role with tool_call_id
        return bool(msg.get('role') == 'tool' and
                   'tool_call_id' in msg and
                   msg.get('tool_call_id'))


__all__ = ['OpenRouterContextManager']
