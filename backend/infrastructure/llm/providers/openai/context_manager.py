"""
OpenAI Context Manager

Manages conversation context and message history for OpenAI API calls.
Handles message formatting, tool result integration, and state management.
"""

from typing import Any
from backend.infrastructure.llm.base.context_manager import BaseContextManager
from .message_formatter import OpenAIMessageFormatter
from .response_processor import OpenAIResponseProcessor


class OpenAIContextManager(BaseContextManager):
    """
    OpenAI-specific context manager for handling conversation state
    
    Manages the working message history in OpenAI API format while
    maintaining compatibility with the base context manager interface.
    """
    
    def __init__(self):
        """Initialize OpenAI context manager"""
        super().__init__(provider_name="openai")
        # 统一使用 working_contents，移除历史遗留的 _working_messages
    
    def add_response(self, response) -> None:
        """
        Add OpenAI API response to context
        
        Args:
            response: OpenAI API response object
        """
        if not hasattr(response, 'choices') or not response.choices:
            return
        
        choice = response.choices[0].message
        
        # Build assistant message
        assistant_message = {
            "role": "assistant",
            "content": choice.content or ""
        }
        
        # Add tool calls if present
        if hasattr(choice, 'tool_calls') and choice.tool_calls:
            assistant_message["tool_calls"] = []
            for tool_call in choice.tool_calls:
                assistant_message["tool_calls"].append({
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments
                    }
                })
        
        self.working_contents.append(assistant_message)
        self.increment_iteration()
    
    def add_tool_result(self, tool_call_id: str, tool_name: str, result: Any) -> None:
        """
        Add tool execution result to context
        
        Args:
            tool_call_id: Tool call identifier
            tool_name: Name of the executed tool
            result: Tool execution result (can contain inline_data for images)
        """
        # Format tool result content using message formatter
        content = OpenAIMessageFormatter._format_tool_result(result)
        
        # Add tool result message
        tool_message = {
            "role": "tool",
            "content": content,
            "tool_call_id": tool_call_id
        }
        
        self.working_contents.append(tool_message)