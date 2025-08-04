"""
BaseContextManager - Abstract base class for all LLM client Context Managers.

Designed for aiNagisa's multi-LLM architecture as a unified context management interface.
Defines core methods that all Context Managers must implement to ensure consistency and extensibility.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
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
        self._messages_history: List[BaseMessage] = []
        self._current_iteration = 0
        self._execution_metadata: Dict[str, Any] = {}
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
    
    # === Common tool result processing methods ===
    
    @staticmethod
    def process_tool_result_for_llm(result: Any) -> Dict[str, Any]:
        """
        Process tool result to extract LLM-relevant content.
        
        Handles standard ToolResult format with llm_content field.
        
        Args:
            result: Raw tool execution result
            
        Returns:
            Processed result dictionary for LLM consumption
        """
        if isinstance(result, dict):
            # If result has llm_content field (ToolResult format), prioritize it
            if 'llm_content' in result and result['llm_content'] is not None:
                return result['llm_content'] if isinstance(result['llm_content'], dict) else {"content": result['llm_content']}
            elif 'status' in result and 'message' in result:
                # ToolResult format without llm_content, use message field
                return {"result": result['message']}
            else:
                # Traditional format, use as-is
                return result.copy()
        elif isinstance(result, str):
            return {"result": result}
        else:
            return {"result": str(result)}
    
    @staticmethod
    def has_multimodal_content(result: Any) -> bool:
        """
        Check if tool result contains multimodal content.
        
        Args:
            result: Tool execution result
            
        Returns:
            True if result contains multimodal content
        """
        if not isinstance(result, dict):
            return False
        
        # Check new unified format
        if 'inline_data' in result:
            return True
        
        # Check legacy format
        if result.get('data', {}).get('processing_result', {}).get('content_format') == 'inline_data':
            return True
        
        return False
    
    @staticmethod
    def extract_inline_data(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract inline data from tool result.
        
        Args:
            result: Tool execution result
            
        Returns:
            Inline data dictionary with mime_type and data, or None
        """
        if not isinstance(result, dict):
            return None
        
        # Check new unified format
        if 'inline_data' in result:
            return result['inline_data']
        
        # Check legacy format
        if result.get('data', {}).get('processing_result', {}).get('content_format') == 'inline_data':
            return result['data']['processing_result']['content']['inline_data']
        
        return None
    
    @staticmethod
    def filter_multimodal_from_response(response_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter out large multimodal data from response to avoid duplication.
        
        Args:
            response_dict: Response dictionary potentially containing inline_data
            
        Returns:
            Filtered response dictionary
        """
        if 'inline_data' in response_dict:
            return {k: v for k, v in response_dict.items() if k != 'inline_data'}
        return response_dict
    
    @staticmethod
    def debug_multimodal_content(tool_name: str, mime_type: str, data_size: int):
        """
        Print debug information for multimodal content.
        
        Args:
            tool_name: Name of the tool that generated the content
            mime_type: MIME type of the content
            data_size: Size of the data in bytes
        """
        print(f"[DEBUG] Created multimodal Part for {tool_name}: {mime_type}, {data_size} bytes")