"""
Enhanced LLM Client Base with SOTA streaming architecture.

This module provides the foundational LLMClientBase class that all provider-specific
clients inherit from, implementing common patterns extracted from the Gemini implementation.
"""

import os
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple, AsyncGenerator, Union
from backend.domain.models.messages import BaseMessage
from backend.infrastructure.llm.response_models import LLMResponse
from backend.config import get_system_prompt


class LLMClientBase(ABC):
    """
    Enhanced LLM client base class with unified streaming architecture.
    
    SOTA streaming architecture design focused on real-time tool call notifications:
    - Core interface: get_response() - streaming processing with real-time notifications
    - Specialized interfaces: generate_title_from_messages(), generate_text_to_image_prompt()
    - Configuration management: update_config() - dynamic configuration updates
    
    Architecture advantages:
    - Real-time: instant status updates during tool calling processes
    - Efficient: AsyncGenerator implementation with zero-latency event delivery
    - Consistent: unified streaming interface avoiding redundant wrappers
    """
    
    def __init__(self, tools_enabled: bool = True, extra_config: Dict[str, Any] = None):
        """
        Initialize LLM client base class.
        
        Args:
            tools_enabled: Whether to enable tool calling functionality
            extra_config: Additional configuration parameters
        """
        self.tools_enabled = tools_enabled
        self.extra_config = extra_config or {}
        
        # Common client attributes that all implementations should have
        self.client = None  # Will be set by concrete implementations
        self.tool_manager = None  # Will be initialized by concrete implementations

    @abstractmethod
    async def get_response(
        self,
        messages: List[BaseMessage],
        session_id: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[Union[Dict[str, Any], Tuple[BaseMessage, Dict[str, Any]]], None]:
        """
        [Core Interface] Get LLM response with real-time tool calling notifications.
        
        SOTA architecture designed for real-time tool calling notifications using streaming state machine pattern:
        1. Real-time yield tool call start/progress/completion notifications
        2. Real-time yield tool execution progress and status updates
        3. Final yield complete response and execution metadata
        4. Complete error handling and recovery mechanisms
        
        This method is the core of the new architecture, solving traditional batch notification latency issues,
        allowing frontend to perceive tool calling status in real-time, significantly improving user experience.
        
        Args:
            messages: Input message list
            session_id: Session ID for tool and context management
            **kwargs: Additional parameters (like max_iterations, temperature, etc.)
            
        Yields:
            Union[Dict[str, Any], Tuple[BaseMessage, Dict[str, Any]]]:
            - Dict[str, Any]: Intermediate notifications (tool calling status updates)
            - Tuple[BaseMessage, Dict[str, Any]]: Final result (final_message, execution_metadata)
            
        Note:
            Notification format examples:
            - Tool start: {'type': 'NAGISA_IS_USING_TOOL', 'tool_name': 'search', 'action_text': 'Searching...'}
            - Tool progress: {'type': 'NAGISA_IS_USING_TOOL', 'tool_name': 'search', 'action_text': 'Using search tool...'}
            - Tool completion: {'type': 'NAGISA_IS_USING_TOOL', 'tool_name': 'search', 'action_text': 'Completed search'}
            - Sequence end: {'type': 'NAGISA_TOOL_USE_CONCLUDED'}
            - Final result: (final_message, {'execution_id': '...', 'tool_calls_executed': 3, ...})
        """
        pass

    def update_config(self, **kwargs):
        """
        Update client configuration.
        
        Args:
            **kwargs: Configuration parameters to update
        """
        # Provide default implementation, subclasses can override
        for key, value in kwargs.items():
            setattr(self, key, value)
            # Also update extra_config
            self.extra_config[key] = value

    # ========== SHARED UTILITY METHODS ==========

    def _generate_execution_id(self) -> str:
        """Generate unique execution ID."""
        import uuid
        return f"EXE_{str(uuid.uuid4())[:8]}"
    
    def _get_timestamp(self) -> float:
        """Get current timestamp."""
        import time
        return time.time()

    async def _clear_session_tool_cache(self, session_id: str):
        """Clear session tool cache - shared implementation."""
        if self.tool_manager and hasattr(self.tool_manager, 'clear_session_tool_cache'):
            self.tool_manager.clear_session_tool_cache(session_id)

    # ========== SPECIALIZED CONTENT GENERATION INTERFACES ==========

    async def generate_title_from_messages(
        self,
        first_user_message: BaseMessage,
        first_assistant_message: BaseMessage,
        title_generation_system_prompt: Optional[str] = None
    ) -> Optional[str]:
        """
        [Optional Interface] Generate title from conversation messages.
        
        Args:
            first_user_message: First user message
            first_assistant_message: First assistant message
            title_generation_system_prompt: Optional title generation system prompt
            
        Returns:
            Generated title string, or None if failed
            
        Raises:
            NotImplementedError: If client doesn't support this functionality
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support title generation"
        )

    async def generate_text_to_image_prompt(
        self, 
        session_id: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        """
        [Optional Interface] Generate text-to-image prompt.
        
        Args:
            session_id: Session ID for getting context
            
        Returns:
            Dictionary containing text prompt and negative prompt, or None if failed
            
        Raises:
            NotImplementedError: If client doesn't support this functionality
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support image prompt generation"
        )

    async def perform_web_search(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        [Optional Interface] Perform web search.
        
        Args:
            query: Search query
            **kwargs: Additional search parameters
            
        Returns:
            Dictionary containing search results
            
        Raises:
            NotImplementedError: If client doesn't support this functionality  
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support web search"
        )

    # ========== ABSTRACT METHODS FOR PROVIDER-SPECIFIC IMPLEMENTATION ==========

    @abstractmethod
    async def get_function_call_schemas(self, session_id: Optional[str] = None):
        """
        Get function call schemas for tool registration.
        
        Args:
            session_id: Optional session ID for context-specific tools
            
        Returns:
            List of tool schemas in provider-specific format
        """
        pass

    @abstractmethod 
    async def call_api_with_context(
        self, 
        context_contents: List[Dict[str, Any]], 
        session_id: Optional[str] = None,
        **kwargs
    ):
        """
        Direct API call using context contents in provider-specific format.
        
        Args:
            context_contents: Pre-formatted context contents
            session_id: Optional session ID for tool schema retrieval
            **kwargs: Additional parameters for API configuration
            
        Returns:
            Raw API response object
        """
        pass