"""
Content generation utilities for Kimi (Moonshot) API.

Specialized generators for web search, title generation, and image prompt generation
using Kimi's Chat Completions API.
"""

from typing import Dict, Any, List, Optional, cast
import asyncio
from openai import OpenAI
from openai.types.chat import ChatCompletion
from backend.domain.models.messages import BaseMessage
from backend.infrastructure.llm.base.content_generators.web_search import BaseWebSearchGenerator
from backend.infrastructure.llm.base.content_generators.title import BaseTitleGenerator
from backend.infrastructure.llm.base.content_generators.image_prompt import BaseImagePromptGenerator
from backend.infrastructure.llm.shared.constants import (
    DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT,
    DEFAULT_TITLE_GENERATION_TEMPERATURE,
    DEFAULT_TITLE_MAX_LENGTH
)
from backend.infrastructure.llm.shared.utils.text_processing import parse_title_response
from backend.config import get_llm_settings


class KimiWebSearchGenerator(BaseWebSearchGenerator):
    """
    Handles web search using Kimi's built-in $web_search tool.

    Kimi provides a native web search capability through the $web_search
    builtin_function tool, which is called via the Chat Completions API.
    """

    @staticmethod
    async def perform_web_search(
        client: OpenAI,  # Kimi uses sync OpenAI client (via OpenRouter or direct)
        query: str,
        debug: bool = False,
        **kwargs  # Accept additional parameters for compatibility (e.g., max_uses)
    ) -> Dict[str, Any]:
        """
        Perform a web search using Kimi's built-in $web_search tool.

        Args:
            client: OpenAI client instance (Kimi client, sync)
            query: The search query to find information on the web
            debug: Enable debug output
            **kwargs: Additional search parameters (accepted for compatibility)

        Returns:
            Dictionary containing search results with sources and metadata
        """
        if debug:
            print(f"[KimiWebSearch] Starting web search with query: {query}")
            if kwargs:
                print(f"[KimiWebSearch] Additional params (accepted): {kwargs}")

        try:
            # Use base class debug method
            BaseWebSearchGenerator.debug_search_start(query, debug)

            # Get Kimi configuration for model
            llm_settings = get_llm_settings()
            kimi_config = llm_settings.get_kimi_config()
            model = kimi_config.model

            if debug:
                print(f"[KimiWebSearch] Using model: {model}")

            # Prepare messages for web search
            messages = [
                {
                    "role": "user",
                    "content": query
                }
            ]

            # Declare Kimi's builtin $web_search tool
            # Format according to official documentation
            tools = [
                {
                    "type": "builtin_function",  # Kimi-specific: use builtin_function
                    "function": {
                        "name": "$web_search",  # Built-in web search function
                    },
                }
            ]

            if debug:
                print(f"[KimiWebSearch] Messages: {messages}")
                print(f"[KimiWebSearch] Tools: {tools}")

            # Call Kimi API with web search tool
            # Use asyncio.to_thread to avoid blocking the event loop with sync API call
            response: ChatCompletion = await asyncio.to_thread(
                client.chat.completions.create,
                model=model,
                messages=cast(Any, messages),
                tools=cast(Any, tools),
                temperature=kimi_config.temperature,
            )

            if debug:
                print(f"[KimiWebSearch] API response received")
                print(f"[KimiWebSearch] Response choices: {len(response.choices)}")

            # Use base class debug method
            BaseWebSearchGenerator.debug_search_complete(debug)

            if not response.choices:
                if debug:
                    print("[KimiWebSearch] No response choices found")
                return BaseWebSearchGenerator.format_search_error(query, "No search results found")

            # Extract response content
            choice = response.choices[0]
            message = choice.message

            # Get text content from response
            response_text = message.content or ""

            if debug:
                print(f"[KimiWebSearch] Response text length: {len(response_text)}")
                print(f"[KimiWebSearch] Has tool calls: {bool(message.tool_calls)}")

            # Kimi returns web search results in the text content
            # The model has already processed the search results and incorporated them
            sources: List[Dict[str, Any]] = []

            # Check if the response mentions web search was performed
            # Kimi integrates search results directly into the response
            if response_text:
                # For now, we indicate that web search was used
                # Future enhancement: parse citations/sources if Kimi provides them
                sources.append({
                    "title": "Kimi Web Search",
                    "url": "",
                    "snippet": "Results integrated into response"
                })

            if debug:
                print(f"[KimiWebSearch] Extracted {len(sources)} sources")

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
            error_msg = f"Kimi web search failed: {str(e)}"
            if debug:
                print(f"[KimiWebSearch] ERROR: {error_msg}")
                import traceback
                print(f"[KimiWebSearch] Traceback: {traceback.format_exc()}")
            return BaseWebSearchGenerator.format_search_error(query, error_msg)


