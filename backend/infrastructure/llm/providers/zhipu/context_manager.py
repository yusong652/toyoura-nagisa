"""
Zhipu (智谱) Context Manager

Manages conversation context and message history for Zhipu API calls.
Handles ChatCompletion responses from zai SDK.
"""

from typing import Any, Dict
from backend.infrastructure.llm.base.context_manager import BaseContextManager
from backend.domain.models.messages import BaseMessage
from .message_formatter import ZhipuMessageFormatter


class ZhipuContextManager(BaseContextManager):
    """
    Zhipu-specific context manager for handling conversation state.

    Uses zai SDK which returns ChatCompletion-like objects.
    Supports reasoning_content (thinking) from GLM models.
    """

    def __init__(self, session_id: str, provider_name: str = "zhipu"):
        """Initialize Zhipu context manager"""
        super().__init__(provider_name=provider_name, session_id=session_id)

    def add_response(self, response) -> None:
        """
        Add Zhipu API response to context.

        Handles two types of responses:
        1. ChatCompletion-like response (during tool calls)
        2. BaseMessage response (final response storage)

        Args:
            response: ChatCompletion-like object or BaseMessage
        """
        if isinstance(response, BaseMessage):
            # Handle final BaseMessage response
            formatted_response = ZhipuMessageFormatter.format_single_message(response)
            self.working_contents.append(formatted_response)

        elif hasattr(response, 'choices') and response.choices:
            # Handle ChatCompletion-like response from zai SDK
            choice = response.choices[0]
            message = choice.message

            # Extract reasoning content (GLM thinking models)
            reasoning_content = getattr(message, 'reasoning_content', None)

            # Build content - handle reasoning_content for proper context preservation
            content_value: Any = message.content

            # If reasoning_content exists, format as multimodal content array
            if reasoning_content:
                # Convert to multimodal format
                content_blocks = []

                # Add thinking content wrapped in <thinking> tags
                content_blocks.append({
                    "type": "text",
                    "text": f"<thinking>{reasoning_content}</thinking>"
                })

                # Add regular content if present
                if message.content:
                    content_blocks.append({
                        "type": "text",
                        "text": message.content
                    })

                content_value = content_blocks

            # Build message dict
            message_dict: Dict[str, Any] = {
                "role": message.role,
                "content": content_value
            }

            # Add tool calls if present
            if hasattr(message, 'tool_calls') and message.tool_calls:
                # Convert tool calls to dict format
                tool_calls_list = []
                for tool_call in message.tool_calls:
                    function_info = tool_call.function

                    # Handle both object and dict formats
                    # zai SDK might return either depending on the response structure
                    if isinstance(function_info, dict):
                        function_name = function_info.get('name', '')
                        function_arguments = function_info.get('arguments', '')
                    else:
                        # Object with attributes
                        function_name = getattr(function_info, 'name', '')
                        function_arguments = getattr(function_info, 'arguments', '')

                    tool_calls_list.append({
                        "id": tool_call.id,
                        "type": tool_call.type,
                        "function": {
                            "name": function_name,
                            "arguments": function_arguments
                        }
                    })
                message_dict["tool_calls"] = tool_calls_list

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
            result: Tool execution result
            inject_reminders: Whether to inject system reminders into this result
        """
        # Inject system reminders to result content if needed (async)
        if inject_reminders:
            reminders = await self._status_monitor.get_all_reminders(check_queue=True)

            if reminders:
                reminder_text = "\n\n" + "\n\n".join(reminders)

                # Modify result llm_content to inject reminders
                if isinstance(result, dict) and 'llm_content' in result:
                    llm_content = result.get('llm_content')

                    # Tool results use parts format
                    if isinstance(llm_content, dict) and 'parts' in llm_content:
                        parts = llm_content.get('parts')
                        if isinstance(parts, list) and parts:
                            # Find last text part and append reminder
                            for part in reversed(parts):
                                if isinstance(part, dict) and part.get('type') == 'text' and 'text' in part:
                                    part['text'] += reminder_text
                                    break

        # Format tool result content using message formatter
        content = ZhipuMessageFormatter._format_tool_result(result)

        # Add tool result message (role: "tool")
        tool_result_message = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content
        }

        self.working_contents.append(tool_result_message)

    def _is_tool_call(self, msg: Dict[str, Any]) -> bool:
        """
        Check if message contains tool calls.

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
        Check if message is a tool result.

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


__all__ = ['ZhipuContextManager']
