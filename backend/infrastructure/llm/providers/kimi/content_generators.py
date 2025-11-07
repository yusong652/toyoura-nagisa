"""
Content generation utilities for Kimi (Moonshot) API.

Specialized generators for web search, title generation, and image prompt generation
using Kimi's Chat Completions API.
"""

from typing import Dict, Any, List, Optional, cast
import asyncio
import json
from openai import OpenAI
from openai.types.chat import ChatCompletion
from backend.domain.models.messages import BaseMessage
from backend.infrastructure.llm.base.content_generators.web_search import BaseWebSearchGenerator
from backend.infrastructure.llm.base.content_generators.title import BaseTitleGenerator
from backend.infrastructure.llm.base.content_generators.image_prompt import BaseImagePromptGenerator
from backend.infrastructure.llm.shared.constants import (
    DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT,
    DEFAULT_TITLE_GENERATION_TEMPERATURE,
    DEFAULT_TITLE_MAX_LENGTH,
    DEFAULT_WEB_SEARCH_SYSTEM_PROMPT
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
                    "role": "system",
                    "content": DEFAULT_WEB_SEARCH_SYSTEM_PROMPT
                },
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

            # Call Kimi API with web search tool - handle tool_calls loop
            # Kimi's web search requires a two-step process:
            # 1. First call returns tool_calls with search request
            # 2. Return tool results, second call generates final response
            finish_reason = None
            choice = None
            search_content_total_tokens = 0
            iteration = 0

            while finish_reason is None or finish_reason == "tool_calls":
                iteration += 1
                if debug:
                    print(f"[KimiWebSearch] API call iteration {iteration}")
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

                if not response.choices:
                    if debug:
                        print("[KimiWebSearch] No response choices found")
                    return BaseWebSearchGenerator.format_search_error(query, "No search results found")

                choice = response.choices[0]
                finish_reason = choice.finish_reason

                if debug:
                    print(f"[KimiWebSearch] Finish reason: {finish_reason}")
                    current_content = choice.message.content or ""
                    print(f"[KimiWebSearch] Current message content length: {len(current_content)}")
                    if current_content:
                        print(f"[KimiWebSearch] Content preview: {current_content[:200]}...")

                # Handle tool calls
                if finish_reason == "tool_calls" and choice.message.tool_calls:
                    # Add assistant message with tool calls to history
                    messages.append(choice.message.model_dump())

                    if debug:
                        print(f"[KimiWebSearch] Processing {len(choice.message.tool_calls)} tool calls")

                    # Process each tool call
                    for tool_call in choice.message.tool_calls:
                        # Access function attributes safely for type checking
                        function = getattr(tool_call, 'function', None)
                        if not function:
                            continue

                        tool_call_name = getattr(function, 'name', '')
                        tool_call_arguments_str = getattr(function, 'arguments', '{}')
                        tool_call_arguments = json.loads(tool_call_arguments_str)

                        if debug:
                            print(f"[KimiWebSearch] Tool call: {tool_call_name}")

                        if tool_call_name == "$web_search":
                            # Extract search content token usage
                            usage_info = tool_call_arguments.get("usage", {})
                            search_content_total_tokens = usage_info.get("total_tokens", 0)

                            if debug:
                                print(f"[KimiWebSearch] Search content tokens: {search_content_total_tokens}")
                                print(f"[KimiWebSearch] Tool call arguments keys: {list(tool_call_arguments.keys())}")

                            # For Kimi, we just return the arguments as-is
                            tool_result = tool_call_arguments
                        else:
                            tool_result = {"error": f"Unknown tool: {tool_call_name}"}

                        # Add tool result to messages
                        tool_call_id = getattr(tool_call, 'id', '')
                        tool_result_content = json.dumps(tool_result, ensure_ascii=False)

                        if debug:
                            print(f"[KimiWebSearch] Tool result content length: {len(tool_result_content)}")
                            print(f"[KimiWebSearch] Tool result preview: {tool_result_content[:300]}...")

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "name": tool_call_name,
                            "content": tool_result_content,
                        })

                        if debug:
                            print(f"[KimiWebSearch] Total messages in history: {len(messages)}")

            # Use base class debug method
            BaseWebSearchGenerator.debug_search_complete(debug)

            if not choice:
                return BaseWebSearchGenerator.format_search_error(query, "No valid response")

            # Verify we got a complete response
            if finish_reason != "stop":
                if debug:
                    print(f"[KimiWebSearch] WARNING: Expected finish_reason='stop', got '{finish_reason}'")

            # Extract final response content
            response_text = choice.message.content or ""

            if debug:
                print(f"[KimiWebSearch] Loop completed after {iteration} iterations")
                print(f"[KimiWebSearch] Final finish_reason: {finish_reason}")
                print(f"[KimiWebSearch] Final response text length: {len(response_text)}")
                print(f"[KimiWebSearch] Final response text: {response_text}")
                print(f"[KimiWebSearch] Search tokens used: {search_content_total_tokens}")

            # Kimi integrates search results directly into the response
            sources: List[Dict[str, Any]] = []
            # Always add a source if we got a valid response after tool calls
            if response_text and iteration > 1:  # iteration > 1 means tool was called
                source_info = {
                    "title": "Kimi Web Search",
                    "url": "",
                    "snippet": "Search results integrated into response"
                }
                if search_content_total_tokens > 0:
                    source_info["snippet"] = f"Search results integrated (tokens: {search_content_total_tokens})"
                sources.append(source_info)

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

            # Get Kimi configuration
            llm_settings = get_llm_settings()
            kimi_config = llm_settings.get_kimi_config()

            # Use non-thinking model for title generation (fast and concise)
            title_model = "kimi-k2-0905-preview"

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

            # Call Kimi API using Chat Completions format
            # Use asyncio.to_thread to avoid blocking the event loop
            response: ChatCompletion = await asyncio.to_thread(
                client.chat.completions.create,
                model=title_model,  # Use non-thinking model for fast title generation
                messages=cast(Any, chat_messages),
                temperature=DEFAULT_TITLE_GENERATION_TEMPERATURE,
                max_tokens=100  # Sufficient for title generation with non-thinking model
            )

            if not response.choices:
                return None

            title_response_text = response.choices[0].message.content or ""

            # Parse title using shared utility function
            return parse_title_response(title_response_text, max_length=DEFAULT_TITLE_MAX_LENGTH)

        except Exception as e:

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
                    # Extract text from content blocks (skip thinking blocks for prompt generation)
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict):
                            block_type = block.get('type')
                            if block_type == 'text':
                                text_parts.append(block.get('text', ''))
                            # Skip thinking blocks - they contain reasoning, not conversation content
                            # elif block_type == 'thinking':
                            #     pass  # Intentionally skip thinking content
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