class TitleGenerator(BaseTitleGenerator):
    """
    Handles conversation title generation using Kimi Chat Completions API.

    Generates concise, descriptive titles based on the first exchange
    in a conversation to help users identify and organize their chats.
    """

    @staticmethod
    async def generate_title_from_messages(
        client: OpenAI,
        latest_messages: List[BaseMessage]
    ) -> Optional[str]:
        """
        Generate a concise conversation title based on recent messages.

        Args:
            client: Kimi OpenAI client instance (sync)
            latest_messages: Recent conversation messages to generate title from

        Returns:
            Generated title string, or None if generation fails
        """
        try:
            # Use base class validation
            if not BaseTitleGenerator.validate_messages_for_title(latest_messages):
                return None

            # Use base class method to prepare messages
            messages = BaseTitleGenerator.prepare_title_generation_messages(
                latest_messages,
                "Please generate a title for the above conversation"
            )

            # Get Kimi configuration
            llm_settings = get_llm_settings()
            kimi_config = llm_settings.get_kimi_config()

            # Build messages for Chat Completions API
            chat_messages = [
                {"role": "system", "content": DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT}
            ]

            for msg in messages:
                # Get role - all message types should have this
                role = getattr(msg, 'role', 'user')
                content = getattr(msg, 'content', '')

                # Handle content list or string
                if isinstance(content, list):
                    # Extract text from content blocks
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get('type') == 'text':
                            text_parts.append(block.get('text', ''))
                    content_str = '\n'.join(text_parts)
                else:
                    content_str = str(content)

                chat_messages.append({
                    "role": role,
                    "content": content_str
                })

            # Call Kimi API using Chat Completions format
            # Use asyncio.to_thread to avoid blocking the event loop
            response: ChatCompletion = await asyncio.to_thread(
                client.chat.completions.create,
                model=kimi_config.model,
                messages=cast(Any, chat_messages),
                temperature=DEFAULT_TITLE_GENERATION_TEMPERATURE,
                max_tokens=100
            )

            if not response.choices:
                return None

            title_response_text = response.choices[0].message.content or ""

            # Parse title using shared utility function
            return parse_title_response(title_response_text, max_length=DEFAULT_TITLE_MAX_LENGTH)

        except Exception as e:
            print(f"Kimi title generation error: {str(e)}")
            return None


class ImagePromptGenerator(BaseImagePromptGenerator):
    """
    Handles text-to-image prompt generation using Kimi Chat Completions API.

    Creates detailed and effective prompts for image generation based on
    recent conversation context.
    """

    @staticmethod
    async def generate_text_to_image_prompt(
        client: OpenAI,
        session_id: Optional[str] = None,
        debug: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Generate high-quality text-to-image prompts using recent conversation context.

        Args:
            client: Kimi OpenAI client instance (sync)
            session_id: Optional session ID for conversation context
            debug: Enable debug output

        Returns:
            Dictionary with 'text_prompt' and 'negative_prompt' keys, or None if failed
        """
        try:
            # Get Kimi configuration
            llm_settings = get_llm_settings()
            kimi_config = llm_settings.get_kimi_config()

            # Prepare generation context using inherited method
            context = ImagePromptGenerator.prepare_generation_context(
                session_id=session_id,
                llm_provider="kimi",
                llm_model=kimi_config.model
            )

            # Build messages using inherited method
            messages = ImagePromptGenerator.build_messages_for_generation(context)

            # Build chat messages for Chat Completions API
            chat_messages = [
                {"role": "system", "content": context['system_prompt']}
            ]

            for msg in messages:
                # Get role - all message types should have this
                role = getattr(msg, 'role', 'user')
                content = getattr(msg, 'content', '')

                # Handle content list or string
                if isinstance(content, list):
                    # Extract text from content blocks
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get('type') == 'text':
                            text_parts.append(block.get('text', ''))
                    content_str = '\n'.join(text_parts)
                else:
                    content_str = str(content)

                chat_messages.append({
                    "role": role,
                    "content": content_str
                })

            if debug:
                print(f"[Kimi ImagePrompt] Calling API with {len(chat_messages)} messages")

            # Call Kimi API
            # Use asyncio.to_thread to avoid blocking the event loop
            response: ChatCompletion = await asyncio.to_thread(
                client.chat.completions.create,
                model=kimi_config.model,
                messages=cast(Any, chat_messages),
                temperature=context.get('temperature', 1.0),
                max_tokens=1024
            )

            if not response.choices:
                return None

            prompt_text = response.choices[0].message.content or ""

            if not prompt_text:
                return None

            if debug:
                print(f"[Kimi ImagePrompt] Raw response: {prompt_text[:200]}...")

            # Process response using inherited method
            return ImagePromptGenerator.process_generation_response(
                prompt_text, context, session_id, debug
            )

        except Exception as e:
            if debug:
                print(f"[Kimi ImagePrompt] Error during prompt generation: {str(e)}")
            return None
