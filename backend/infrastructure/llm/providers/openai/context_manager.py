"""
OpenAI Context Manager

Manages conversation context and message history for OpenAI API calls.
Handles message formatting, tool result integration, and state management.
"""

from typing import Any, Optional, Dict
from backend.infrastructure.llm.base.context_manager import BaseContextManager
from backend.domain.models.messages import BaseMessage
from .message_formatter import OpenAIMessageFormatter
from .response_processor import OpenAIResponseProcessor


class OpenAIContextManager(BaseContextManager):
    """
    OpenAI-specific context manager for handling conversation state
    
    Manages the working message history in OpenAI API format while
    maintaining compatibility with the base context manager interface.
    """
    
    def __init__(self, provider_name: str = "openai", session_id: Optional[str] = None):
        """Initialize OpenAI context manager"""
        super().__init__(provider_name=provider_name, session_id=session_id)
        # Unified use of working_contents, removing legacy _working_messages
    
    def add_response(self, response) -> None:
        """
        Add OpenAI API response to context
        
        Handles two types of responses:
        1. Original OpenAI API response object (during tool calls)
        2. BaseMessage response (final response storage)
        
        Args:
            response: OpenAI API response object or BaseMessage
        """
        if isinstance(response, BaseMessage):
            # Handle final BaseMessage response
            self._message_history.append(response)
            
            # Format and add to working context
            from backend.infrastructure.llm.shared.utils.provider_registry import get_message_formatter_class
            formatter_class = get_message_formatter_class(self._provider_name)
            formatted_response = formatter_class.format_single_message(response)
            
            self.working_contents.append(formatted_response)
        else:
            # Handle original OpenAI API response
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
    
    def _is_tool_call(self, msg: Dict[str, Any]) -> bool:
        """
        Check if message contains tool calls (OpenAI format)
        
        OpenAI tool calls are included as tool_calls field in assistant messages
        
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
        Check if message is a tool result (OpenAI format)
        
        OpenAI tool results have role 'tool' and contain tool_call_id
        
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