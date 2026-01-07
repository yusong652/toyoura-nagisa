"""
Anthropic-specific web search generator.

Performs web searches using the Anthropic Claude API with web_search_20250305 tool.
"""

from typing import Dict, Any

import anthropic

from backend.domain.models.messages import UserMessage
from backend.infrastructure.llm.base.content_generators.web_search import BaseWebSearchGenerator
from backend.infrastructure.llm.shared.constants import DEFAULT_WEB_SEARCH_SYSTEM_PROMPT
from backend.infrastructure.llm.providers.anthropic.config import get_anthropic_client_config
from backend.infrastructure.llm.providers.anthropic.message_formatter import MessageFormatter


class AnthropicWebSearchGenerator(BaseWebSearchGenerator):
    """
    Anthropic-specific web search using the web_search_20250305 tool.

    Performs web searches using the native web search capability via the Anthropic API.
    Returns structured results with proper error handling and debugging support.
    """

    @staticmethod
    async def perform_web_search(
        client: anthropic.AsyncAnthropic,
        query: str,
        debug: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Perform a web search using the native web search tool via Anthropic API.

        Uses the web_search_20250305 tool. The model will automatically
        decide whether to perform a search based on the query requirements.

        Args:
            client: Anthropic Claude client instance
            query: The search query to find information on the web
            debug: Enable debug output
            **kwargs: Additional search parameters:
                - max_uses: Maximum number of search tool uses (default: 5)

        Returns:
            Dictionary containing search results or error information
        """
        max_uses = kwargs.get('max_uses', 5)
        try:
            # Create user message with search query
            user_message = UserMessage(role="user", content=query)

            # Format message using MessageFormatter
            formatted_messages = MessageFormatter.format_messages([user_message])

            # Use shared web search system prompt for consistency
            web_search_system_prompt = DEFAULT_WEB_SEARCH_SYSTEM_PROMPT

            # Use the new Anthropic configuration system
            anthropic_config = get_anthropic_client_config()

            # Build API call parameters using the configuration system
            api_kwargs = anthropic_config.get_api_call_kwargs(
                system_prompt=web_search_system_prompt,
                messages=formatted_messages,
                tools=[{
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": max_uses
                }]
            )

            # Override some parameters specific to web search
            api_kwargs.update({
                "max_tokens": 4096,
                "temperature": 1.0
            })
            # Update thinking budget if thinking is enabled
            if "thinking" in api_kwargs:
                api_kwargs["thinking"]["budget_tokens"] = 2048

            # Call the API with web search tool (async version)
            response = await client.messages.create(**api_kwargs)

            # Extract response text and tool usage information
            response_text = ""
            tool_calls = []
            sources = []

            if response.content:
                for content_block in response.content:
                    if hasattr(content_block, 'text'):
                        response_text += content_block.text
                    elif hasattr(content_block, 'type') and content_block.type == 'tool_use':
                        # Track tool calls for debugging
                        tool_calls.append({
                            'tool_name': getattr(content_block, 'name', 'unknown'),
                            'tool_id': getattr(content_block, 'id', 'unknown'),
                            'input': getattr(content_block, 'input', {})
                        })


            # Note: Unlike Gemini, Anthropic's web_search_20250305 tool doesn't expose
            # individual source URLs in the response structure. The search results
            # are synthesized into the response text directly.

            # Build structured result
            result = {
                "query": query,
                "response_text": response_text,
                "sources": sources,  # Empty for Anthropic as sources aren't exposed
                "total_sources": len(sources),
                "tool_calls": tool_calls,
                "note": "Anthropic web search synthesizes results directly into response text"
            }

            return result

        except Exception as e:
            error_msg = f"An error occurred during web search: {str(e)}"
            if debug:
                print(f"[WebSearch] Error: {error_msg}")
            return {"error": error_msg, "query": query}
