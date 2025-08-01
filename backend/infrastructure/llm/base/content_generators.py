"""
Base content generators - Abstract base classes for specialized content generation.

This module provides the foundation for all provider-specific content generators,
extracting common patterns and providing shared interfaces.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from backend.domain.models.messages import BaseMessage


class BaseContentGenerator(ABC):
    """
    Abstract base class for content generators.
    
    Provides common interface for specialized content generation utilities
    like title generation, image prompt generation, and web search.
    """
    
    def __init__(self, client, config=None):
        """
        Initialize content generator.
        
        Args:
            client: LLM client instance
            config: Optional configuration object
        """
        self.client = client
        self.config = config


class BaseTitleGenerator(BaseContentGenerator):
    """
    Abstract base class for title generation.
    
    Handles conversation title generation using LLM APIs.
    Generates concise, descriptive titles based on the first exchange
    in a conversation to help users identify and organize their chats.
    """
    
    @staticmethod
    @abstractmethod
    def generate_title_from_messages(
        client,  # LLM client instance
        latest_messages: List[BaseMessage]
    ) -> Optional[str]:
        """
        Generate a concise conversation title based on recent messages.
        
        Args:
            client: LLM client instance for API calls
            latest_messages: Recent conversation messages to generate title from
            
        Returns:
            Generated title string, or None if generation fails
        """
        pass


class BaseWebSearchGenerator(BaseContentGenerator):
    """
    Abstract base class for web search generation.
    
    Handles web search using LLM APIs with appropriate search tools.
    Performs web searches and returns structured results with proper error
    handling and debugging support.
    """
    
    @staticmethod
    @abstractmethod
    def perform_web_search(
        client,  # LLM client instance
        query: str,
        debug: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Perform a web search using the LLM's web search capabilities.
        
        Args:
            client: LLM client instance for API calls
            query: The search query to find information on the web
            debug: Enable debug output
            **kwargs: Additional search parameters (max_uses, etc.)
            
        Returns:
            Dictionary containing search results or error information
        """
        pass


class BaseImagePromptGenerator(BaseContentGenerator):
    """
    Abstract base class for image prompt generation.
    
    Handles text-to-image prompt generation using LLM APIs.
    Creates detailed and effective prompts for image generation based on
    recent conversation context, with support for positive and negative prompts.
    """
    
    @staticmethod
    @abstractmethod
    def generate_text_to_image_prompt(
        client,  # LLM client instance
        session_id: Optional[str] = None,
        debug: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Generate high-quality text-to-image prompts using recent conversation context.
        
        Args:
            client: LLM client instance for API calls
            session_id: Optional session ID for conversation context
            debug: Enable debug output
            
        Returns:
            Dictionary with 'text_prompt' and 'negative_prompt' keys, or None if failed
        """
        pass