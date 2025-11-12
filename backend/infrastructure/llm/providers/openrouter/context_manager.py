"""
OpenRouter Context Manager

Manages conversation context and message history for OpenRouter API calls.
Handles ChatCompletion responses (using OpenAI Chat Completions API format).
"""

from typing import Any, Dict
from openai.types.chat import ChatCompletion
from backend.infrastructure.llm.base.context_manager import BaseContextManager
from backend.domain.models.messages import BaseMessage
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

        Handles two types of responses:
        1. ChatCompletion response (during tool calls)
        2. BaseMessage response (final response storage)

        Args:
            response: ChatCompletion object or BaseMessage
        """
        if isinstance(response, BaseMessage):
            # Handle final BaseMessage response
            formatted_response = OpenRouterMessageFormatter.format_single_message(response)
            self.working_contents.append(formatted_response)

        elif isinstance(response, ChatCompletion):
            # Handle ChatCompletion response
            if not response.choices:
                return

            choice = response.choices[0]
            message = choice.message

            # Build message dict in Chat Completions format
            message_dict: Dict[str, Any] = {
                "role": message.role,
                "content": message.content
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
            reminders = await self._status_monitor.get_all_reminders(check_queue=True)
            print(f"[DEBUG] OpenRouterContextManager.add_tool_result: Got {len(reminders)} reminders")

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
                                    print(f"[DEBUG] Injected reminders to tool result parts")
                                    break

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
