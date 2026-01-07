"""
Gemini-specific web search generator.

Performs web searches using Google Search via the Gemini API.
"""

from typing import Dict, Any
from google.genai import types

from backend.config import get_llm_settings
from backend.infrastructure.llm.base.content_generators.web_search import BaseWebSearchGenerator
from backend.infrastructure.llm.shared.constants.prompts import DEFAULT_WEB_SEARCH_SYSTEM_PROMPT
from backend.infrastructure.llm.providers.gemini.config import get_gemini_client_config
from backend.infrastructure.llm.providers.gemini.debug import GeminiDebugger
from backend.infrastructure.llm.providers.gemini.message_formatter import GeminiMessageFormatter
from backend.infrastructure.llm.providers.gemini.response_processor import GeminiResponseProcessor


class GeminiWebSearchGenerator(BaseWebSearchGenerator):
    """
    Gemini-specific web search using shared logic and Gemini's google_search tool.
    """

    async def perform_web_search(
        self,
        query: str,
        debug: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Perform a web search using Google Search via the Gemini API.

        Uses Gemini's modern google_search tool with shared result processing.
        """
        try:
            # Extract max_uses from kwargs with default value
            max_uses = kwargs.get('max_uses', 5)

            # Use base class debug method
            BaseWebSearchGenerator.debug_search_start(query, debug)

            # Create user message using base class method
            user_message = BaseWebSearchGenerator.create_search_user_message(query)

            # Get unified configuration
            gemini_client_config = get_gemini_client_config()
            llm_settings = get_llm_settings()
            gemini_llm_config = llm_settings.get_gemini_config()
            model = gemini_llm_config.model

            # Web search uses a simpler config:
            # - No thinking config (google_search tool is a simple retrieval, not reasoning)
            # - No max_output_tokens limit (let model decide based on search results)
            # - Include safety settings for content filtering
            search_config = types.GenerateContentConfig(
                system_instruction=DEFAULT_WEB_SEARCH_SYSTEM_PROMPT,
                tools=[types.Tool(google_search=types.GoogleSearch())],
                safety_settings=gemini_client_config.safety_settings.to_gemini_format(),
            )

            # Format message using MessageFormatter
            contents = GeminiMessageFormatter.format_messages([user_message])

            if debug:
                GeminiDebugger.print_request(contents, search_config, model)
                print(f"[WebSearch] Note: max_uses={max_uses} parameter ignored for Gemini (API limitation)")

            # Call the model with the query (async version)
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=search_config
            )

            # Use base class debug method
            BaseWebSearchGenerator.debug_search_complete(debug)
            if debug:
                GeminiDebugger.print_response(response)

            # Check for candidates
            if response.candidates:
                # Extract sources using ResponseProcessor
                sources = GeminiResponseProcessor.extract_web_search_sources(response, debug=debug)

                # Extract response text using ResponseProcessor
                response_text = GeminiResponseProcessor.extract_text_content(response)

                # Build structured result using base class method
                result = BaseWebSearchGenerator.format_search_result(
                    query=query,
                    response_text=response_text,
                    sources=sources
                )

                # Use base class debug method
                BaseWebSearchGenerator.debug_search_results(
                    len(sources), len(response_text), debug
                )

                return result
            else:
                if debug:
                    print("[WebSearch] No candidates found in response")
                return BaseWebSearchGenerator.format_search_error(
                    query, "No search results found"
                )

        except Exception as e:
            import traceback
            error_msg = f"An error occurred during web search: {str(e)}"
            print(f"[WebSearch] Error: {error_msg}")
            print(f"[WebSearch] Traceback:\n{traceback.format_exc()}")
            return BaseWebSearchGenerator.format_search_error(query, error_msg)
