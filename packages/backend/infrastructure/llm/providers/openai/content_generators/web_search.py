"""
OpenAI-specific web search generator.

Performs web searches using OpenAI's native web search capabilities.
"""

from typing import Dict, Any, List

from openai.types.responses import Response, ResponseOutputMessage
from openai.types.responses.response_output_text import ResponseOutputText, AnnotationURLCitation

from backend.infrastructure.llm.base.content_generators.web_search import BaseWebSearchGenerator
from backend.infrastructure.llm.shared.constants import DEFAULT_WEB_SEARCH_SYSTEM_PROMPT
from backend.infrastructure.llm.providers.openai.message_formatter import OpenAIMessageFormatter
from backend.infrastructure.llm.providers.openai.debug import OpenAIDebugger


class OpenAIWebSearchGenerator(BaseWebSearchGenerator):
    """
    OpenAI-specific web search using native web search capabilities.

    Uses the gpt-5 model with web_search tool to perform searches
    and return structured results with sources.
    """

    async def perform_web_search(
        self,
        query: str,
        debug: bool = False,
        **kwargs  # Accept additional parameters for compatibility (e.g., max_uses)
    ) -> Dict[str, Any]:
        """
        Perform a web search using OpenAI's native web search API.

        Args:
            query: The search query to find information on the web
            debug: Enable debug output
            **kwargs: Additional search parameters (accepted for compatibility but not used)

        Returns:
            Dictionary containing search results with sources and metadata
        """
        if kwargs:
            print(f"[WebSearchGenerator] Additional params (ignored): {kwargs}")

        try:
            # Use base class debug method
            BaseWebSearchGenerator.debug_search_start(query, debug)

            # Create user message using base class method
            user_message = BaseWebSearchGenerator.create_search_user_message(query)

            # Format message to Responses API input
            input_items = OpenAIMessageFormatter.format_messages([user_message])

            # Prepare API kwargs for web search (Responses API)
            api_kwargs = {
                "model": "gpt-5",  # GPT-5 supports web_search tool in Responses API
                "instructions": DEFAULT_WEB_SEARCH_SYSTEM_PROMPT,
                "input": input_items,
                "max_output_tokens": 2048,
                "tools": [{"type": "web_search"}],
                "metadata": {"generator": "web_search"}
            }

            if debug:
                OpenAIDebugger.print_debug_request_payload(api_kwargs)

            # Perform the web search using async API
            response: Response = await self.client.responses.create(**api_kwargs)

            if debug:
                OpenAIDebugger.log_raw_response(response)

            # Use base class debug method
            BaseWebSearchGenerator.debug_search_complete(debug)

            if not response.output:
                if debug:
                    print("[WebSearch] No response content found")
                return BaseWebSearchGenerator.format_search_error(query, "No search results found")

            response_text = ""
            sources: List[Dict[str, Any]] = []

            for item in response.output:
                if not isinstance(item, ResponseOutputMessage):
                    continue

                for part in item.content:
                    if not isinstance(part, ResponseOutputText):
                        continue

                    text_segment = part.text or ""
                    response_text += text_segment

                    for annotation in part.annotations or []:
                        if isinstance(annotation, AnnotationURLCitation):
                            snippet = text_segment[
                                annotation.start_index:annotation.end_index
                            ]
                            sources.append({
                                "title": getattr(annotation, "title", ""),
                                "url": getattr(annotation, "url", ""),
                                "snippet": snippet
                            })
                            print(f"[WebSearchGenerator] Added source: {annotation.url}")

            if not sources:
                print("[WebSearchGenerator] No URL citations returned; using response text only")

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
            error_msg = f"An error occurred during web search: {str(e)}"
            print(f"[WebSearchGenerator] ERROR: {error_msg}")
            import traceback
            print(f"[WebSearchGenerator] Traceback: {traceback.format_exc()}")
            if debug:
                print(f"[WebSearch] Error: {error_msg}")
            return BaseWebSearchGenerator.format_search_error(query, error_msg)
