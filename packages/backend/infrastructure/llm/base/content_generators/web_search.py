"""
Base web search generator for performing web searches using LLM APIs.

Handles web search with proper error handling and debugging support.
"""

from abc import abstractmethod
from typing import Optional, Dict, Any, List, Awaitable
from backend.domain.models.messages import UserMessage
from .base import BaseContentGenerator


class BaseWebSearchGenerator(BaseContentGenerator):
    """
    Abstract base class for web search generation.

    Handles web search using LLM APIs with appropriate search tools.
    Performs web searches and returns structured results with proper error
    handling and debugging support.
    """

    @staticmethod
    @abstractmethod
    async def perform_web_search(
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
    
    @staticmethod
    def create_search_user_message(query: str) -> UserMessage:
        """
        Create a user message for web search query.
        
        Args:
            query: The search query
            
        Returns:
            UserMessage object containing the query
        """
        return UserMessage(role="user", content=query)
    
    @staticmethod
    def format_search_result(
        query: str,
        response_text: str,
        sources: List[Dict[str, Any]],
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Format web search results into standardized structure.
        
        Args:
            query: Original search query
            response_text: Synthesized response text
            sources: List of source dictionaries
            error: Optional error message
            
        Returns:
            Standardized search result dictionary
        """
        return {
            "query": query,
            "response_text": response_text,
            "sources": sources,
            "total_sources": len(sources),
            "error": error
        }
    
    @staticmethod
    def format_search_error(query: str, error_message: str) -> Dict[str, Any]:
        """
        Format search error into standardized response.
        
        Args:
            query: Original search query
            error_message: Error description
            
        Returns:
            Standardized error response
        """
        return BaseWebSearchGenerator.format_search_result(
            query=query,
            response_text="",
            sources=[],
            error=error_message
        )
    
    @staticmethod
    def debug_search_start(query: str, debug: bool):
        """
        Print debug message for search start.
        
        Args:
            query: Search query
            debug: Whether debug is enabled
        """
        if debug:
            print(f"[WebSearch] Performing search for query: {query}")
    
    @staticmethod
    def debug_search_complete(debug: bool):
        """
        Print debug message for search completion.
        
        Args:
            debug: Whether debug is enabled
        """
        if debug:
            print(f"[WebSearch] API call completed")
    
    @staticmethod
    def debug_search_results(sources_count: int, response_length: int, debug: bool):
        """
        Print debug message for search results.
        
        Args:
            sources_count: Number of sources found
            response_length: Length of response text
            debug: Whether debug is enabled
        """
        if debug:
            print(f"[WebSearch] Extracted {sources_count} sources")
            print(f"[WebSearch] Response text length: {response_length}")