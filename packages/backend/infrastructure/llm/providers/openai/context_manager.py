"""
OpenAI Context Manager

Manages conversation context and message history for OpenAI API calls.
Handles message formatting, tool result integration, and state management.
"""

from typing import Any, Dict
from backend.infrastructure.llm.base.context_manager import BaseContextManager
from .message_formatter import OpenAIMessageFormatter


class OpenAIContextManager(BaseContextManager):
    """
    OpenAI-specific context manager for handling conversation state
    
    Manages the working message history in OpenAI API format while
    maintaining compatibility with the base context manager interface.
    """
    
    def __init__(self,session_id: str, provider_name: str = "openai"):
        """Initialize OpenAI context manager"""
        super().__init__(provider_name=provider_name, session_id=session_id)
        # Unified use of working_contents, removing legacy _working_messages
    
    def add_response(self, response) -> None:
        """
        Add OpenAI API response to context

        Args:
            response: OpenAI API Response object
        """
        from .response_processor import OpenAIResponseProcessor

        # Delegate formatting to response processor for separation of concerns
        context_items = OpenAIResponseProcessor.format_response_for_context(response)

        # Note: Use extend() instead of append() because OpenAI returns a list
        # (one response can produce multiple context items: message, reasoning, function_call)
        self.working_contents.extend(context_items)
    
    async def add_tool_result(self, tool_call_id: str, tool_name: str, result: Any, inject_reminders: bool = False) -> None:
        """
        Add tool execution result to context (async)

        Args:
            tool_call_id: Tool call identifier
            tool_name: Name of the executed tool
            result: Tool execution result (can contain inline_data for images)
            inject_reminders: Whether to inject system reminders into this result
        """
        # Inject system reminders to result content if needed (async)
        if inject_reminders:
            await self._inject_reminders_to_result(result)

        # Format tool result using message formatter
        tool_result_item = OpenAIMessageFormatter.format_tool_result_for_context(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            result=result
        )

        self.working_contents.append(tool_result_item)
    
    def _is_tool_call(self, msg: Dict[str, Any]) -> bool:
        """
        Check if message contains tool calls (OpenAI Responses API format)

        In Responses API, tool calls are:
        - type="function_call" items
        - type="reasoning" items (paired with function_call)

        Args:
            msg: Message to check

        Returns:
            bool: True if message contains tool calls or reasoning
        """
        if not isinstance(msg, dict):
            return False

        # Check for Responses API format
        item_type = msg.get('type')
        return item_type in ('function_call', 'reasoning')

    def _is_tool_result(self, msg: Dict[str, Any]) -> bool:
        """
        Check if message is a tool result (OpenAI Responses API format)

        In Responses API, tool results are type="function_call_output" items

        Args:
            msg: Message to check

        Returns:
            bool: True if message is a tool result
        """
        if not isinstance(msg, dict):
            return False

        # Check for Responses API format
        return msg.get('type') == 'function_call_output'
