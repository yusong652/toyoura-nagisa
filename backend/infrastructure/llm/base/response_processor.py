"""
Base response processor - Abstract base class for response processing.

This module provides the foundation for all provider-specific response processors,
ensuring consistent response handling across different LLM providers.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from backend.domain.models.messages import BaseMessage, AssistantMessage


class BaseResponseProcessor(ABC):
    """
    Abstract base class for response processors.
    
    Defines unified interface for processing LLM API responses, extracting content,
    handling tool calls, and formatting responses for storage and display.
    """
    
    @staticmethod
    @abstractmethod
    def extract_text_content(response) -> str:
        """
        Extract text content from LLM API response.
        
        Args:
            response: Raw LLM API response object
            
        Returns:
            str: Extracted text content
        """
        pass
    
    @staticmethod
    @abstractmethod
    def extract_tool_calls(response) -> List[Dict[str, Any]]:
        """
        Extract tool call information from LLM API response.
        
        Args:
            response: Raw LLM API response object
            
        Returns:
            List[Dict[str, Any]]: List of tool calls with name, arguments, id, etc.
        """
        pass
    
    @staticmethod
    @abstractmethod
    def should_continue_tool_calling(response) -> bool:
        """
        Determine if tool calling should continue based on response.
        
        Args:
            response: Raw LLM API response object
            
        Returns:
            bool: True if response contains tool calls that need execution
        """
        pass
    
    @staticmethod
    @abstractmethod
    def format_response_for_storage(response) -> BaseMessage:
        """
        Format LLM API response for storage in conversation history.
        
        Args:
            response: Raw LLM API response object
            
        Returns:
            BaseMessage: Formatted message for storage
        """
        pass
    
    @staticmethod
    def extract_thinking_content(response) -> Optional[str]:
        """
        Extract thinking/reasoning content from response (shared utility).
        
        Args:
            response: Raw LLM API response object
            
        Returns:
            Optional[str]: Extracted thinking content, None if not available
        """
        # Default implementation - providers can override
        return None
    
    @staticmethod
    def has_tool_calls(response) -> bool:
        """
        Check if response contains tool calls (shared utility).
        
        Args:
            response: Raw LLM API response object
            
        Returns:
            bool: True if response contains tool calls
        """
        # Default implementation - providers should override
        return False
    
    @staticmethod
    def extract_web_search_sources(response, debug: bool = False) -> List[Dict[str, Any]]:
        """
        Extract web search sources from response (shared utility for providers that support it).
        
        Args:
            response: Raw LLM API response object
            debug: Enable debug output
            
        Returns:
            List[Dict[str, Any]]: List of web search sources
        """
        # Default implementation - providers can override
        return []