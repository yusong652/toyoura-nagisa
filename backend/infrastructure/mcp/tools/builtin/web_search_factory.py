"""Web Search Tool Factory for Multi-LLM Support."""

from typing import Dict, Any, Optional
from backend.config import get_llm_settings


class WebSearchToolFactory:
    """Factory class to handle web search across different LLM providers."""
    
    @staticmethod
    def get_web_search_generator(llm_type: str):
        """
        Get the appropriate web search generator based on LLM type.
        
        Args:
            llm_type: Type of LLM client ('gemini' or 'anthropic')
            
        Returns:
            WebSearchGenerator class for the specified LLM type
        """
        if llm_type.lower() == 'gemini':
            from backend.infrastructure.llm.providers.gemini.content_generators import GeminiWebSearchGenerator as WebSearchGenerator
            return WebSearchGenerator
        elif llm_type.lower() == 'anthropic':
            from backend.infrastructure.llm.anthropic.content_generators import WebSearchGenerator
            return WebSearchGenerator
        else:
            raise ValueError(f"Unsupported LLM type: {llm_type}")
    
    @staticmethod
    def perform_web_search(
        llm_client,
        llm_type: str,
        query: str,
        debug: bool = False,
        max_uses: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Perform web search using appropriate LLM client.
        
        Args:
            llm_client: The LLM client instance
            llm_type: Type of LLM ('gemini' or 'anthropic')
            query: Search query
            debug: Enable debug output
            max_uses: Maximum number of search uses (ignored for Gemini)
            
        Returns:
            Dictionary containing search results
        """
        try:
            # Get the appropriate web search generator
            WebSearchGenerator = WebSearchToolFactory.get_web_search_generator(llm_type)
            
            # Get LLM-specific configuration
            llm_settings = get_llm_settings()
            
            # Use configured max_uses if not provided
            if max_uses is None:
                if llm_type.lower() == 'gemini':
                    gemini_config = llm_settings.get_gemini_config()
                    max_uses = gemini_config.web_search_max_uses
                elif llm_type.lower() == 'anthropic':
                    anthropic_config = llm_settings.get_anthropic_config()
                    max_uses = anthropic_config.web_search_max_uses
                else:
                    max_uses = 5
            
            # Get debug setting from configuration if not explicitly set
            if not debug:
                debug = llm_settings.debug
            
            # Perform the search with appropriate parameters
            if llm_type.lower() == 'gemini':
                # Gemini client expects the raw client
                client = getattr(llm_client, 'client', llm_client)
                return WebSearchGenerator.perform_web_search(
                    client=client,
                    query=query,
                    debug=debug,
                    max_uses=max_uses  # Will be ignored but accepted for API compatibility
                )
            elif llm_type.lower() == 'anthropic':
                # Anthropic client can be passed directly
                client = getattr(llm_client, 'client', llm_client)
                return WebSearchGenerator.perform_web_search(
                    client=client,
                    query=query,
                    debug=debug,
                    max_uses=max_uses
                )
            else:
                return {
                    "error": f"Unsupported LLM type: {llm_type}",
                    "query": query
                }
                
        except Exception as e:
            return {
                "error": f"Web search factory error: {str(e)}",
                "query": query,
                "llm_type": llm_type
            }

    @staticmethod
    def detect_llm_type(llm_client) -> str:
        """
        Auto-detect LLM type from client instance.
        
        Args:
            llm_client: The LLM client instance
            
        Returns:
            LLM type string ('gemini' or 'anthropic')
        """
        client_type = type(llm_client).__name__.lower()
        client_module = type(llm_client).__module__.lower()
        
        if 'gemini' in client_type or 'gemini' in client_module:
            return 'gemini'
        elif 'anthropic' in client_type or 'anthropic' in client_module:
            return 'anthropic'
        elif hasattr(llm_client, 'client'):
            # Try to detect from wrapped client
            return WebSearchToolFactory.detect_llm_type(llm_client.client)
        else:
            # Fallback: check for specific attributes
            if hasattr(llm_client, 'models') and hasattr(llm_client, 'generate_content'):
                return 'gemini'
            elif hasattr(llm_client, 'messages') and hasattr(llm_client, 'create'):
                return 'anthropic'
            else:
                raise ValueError(f"Unable to detect LLM type from client: {type(llm_client)}")