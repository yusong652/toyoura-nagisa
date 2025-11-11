"""
Kimi (Moonshot) Context Manager

Manages conversation context and message history for Kimi API calls.
Handles ChatCompletion responses (unlike OpenAI's Responses API).
"""

from typing import Any, Dict
from openai.types.chat import ChatCompletion
from backend.infrastructure.llm.base.context_manager import BaseContextManager
from backend.domain.models.messages import BaseMessage
from .message_formatter import KimiMessageFormatter


class KimiContextManager(BaseContextManager):
    """
    Kimi-specific context manager for handling conversation state.

    Unlike OpenAI's Responses API, Kimi uses Chat Completions API which
    returns ChatCompletion objects instead of Response objects.
    """

    def __init__(self, session_id: str, provider_name: str = "kimi"):
        """Initialize Kimi context manager"""
        super().__init__(provider_name=provider_name, session_id=session_id)

    def add_response(self, response) -> None:
        """
        Add Kimi API response to context.

        Handles two types of responses:
        1. ChatCompletion response (during tool calls)
        2. BaseMessage response (final response storage)

        Args:
            response: ChatCompletion object or BaseMessage
        """
        if isinstance(response, BaseMessage):
            # Handle final BaseMessage response
            formatted_response = KimiMessageFormatter.format_single_message(response)
            self.working_contents.append(formatted_response)

        elif isinstance(response, ChatCompletion):
            # Handle ChatCompletion response
            if not response.choices:
                return

            choice = response.choices[0]
            message = choice.message

            # Extract reasoning content (K2 Thinking models)
            reasoning_content = getattr(message, 'reasoning_content', None)

            # Build content - handle reasoning_content for proper context preservation
            # Important: For multi-turn tool calling, we must preserve thinking in context
            # so the model can maintain its reasoning chain across turns
            content_value: Any = message.content

            # If reasoning_content exists, format as multimodal content array
            # This ensures thinking is preserved in conversation history
            if reasoning_content:
                # Convert to multimodal format following OpenAI's pattern
                content_blocks = []

                # Add thinking content wrapped in <thinking> tags
                # This format is compatible with OpenAI's message formatter
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

            # Build message dict in Chat Completions format
            message_dict: Dict[str, Any] = {
                "role": message.role,
                "content": content_value
            }

            # Add tool calls if present
            if message.tool_calls:
                # Convert tool calls to dict format
                tool_calls_list = []
                for tool_call in message.tool_calls:
                    # tool_call is ChatCompletionMessageToolCall with id, type, function
                    function_info = tool_call.function  # type: ignore
                    tool_calls_list.append({
                        "id": tool_call.id,
                        "type": tool_call.type,
                        "function": {
                            "name": function_info.name,  # type: ignore
                            "arguments": function_info.arguments  # type: ignore
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
            result: Tool execution result (can contain inline_data for images)
            inject_reminders: Whether to inject system reminders into this result
        """
        # Inject system reminders to result content if needed (async)
        if inject_reminders:
            reminders = await self._get_background_task_reminders()

            if reminders:
                reminder_text = "\n\n" + "\n\n".join([
                    f"<system-reminder>\n{reminder}\n</system-reminder>"
                    for reminder in reminders
                ])

                # Modify result llm_content to inject reminders
                if isinstance(result, dict) and 'llm_content' in result:
                    llm_content = result['llm_content']

                    # Tool results use parts format
                    if isinstance(llm_content, dict) and 'parts' in llm_content:
                        parts = llm_content.get('parts', [])
                        if isinstance(parts, list):
                            # Find last text part and append reminder
                            for part in reversed(parts):
                                if isinstance(part, dict) and part.get('type') == 'text' and 'text' in part:
                                    part['text'] += reminder_text
                                    break

        # Format tool result content using message formatter
        content = KimiMessageFormatter._format_tool_result(result)

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

        Kimi tool calls are included as tool_calls field in assistant messages,
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

        Kimi tool results have role 'tool' and contain tool_call_id,
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


__all__ = ['KimiContextManager']
