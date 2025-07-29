"""
Shared web search generator implementation.

Common web search logic that can be adapted for different LLM providers.
"""

from typing import Dict, Any
from backend.domain.models.messages import UserMessage

from ...base.content_generators import BaseWebSearchGenerator
from ..constants.prompts import DEFAULT_WEB_SEARCH_SYSTEM_PROMPT
from ..constants.defaults import DEFAULT_WEB_SEARCH_TEMPERATURE


class SharedWebSearchGenerator(BaseWebSearchGenerator):
    """
    Shared implementation of web search generation.
    
    Provides common logic for web search that can be adapted by different LLM providers.
    Each provider needs to implement the actual API call with search tools.
    """
    
    @staticmethod
    def prepare_search_context(
        query: str,
        system_prompt: str = DEFAULT_WEB_SEARCH_SYSTEM_PROMPT,
        temperature: float = DEFAULT_WEB_SEARCH_TEMPERATURE,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Prepare context data for web search.
        
        Args:
            query: The search query
            system_prompt: System prompt for search behavior
            temperature: Temperature setting for search
            **kwargs: Additional search parameters
            
        Returns:
            Dictionary containing prepared search context
        """
        return {
            'query': query,
            'system_prompt': system_prompt,
            'temperature': temperature,
            'user_message': UserMessage(role="user", content=query),
            **kwargs
        }
    
    @staticmethod
    def process_search_response(
        response,
        query: str,
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        Process web search response into standardized format.
        
        Args:
            response: Raw LLM API response
            query: Original search query
            debug: Enable debug output
            
        Returns:
            Dictionary containing standardized search results
        """
        # This is a base implementation - providers should override with specific logic
        if debug:
            print(f"[WebSearch] Processing search response for query: {query}")
        
        # Default structure - providers should extract actual sources and content
        return {
            "query": query,
            "response_text": str(response) if response else "",
            "sources": [],
            "total_sources": 0,
            "error": None
        }
    
    @staticmethod
    def extract_sources_from_response(response, debug: bool = False) -> list:
        """
        Extract source information from search response.
        
        Args:
            response: Raw LLM API response
            debug: Enable debug output
            
        Returns:
            List of source dictionaries
        """
        # Base implementation - providers should override
        if debug:
            print("[WebSearch] Extracting sources from response")
        
        return []
    
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
        return {
            "query": query,
            "response_text": "",
            "sources": [],
            "total_sources": 0,
            "error": error_message
        }