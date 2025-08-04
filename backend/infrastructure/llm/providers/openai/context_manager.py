"""
OpenAI Context Manager

Manages conversation context and message history for OpenAI API calls.
Handles message formatting, tool result integration, and state management.
"""

from typing import List, Dict, Any
from backend.domain.models.messages import BaseMessage
from backend.infrastructure.llm.base.context_manager import BaseContextManager
from .message_formatter import MessageFormatter
from .response_processor import ResponseProcessor


class OpenAIContextManager(BaseContextManager):
    """
    OpenAI-specific context manager for handling conversation state
    
    Manages the working message history in OpenAI API format while
    maintaining compatibility with the base context manager interface.
    """
    
    def __init__(self):
        """Initialize OpenAI context manager"""
        super().__init__(provider_name="openai")
        self._working_messages: List[Dict[str, Any]] = []
        # 注意：OpenAI 使用 _working_messages 而不是 working_contents
    
    def initialize_from_messages(self, messages: List[BaseMessage]) -> None:
        """
        Initialize context from input messages
        
        Args:
            messages: List of input messages to initialize context
        """
        # 调用基类实现，会自动设置 self.working_contents
        super().initialize_from_messages(messages)
        # OpenAI 特定：同时设置 _working_messages 以保持兼容性
        self._working_messages = self.working_contents
        self._messages_history = messages.copy()
    
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
        
        self._working_messages.append(assistant_message)
        self.increment_iteration()
    
    def extract_tool_calls_from_response(self, response) -> List[Dict[str, Any]]:
        """
        Extract tool calls from OpenAI response
        
        Args:
            response: OpenAI API response object
            
        Returns:
            List of tool call dictionaries
        """
        return ResponseProcessor.extract_tool_calls(response)
    
    def add_tool_result(self, tool_call_id: str, tool_name: str, result: Any) -> None:
        """
        Add tool execution result to context
        
        Args:
            tool_call_id: Tool call identifier
            tool_name: Name of the executed tool
            result: Tool execution result
        """
        # Format tool result content
        if isinstance(result, dict):
            # Handle structured tool results
            if "llm_content" in result:
                content = str(result["llm_content"])
            else:
                import json
                try:
                    content = json.dumps(result, ensure_ascii=False)
                except (TypeError, ValueError):
                    content = str(result)
        else:
            content = str(result)
        
        # Add tool result message
        tool_message = {
            "role": "tool",
            "content": content,
            "tool_call_id": tool_call_id
        }
        
        self._working_messages.append(tool_message)
    
    def get_working_messages(self) -> List[Dict[str, Any]]:
        """
        Get current working messages in OpenAI format
        
        Returns:
            List of OpenAI-formatted messages
        """
        return self._working_messages.copy()
    
    def should_continue_tool_calling_from_response(self, response) -> bool:
        """
        Check if tool calling should continue based on response
        
        Args:
            response: OpenAI API response object
            
        Returns:
            True if tool calling should continue
        """
        return ResponseProcessor.should_continue_tool_calling(response)
    
    def get_context_summary(self) -> Dict[str, Any]:
        """
        Get summary of current context state
        
        Returns:
            Dictionary containing context summary
        """
        return {
            **self.get_debug_info(),
            'working_messages_count': len(self._working_messages),
            'has_tool_calls': any(
                'tool_calls' in msg for msg in self._working_messages
                if isinstance(msg, dict) and msg.get('role') == 'assistant'
            ),
            'tool_results_count': len([
                msg for msg in self._working_messages
                if isinstance(msg, dict) and msg.get('role') == 'tool'
            ])
        }
    
    def clear_context(self) -> None:
        """Clear all context state"""
        super().clear_context()
        self._working_messages.clear()