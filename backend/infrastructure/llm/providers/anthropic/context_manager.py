"""
AnthropicContextManager - Anthropic Claude specialized context manager

Context management implementation optimized for Anthropic API response formats and tool calling mechanisms.
Adopts the same dual-track design as Gemini: maintain original API format for working context, standardized format for storage.
"""

from typing import Any, Optional, Dict
from backend.infrastructure.llm.base.context_manager import BaseContextManager
from backend.domain.models.messages import BaseMessage


class AnthropicContextManager(BaseContextManager):
    """
    Anthropic Claude specialized context manager
    
    Focus on working context management:
    - Working context: Maintain original Anthropic API format, ensuring integrity
    - Support context state management during tool calls
    """
    
    def __init__(self, provider_name: str = "anthropic", session_id: Optional[str] = None):
        super().__init__(provider_name=provider_name, session_id=session_id)
        # Unified use of working_contents, removing legacy working_messages
    
    def add_response(self, response) -> None:
        """
        Add Anthropic API response to context
        
        Handles two types of responses:
        1. Original Anthropic API response object (during tool calls)
        2. BaseMessage response (final response storage)
        
        Args:
            response: Anthropic API response object or BaseMessage
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
            # Handle original Anthropic API response
            if not hasattr(response, 'content') or not response.content:
                raise ValueError("Invalid Anthropic API response format")
            
            # ✅ Per official documentation: Filter response object, keep only API-supported fields
            # Official API only supports role and content fields
            filtered_message = {
                "role": response.role,
                "content": response.content
            }
            self.working_contents.append(filtered_message)
    
    def add_tool_result(self, tool_call_id: str, tool_name: str, result: Any) -> None:
        """
        Add tool execution result to context - unified implementation
        
        Use message formatter to handle format, maintaining architectural consistency
        
        Args:
            tool_call_id: Unique identifier for tool call
            tool_name: Tool name
            result: Tool execution result
        """
        from .message_formatter import MessageFormatter
        
        # Use message formatter to handle tool result format
        working_content = MessageFormatter.format_tool_result_for_context(tool_call_id, tool_name, result)
        
        # Add to working context
        self.working_contents.append(working_content)
    
    def _is_tool_call(self, msg: Dict[str, Any]) -> bool:
        """
        Check if message contains tool calls (Anthropic format)
        
        Anthropic tool calls are included as tool_use blocks in assistant message content
        
        Args:
            msg: Message to check
            
        Returns:
            bool: True if message contains tool calls
        """
        if not isinstance(msg, dict):
            return False
            
        # Check if it's an assistant role with content
        if msg.get('role') != 'assistant' or 'content' not in msg:
            return False
            
        # Check if content contains tool_use blocks
        content = msg.get('content', [])
        if not isinstance(content, list):
            return False
            
        for block in content:
            if isinstance(block, dict) and block.get('type') == 'tool_use':
                return True
                
        return False
    
    def _is_tool_result(self, msg: Dict[str, Any]) -> bool:
        """
        Check if message is a tool result (Anthropic format)
        
        Anthropic tool results are included as tool_result blocks in user message content
        
        Args:
            msg: Message to check
            
        Returns:
            bool: True if message is a tool result
        """
        if not isinstance(msg, dict):
            return False
            
        # Check if it's a user role with content
        if msg.get('role') != 'user' or 'content' not in msg:
            return False
            
        # Check if content contains tool_result blocks
        content = msg.get('content', [])
        if not isinstance(content, list):
            return False
            
        for block in content:
            if isinstance(block, dict) and block.get('type') == 'tool_result':
                return True
                
        return False
