"""
Zhipu-specific web search generator.

Performs web searches using Zhipu's built-in web_search tool.
"""

from typing import Dict, Any, List, cast
import asyncio

from zai.types.chat import Completion

from backend.config import get_llm_settings
from backend.infrastructure.llm.base.content_generators.web_search import BaseWebSearchGenerator
from backend.infrastructure.llm.shared.constants import DEFAULT_WEB_SEARCH_SYSTEM_PROMPT


class ZhipuWebSearchGenerator(BaseWebSearchGenerator):
    """
    Zhipu-specific web search using the built-in web_search tool.

    Zhipu provides a native web search capability through the web_search
    tool, which is called via the Chat Completions API with search parameters
    specified directly in the tools configuration.
    """

    async def perform_web_search(
        self,
        query: str,
        debug: bool = False,
        **kwargs  # Accept additional parameters for compatibility (e.g., max_uses)
    ) -> Dict[str, Any]:
        """
        Perform a web search using Zhipu's built-in web_search tool.

        Args:
            query: The search query to find information on the web
            debug: Enable debug output
            **kwargs: Additional search parameters (accepted for compatibility)

        Returns:
            Dictionary containing search results with sources and metadata
        """

        try:
            # Use base class debug method
            BaseWebSearchGenerator.debug_search_start(query, debug)

            # Get Zhipu configuration for model
            llm_settings = get_llm_settings()
            zhipu_config = llm_settings.get_zhipu_config()
            model = zhipu_config.model

            # Prepare messages for web search
            messages = [
                {
                    "role": "system",
                    "content": DEFAULT_WEB_SEARCH_SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": query
                }
            ]

            # Define Zhipu's web_search tool with inline parameters
            # According to documentation, search_query and search_result are specified directly
            tools = [
                {
                    "type": "web_search",
                    "web_search": {
                        "search_query": query,  # Pass the query directly
                        "search_result": True,  # Request search results
                    }
                }
            ]

            # Call Zhipu API with web search tool
            # Wrap synchronous call with asyncio.to_thread
            response: Completion = cast(
                Completion,
                await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model=model,
                    messages=messages,
                    tools=tools,
                    temperature=zhipu_config.temperature,
                    max_tokens=8000,  # Increased for comprehensive web search results
                    stream=False
                )
            )

            # Use base class debug method
            BaseWebSearchGenerator.debug_search_complete(debug)

            if not response.choices:
                if debug:
                    print("[ZhipuWebSearch] No response choices found")
                return BaseWebSearchGenerator.format_search_error(query, "No search results found")

            choice = response.choices[0]
            finish_reason = choice.finish_reason

            # Extract response content
            response_text = choice.message.content or ""

            # Handle token length limit
            if finish_reason == "length":
                warning_msg = " (Note: Response was truncated due to length limit. Consider breaking down your query.)"
                if debug:
                    print(f"[ZhipuWebSearch] WARNING: Response truncated due to length limit")
            else:
                warning_msg = ""

            # Zhipu integrates search results directly into the response
            # Always create a source entry to indicate web search was executed
            sources: List[Dict[str, Any]] = []

            # Determine source snippet based on response
            if response_text:
                snippet = "Search results integrated into response" + warning_msg
            elif finish_reason == "length":
                snippet = "Search executed but response was truncated due to length limit"
            else:
                snippet = "Search executed but no results returned"

            source_info = {
                "title": "Zhipu Web Search",
                "url": "",
                "snippet": snippet
            }
            sources.append(source_info)

            # Format result using base class method
            result = BaseWebSearchGenerator.format_search_result(
                query=query,
                response_text=response_text,
                sources=sources
            )

            BaseWebSearchGenerator.debug_search_results(
                len(sources), len(response_text), debug
            )

            return result

        except Exception as e:
            error_msg = f"Zhipu web search failed: {str(e)}"
            if debug:
                print(f"[ZhipuWebSearch] ERROR: {error_msg}")
                import traceback
                print(f"[ZhipuWebSearch] Traceback: {traceback.format_exc()}")
            return BaseWebSearchGenerator.format_search_error(query, error_msg)
