"""
BaseContextManager - Abstract base class for all LLM client Context Managers.

Designed for aiNagisa's multi-LLM architecture as a unified context management interface.
Defines core methods that all Context Managers must implement to ensure consistency and extensibility.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from backend.domain.models.messages import BaseMessage
from backend.infrastructure.llm.shared.utils.provider_registry import get_message_formatter_class


class BaseContextManager(ABC):
    """
    Abstract base class for LLM client context managers.
    
    Defines unified interface specifications supporting:
    - Message history management and state isolation
    - Response content context preservation
    - Automatic provider-specific message formatting
    """
    
    def __init__(self, provider_name: Optional[str] = None):
        """
        Initialize base state.
        
        Args:
            provider_name: Name of the LLM provider (e.g., 'gemini', 'anthropic', 'openai')
        """
        self._provider_name = provider_name
        # Working contents will be populated by initialize_from_messages
        self.working_contents: List[Dict[str, Any]] = []
    
    def initialize_from_messages(self, messages: List[BaseMessage]) -> None:
        """
        Initialize context manager from input message list.
        
        Uses provider-specific message formatter to convert messages
        to the appropriate format for the LLM API.
        
        Args:
            messages: Input message history list
            
        Raises:
            ValueError: If provider name is not set
        """
        if not self._provider_name:
            raise ValueError("Provider name not set in context manager")
            
        # Get the appropriate message formatter
        formatter_class = get_message_formatter_class(self._provider_name)
        
        # Call the unified format_messages method
        self.working_contents = formatter_class.format_messages(messages)
    
    @abstractmethod
    def add_response(self, response) -> None:
        """
        Add LLM API response to context.
        
        Args:
            response: Raw response object from LLM API
        """
        pass
    
    
    @abstractmethod
    def add_tool_result(self, tool_call_id: str, tool_name: str, result: Any) -> None:
        """
        Add tool execution result to context.
        
        Args:
            tool_call_id: Unique identifier for tool call
            tool_name: Tool name
            result: Tool execution result
        """
        pass
    
    def get_working_contents(self) -> List[Dict[str, Any]]:
        """
        Get working context contents for API calls.
        
        Returns:
            List[Dict[str, Any]]: Current working contents in provider-specific format
        """
        return self.working_contents
