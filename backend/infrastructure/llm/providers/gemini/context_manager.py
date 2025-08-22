"""
Gemini Context Manager - Manages original context during tool calls

This module is responsible for maintaining the original Gemini API response format
during tool calls, ensuring thinking chain and validation field integrity while
handling storage format messages.

Core design principles:
1. Working context: Maintain original Gemini API format with complete thinking chain and validation fields
2. Focus on context state management during tool calls
"""

from typing import Any, Optional, Dict
from backend.infrastructure.llm.base.context_manager import BaseContextManager
from backend.domain.models.messages import BaseMessage
from .message_formatter import GeminiMessageFormatter


class GeminiContextManager(BaseContextManager):
    """
    Manages context during Gemini API tool calls
    
    Core functionality:
    - Maintain working context in original format, ensuring thinking chain integrity
    - Provide context state management during tool calls
    - Support context continuity across multiple tool calls
    
    Usage scenarios:
    1. Initialization: Create initial context from message history
    2. Tool calls: Add original responses and tool results
    3. Finalization: Create standardized messages for storage
    """
    
    def __init__(self, provider_name: str = "gemini", session_id: Optional[str] = None):
        """Initialize context manager"""
        super().__init__(provider_name=provider_name, session_id=session_id)
        # working_contents already initialized in base class
    
    def add_response(self, response) -> None:
        """
        Add Gemini API response to working context
        
        Handles two types of responses:
        1. Original Gemini API response object (during tool calls)
        2. BaseMessage response (final response storage)
        
        Args:
            response: Original Gemini API response object or BaseMessage
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
            # Handle original Gemini API response
            try:
                candidate = response.candidates[0]
            except (AttributeError, IndexError):
                raise ValueError("Invalid Gemini API response format")
            
            # ✅ Official best practice: Use candidate.content directly without restructuring
            # This ensures complete preservation of all original fields including thinking chain, validation fields, etc.
            raw_content = candidate.content
            
            # Add to working context
            self.working_contents.append(raw_content)
    
    def add_tool_result(self, tool_call_id: str, tool_name: str, result: Any) -> None:
        """
        Add tool execution result to context - unified implementation
        
        Use message formatter to handle format, maintaining consistent architecture pattern with Anthropic
        
        Args:
            tool_call_id: Unique identifier for tool call (required by interface, not used by Gemini)
            tool_name: Tool name
            result: Tool execution result
        """
        # Use message formatter to handle tool result format
        working_content = GeminiMessageFormatter.format_tool_result_for_context(tool_name, result)
        
        # Add to working context
        self.working_contents.append(working_content)
    
    def _is_tool_call(self, msg: Dict[str, Any]) -> bool:
        """
        Check if message contains tool calls (Gemini format)
        
        Gemini tool calls are included as function_call in parts of assistant messages
        
        Args:
            msg: Message to check
            
        Returns:
            bool: True if message contains tool calls
        """
        if not isinstance(msg, dict):
            return False
            
        # Check if it's a model role message with parts
        if msg.get('role') != 'model' or 'parts' not in msg:
            return False
            
        # Check if parts contain function_call
        parts = msg.get('parts', [])
        if not isinstance(parts, list):
            return False
            
        for part in parts:
            if isinstance(part, dict) and 'function_call' in part:
                return True
                
        return False
    
    def _is_tool_result(self, msg: Dict[str, Any]) -> bool:
        """
        Check if message is a tool result (Gemini format)
        
        Gemini tool results are included as function_response in parts of user messages
        
        Args:
            msg: Message to check
            
        Returns:
            bool: True if message is a tool result
        """
        if not isinstance(msg, dict):
            return False
            
        # Check if it's a user role message with parts
        if msg.get('role') != 'user' or 'parts' not in msg:
            return False
            
        # Check if parts contain function_response
        parts = msg.get('parts', [])
        if not isinstance(parts, list):
            return False
            
        for part in parts:
            if isinstance(part, dict) and 'function_response' in part:
                return True
                
        return False
