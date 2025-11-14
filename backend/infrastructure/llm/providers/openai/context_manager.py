"""
OpenAI Context Manager

Manages conversation context and message history for OpenAI API calls.
Handles message formatting, tool result integration, and state management.
"""

from typing import Any, Dict
from openai.types.responses import Response
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

        Processes response.output items and converts them to Responses API input format
        for use in subsequent API calls.

        Args:
            response: OpenAI API Response object
        """
        if not isinstance(response, Response):
            return

        if not response.output:
            return

        # Process each output item and convert to input format
        for item in response.output:
            # Convert Pydantic model to dict
            item_dict = item.model_dump(mode='json', exclude_none=False)
            item_type = item_dict.get("type")

            # Handle message items (assistant responses)
            if item_type == "message":
                role = item_dict.get("role")
                if not role:
                    continue

                content = item_dict.get("content", [])

                # Extract text content from response.output format
                if isinstance(content, list):
                    if not content:
                        content_value = ""
                    else:
                        # Extract only text content (skip reasoning)
                        text_parts = []
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "output_text":
                                text_parts.append(block.get("text", ""))
                            elif isinstance(block, str):
                                text_parts.append(block)
                        content_value = "".join(text_parts)
                elif isinstance(content, str):
                    content_value = content
                else:
                    content_value = str(content) if content else ""

                self.working_contents.append({
                    "role": role,
                    "content": content_value
                })

            # Handle reasoning items
            # Note: Current request's reasoning MUST be kept for pairing with function_call
            # Historical reasoning (from DB) is NOT loaded (format_single_message skips thinking)
            # This dual approach works because API only requires pairing in current request
            elif item_type == "reasoning":
                summary = item_dict.get("summary", [])
                reasoning_id = item_dict.get("id")

                # Keep reasoning item if it has an ID (required for pairing with function_call)
                # Note: Empty summary ([]) should still be kept to maintain pairing
                if reasoning_id:
                    # Keep type, id, and summary for input
                    self.working_contents.append({
                        "type": "reasoning",
                        "id": reasoning_id,
                        "summary": summary if summary else []
                    })

            # Handle function_call items
            elif item_type == "function_call":
                # Ensure arguments field exists
                if 'arguments' not in item_dict or item_dict['arguments'] is None:
                    item_dict['arguments'] = "{}"

                # Convert arguments to string if needed
                arguments = item_dict.get("arguments")
                if isinstance(arguments, dict):
                    import json
                    try:
                        arguments = json.dumps(arguments)
                    except (TypeError, ValueError):
                        arguments = "{}"
                elif arguments is None:
                    arguments = "{}"
                else:
                    arguments = str(arguments)

                # Use correct IDs for input format:
                # - id: fc_xxx (required for input[].id field)
                # - call_id: call_xxx (used to match with function_call_output)
                self.working_contents.append({
                    "type": "function_call",
                    "id": item_dict.get("id"),           # fc_xxx - required by API
                    "call_id": item_dict.get("call_id"), # call_xxx - for matching results
                    "name": item_dict.get("name"),
                    "arguments": arguments
                })

            # Handle function_call_output items (pass through)
            elif item_type == "function_call_output":
                self.working_contents.append(item_dict)
    
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
            reminders = await self._status_monitor.get_all_reminders(check_queue=True)

            if reminders:
                # StatusMonitor now returns complete system-reminder blocks
                # Just join them with newlines
                reminder_text = "\n\n" + "\n\n".join(reminders)

                # Modify result llm_content to inject reminders
                if isinstance(result, dict) and 'llm_content' in result:
                    llm_content = result.get('llm_content')

                    # Tool results use parts format: {"parts": [{"type": "text", "text": "..."}]}
                    if isinstance(llm_content, dict) and 'parts' in llm_content:
                        parts = llm_content.get('parts')
                        if isinstance(parts, list) and parts:
                            # Find last text part and append reminder
                            for part in reversed(parts):
                                if isinstance(part, dict) and part.get('type') == 'text' and 'text' in part:
                                    part['text'] += reminder_text
                                    break

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
