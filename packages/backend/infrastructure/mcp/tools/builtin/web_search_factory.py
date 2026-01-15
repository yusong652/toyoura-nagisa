"""Web Search Tool Factory for Multi-LLM Support."""

from typing import Dict, Any, Optional, Union, cast, Awaitable
import asyncio
from backend.config import get_llm_settings
from backend.infrastructure.llm.base.client import LLMClientBase


class WebSearchToolFactory:
    """Factory class to handle web search across different LLM providers."""
    
    @staticmethod
    def get_web_search_generator(llm_type: str):
        """
        Get the appropriate web search generator based on LLM type.

        Args:
            llm_type: Type of LLM client ('google', 'anthropic', 'openai', 'moonshot', or 'zhipu')

        Returns:
            WebSearchGenerator class for the specified LLM type
        """
        if llm_type.lower() == 'google':
            from backend.infrastructure.llm.providers.google.content_generators import GoogleWebSearchGenerator as WebSearchGenerator
            return WebSearchGenerator
        elif llm_type.lower() == 'anthropic':
            from backend.infrastructure.llm.providers.anthropic.content_generators import AnthropicWebSearchGenerator as WebSearchGenerator
            return WebSearchGenerator
        elif llm_type.lower() == 'openai':
            from backend.infrastructure.llm.providers.openai.content_generators import OpenAIWebSearchGenerator
            return OpenAIWebSearchGenerator
        elif llm_type.lower() == 'moonshot':
            from backend.infrastructure.llm.providers.moonshot.content_generators import MoonshotWebSearchGenerator as WebSearchGenerator
            return WebSearchGenerator
        elif llm_type.lower() == 'zhipu':
            from backend.infrastructure.llm.providers.zhipu.content_generators import ZhipuWebSearchGenerator
            return ZhipuWebSearchGenerator
        else:
            raise ValueError(f"Unsupported LLM type: {llm_type}")
    
    @staticmethod
    async def perform_web_search(
        llm_client: LLMClientBase,
        llm_type: str,
        query: str,
        debug: bool = False,
        max_uses: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Perform web search using appropriate LLM client.
        
        Args:
            llm_client: The LLM client instance
            llm_type: Type of LLM ('google' or 'anthropic')
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
                if llm_type.lower() == 'google':
                    google_config = llm_settings.get_google_config()
                    max_uses = google_config.web_search_max_uses
                elif llm_type.lower() == 'anthropic':
                    anthropic_config = llm_settings.get_anthropic_config()
                    max_uses = anthropic_config.web_search_max_uses
                elif llm_type.lower() == 'openai':
                    # OpenAI doesn't use max_uses but we keep it for compatibility
                    max_uses = 5
                elif llm_type.lower() == 'moonshot':
                    # Moonshot uses built-in $web_search tool, max_uses not applicable
                    max_uses = 1
                elif llm_type.lower() == 'zhipu':
                    # Zhipu uses built-in web_search tool, max_uses not applicable
                    max_uses = 1
                else:
                    max_uses = 5
            
            # Get debug setting from configuration if not explicitly set
            if not debug:
                debug = llm_settings.debug
            
            # Perform the search with appropriate parameters
            # Extract the async client for providers that support it (Moonshot, OpenAI)
            # Fallback to 'client' for providers that don't have separate async/sync clients
            client = getattr(llm_client, 'async_client', None) or getattr(llm_client, 'client', llm_client)

            # Instantiate the generator with the client
            generator = WebSearchGenerator(client=client)

            if llm_type.lower() in ('google', 'anthropic', 'openai', 'moonshot', 'zhipu'):
                # All providers now use instance method (async)
                return await generator.perform_web_search(
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
            LLM type string ('google', 'anthropic', 'openai', 'moonshot', or 'zhipu')
        """
        client_type = type(llm_client).__name__.lower()
        client_module = type(llm_client).__module__.lower()

        # Check specific providers FIRST (Moonshot, OpenRouter, Zhipu) before OpenAI
        # (since they use OpenAI-compatible API)
        if 'moonshot' in client_type or 'moonshot' in client_module:
            return 'moonshot'
        elif 'openrouter' in client_type or 'openrouter' in client_module:
            return 'openrouter'
        elif 'zhipu' in client_type or 'zhipu' in client_module:
            return 'zhipu'
        elif 'google' in client_type or 'google' in client_module:
            return 'google'
        elif 'anthropic' in client_type or 'anthropic' in client_module:
            return 'anthropic'
        elif 'openai' in client_type or 'openai' in client_module:
            return 'openai'
        elif hasattr(llm_client, 'client'):
            # Try to detect from wrapped client
            return WebSearchToolFactory.detect_llm_type(llm_client.client)
        else:
            # Fallback: check for specific attributes
            if hasattr(llm_client, 'models') and hasattr(llm_client, 'generate_content'):
                return 'google'
            elif hasattr(llm_client, 'messages') and hasattr(llm_client, 'create'):
                return 'anthropic'
            elif hasattr(llm_client, 'chat') and hasattr(llm_client.chat, 'completions'):
                return 'openai'
            else:
                raise ValueError(f"Unable to detect LLM type from client: {type(llm_client)}")