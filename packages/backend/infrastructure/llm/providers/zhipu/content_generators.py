"""
Content generation utilities for Zhipu (智谱) API.

Specialized generators for web search, title generation, and image prompt generation
using Zhipu's Chat Completions API via zai SDK.
"""

from typing import Dict, Any, List, Optional, cast
import asyncio
from zai import ZhipuAiClient
from zai.types.chat import Completion

from backend.domain.models.messages import BaseMessage
from backend.infrastructure.llm.base.content_generators.web_search import BaseWebSearchGenerator
from backend.infrastructure.llm.base.content_generators.title import BaseTitleGenerator
from backend.infrastructure.llm.base.content_generators.image_prompt import BaseImagePromptGenerator
from backend.infrastructure.llm.shared.constants import (
    DEFAULT_WEB_SEARCH_SYSTEM_PROMPT,
    DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT,
    DEFAULT_TITLE_GENERATION_TEMPERATURE,
    DEFAULT_TITLE_MAX_LENGTH,
)
from backend.infrastructure.llm.shared.utils.text_processing import parse_title_response
from backend.config import get_llm_settings


class TitleGenerator(BaseTitleGenerator):
    """
    Handles conversation title generation using Zhipu Chat Completions API.

    Generates concise, descriptive titles based on the first exchange
    in a conversation to help users identify and organize their chats.
    """

    @staticmethod
    async def generate_title_from_messages(
        client: ZhipuAiClient,  # Zhipu uses synchronous client
        latest_messages: List[BaseMessage]
    ) -> Optional[str]:
        """
        Generate a concise conversation title based on recent messages.

        Args:
            client: Zhipu ZhipuAiClient instance (synchronous)
            latest_messages: Recent conversation messages to generate title from

        Returns:
            Generated title string, or None if generation fails
        """
        try:
            # Use base class validation
            if not BaseTitleGenerator.validate_messages_for_title(latest_messages):
                return None

            # Get Zhipu configuration
            llm_settings = get_llm_settings()
            zhipu_config = llm_settings.get_zhipu_config()

            # Use non-thinking model for title generation (fast and concise)
            # GLM-4-Flash is the fastest model for simple tasks
            title_model = "glm-4.5-air"

            # Extract text content from messages
            conversation_parts = []
            for msg in latest_messages:
                role = getattr(msg, 'role', 'user')
                content = getattr(msg, 'content', '')

                # Handle content list or string
                if isinstance(content, list):
                    # Extract text from content blocks (skip thinking blocks)
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict):
                            block_type = block.get('type')
                            if block_type == 'text':
                                text_parts.append(block.get('text', ''))
                            # Skip thinking blocks for title generation
                    content_str = '\n'.join(text_parts)
                else:
                    content_str = str(content)

                # Add to conversation with role label
                role_label = "User" if role == "user" else "Assistant"
                conversation_parts.append(f"{role_label}: {content_str}")

            # Combine conversation into single context
            conversation_context = '\n'.join(conversation_parts)

            # Build chat messages with conversation as context in user message
            chat_messages = [
                {"role": "system", "content": DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT},
                {"role": "user", "content": f"Please generate a title based on the following conversation:\n\n{conversation_context}"}
            ]

            # Call Zhipu API using Chat Completions format
            # Wrap synchronous call with asyncio.to_thread
            response: Completion = cast(
                Completion,
                await asyncio.to_thread(
                    client.chat.completions.create,
                    model=title_model,
                    messages=chat_messages,
                    temperature=DEFAULT_TITLE_GENERATION_TEMPERATURE,
                    max_tokens=2048,  # Sufficient for title generation
                    stream=False
                )
            )

            if not response.choices:
                return None

            title_response_text = response.choices[0].message.content or ""

            # Parse title using shared utility function
            return parse_title_response(title_response_text, max_length=DEFAULT_TITLE_MAX_LENGTH)

        except Exception as e:
            # Silently fail for title generation (non-critical feature)
            return None


class ImagePromptGenerator(BaseImagePromptGenerator):
    """
    Handles text-to-image prompt generation using Zhipu Chat Completions API.

    Creates detailed and effective prompts for image generation based on
    recent conversation context.
    """

    @staticmethod
    async def generate_text_to_image_prompt(
        client: ZhipuAiClient,  # Zhipu uses synchronous client
        session_id: Optional[str] = None,
        debug: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Generate high-quality text-to-image prompts using recent conversation context.

        Args:
            client: Zhipu ZhipuAiClient instance (synchronous)
            session_id: Optional session ID for conversation context
            debug: Enable debug output

        Returns:
            Dictionary with 'text_prompt' and 'negative_prompt' keys, or None if failed
        """
        try:
            # Get Zhipu configuration
            llm_settings = get_llm_settings()
            zhipu_config = llm_settings.get_zhipu_config()

            # Prepare generation context using inherited method
            context = ImagePromptGenerator.prepare_generation_context(
                session_id=session_id,
                llm_provider="zhipu",
                llm_model=zhipu_config.model
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
                    # Extract text from content blocks (skip thinking blocks for prompt generation)
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict):
                            block_type = block.get('type')
                            if block_type == 'text':
                                text_parts.append(block.get('text', ''))
                            # Skip thinking blocks - they contain reasoning, not conversation content
                    content_str = '\n'.join(text_parts)
                else:
                    content_str = str(content)

                chat_messages.append({
                    "role": role,
                    "content": content_str
                })

            if debug:
                print(f"[Zhipu ImagePrompt] Calling API with {len(chat_messages)} messages")

            # Call Zhipu API (wrap synchronous call with asyncio.to_thread)
            response: Completion = cast(
                Completion,
                await asyncio.to_thread(
                    client.chat.completions.create,
                    model=zhipu_config.model,
                    messages=chat_messages,
                    temperature=context.get('temperature', 1.0),
                    max_tokens=1024,
                    stream=False
                )
            )

            if not response.choices:
                return None

            prompt_text = response.choices[0].message.content or ""

            if not prompt_text:
                return None

            if debug:
                print(f"[Zhipu ImagePrompt] Raw response: {prompt_text[:200]}...")

            # Process response using inherited method
            return ImagePromptGenerator.process_generation_response(
                prompt_text, context, session_id, debug
            )

        except Exception as e:
            if debug:
                print(f"[Zhipu ImagePrompt] Error during prompt generation: {str(e)}")
            return None


class WebSearchGenerator(BaseWebSearchGenerator):
    """
    Handles web search using Zhipu's built-in web_search tool.

    Zhipu provides a native web search capability through the web_search
    tool, which is called via the Chat Completions API with search parameters
    specified directly in the tools configuration.
    """

    @staticmethod
    async def perform_web_search(
        client: ZhipuAiClient,  # Zhipu uses synchronous client
        query: str,
        debug: bool = False,
        **kwargs  # Accept additional parameters for compatibility (e.g., max_uses)
    ) -> Dict[str, Any]:
        """
        Perform a web search using Zhipu's built-in web_search tool.

        Args:
            client: Zhipu ZhipuAiClient instance (synchronous)
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
                    client.chat.completions.create,
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
