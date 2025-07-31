"""
BaseContextManager - Abstract base class for all LLM client Context Managers.

Designed for aiNagisa's multi-LLM architecture as a unified context management interface.
Defines core methods that all Context Managers must implement to ensure consistency and extensibility.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from backend.domain.models.messages import BaseMessage


class BaseContextManager(ABC):
    """
    Abstract base class for LLM client context managers.
    
    Defines unified interface specifications supporting:
    - Message history management and state isolation
    - Response content context preservation
    """
    
    def __init__(self):
        """Initialize base state."""
        self._messages_history: List[BaseMessage] = []
        self._current_iteration = 0
        self._execution_metadata: Dict[str, Any] = {}
    
    @abstractmethod
    def initialize_from_messages(self, messages: List[BaseMessage]) -> None:
        """
        Initialize context manager from input message list.
        
        Args:
            messages: Input message history list
        """
        pass
    
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
    
    
    # === Common utility methods ===
    
    def get_current_iteration(self) -> int:
        """Get current iteration count."""
        return self._current_iteration
    
    def increment_iteration(self) -> None:
        """Increment iteration count."""
        self._current_iteration += 1
    
    def get_messages_count(self) -> int:
        """Get message history count."""
        return len(self._messages_history)
    
    def set_execution_metadata(self, key: str, value: Any) -> None:
        """Set execution metadata."""
        self._execution_metadata[key] = value
    
    def get_execution_metadata(self, key: str, default: Any = None) -> Any:
        """Get execution metadata."""
        return self._execution_metadata.get(key, default)
    
    def clear_context(self) -> None:
        """Clear context state."""
        self._messages_history.clear()
        self._current_iteration = 0
        self._execution_metadata.clear()
    
    def get_debug_info(self) -> Dict[str, Any]:
        """Get debug information."""
        return {
            'messages_count': self.get_messages_count(),
            'current_iteration': self.get_current_iteration(),
            'execution_metadata': self._execution_metadata.copy()
        }