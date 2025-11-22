"""
Content generation utilities for OpenRouter API.

Specialized generators for title generation and image prompt generation
using OpenRouter's Chat Completions API.

Note: OpenRouter does not support provider-specific features like Kimi's $web_search.
For web search capabilities, use native provider implementations.
"""

from typing import Dict, Any, List, Optional, cast
import json
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion
from backend.domain.models.messages import BaseMessage
from backend.infrastructure.llm.base.content_generators.title import BaseTitleGenerator
from backend.infrastructure.llm.base.content_generators.image_prompt import BaseImagePromptGenerator
from backend.infrastructure.llm.shared.constants import (
    DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT,
    DEFAULT_TITLE_GENERATION_TEMPERATURE,
    DEFAULT_TITLE_MAX_LENGTH,
)
from backend.infrastructure.llm.shared.utils.text_processing import parse_title_response
from backend.config import get_llm_settings


class TitleGenerator(BaseTitleGenerator):
    """
    Handles conversation title generation using OpenRouter Chat Completions API.

    Generates concise, descriptive titles based on the first exchange
    in a conversation to help users identify and organize their chats.
    """

    @staticmethod
    async def generate_title_from_messages(
        client: AsyncOpenAI,  # OpenRouter uses async OpenAI client
        latest_messages: List[BaseMessage]
    ) -> Optional[str]:
        """
        Generate a concise conversation title based on recent messages.

        Args:
            client: Async OpenAI client instance (OpenRouter client)
            latest_messages: Recent conversation messages to generate title from

        Returns:
            Generated title string, or None if generation fails
        """
        try:
            # Use base class validation
            if not BaseTitleGenerator.validate_messages_for_title(latest_messages):
                return None

            # Get OpenRouter configuration
            llm_settings = get_llm_settings()
            openrouter_config = llm_settings.get_openrouter_config()

            # Extract text content from messages and assemble into conversation context
            # This approach avoids sending complex message structures
            conversation_parts = []
            for msg in latest_messages:
                role = getattr(msg, 'role', 'user')
                content = getattr(msg, 'content', '')

                # Handle content list or string
                if isinstance(content, list):
                    # Extract text from content blocks
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
                {"role": "user", "content": f"Please generate a concise title based on the following conversation:\n\n{conversation_context}"}
            ]

            # Call OpenRouter API using Chat Completions format
            # Note: Set max_tokens to 1000 for thinking models (like GLM-4.6)
            # Thinking models need extra tokens for reasoning process before outputting the final answer
            response: ChatCompletion = await client.chat.completions.create(
                model=openrouter_config.model,
                messages=cast(Any, chat_messages),
                temperature=DEFAULT_TITLE_GENERATION_TEMPERATURE,
                max_tokens=1000
            )

            if not response.choices:
                return None

            # Extract title from response content
            title_response_text = response.choices[0].message.content or ""

            # Parse title using shared utility function
            return parse_title_response(title_response_text, max_length=DEFAULT_TITLE_MAX_LENGTH)

        except Exception as e:
            print(f"[ERROR] OpenRouter title generation failed: {str(e)}")
            return None


class ImagePromptGenerator(BaseImagePromptGenerator):
    """
    Handles text-to-image prompt generation using OpenRouter Chat Completions API.

    Creates detailed and effective prompts for image generation based on
    recent conversation context.
    """

    @staticmethod
    async def generate_text_to_image_prompt(
        client: AsyncOpenAI,
        session_id: Optional[str] = None,
        debug: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Generate high-quality text-to-image prompts using recent conversation context.

        Args:
            client: Async OpenRouter OpenAI client instance
            session_id: Optional session ID for conversation context
            debug: Enable debug output

        Returns:
            Dictionary with 'text_prompt' and 'negative_prompt' keys, or None if failed
        """
        try:
            # Get OpenRouter configuration
            llm_settings = get_llm_settings()
            openrouter_config = llm_settings.get_openrouter_config()

            # Prepare generation context using inherited method
            context = ImagePromptGenerator.prepare_generation_context(
                session_id=session_id,
                llm_provider="openrouter",
                llm_model=openrouter_config.model
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
                print(f"[OpenRouter ImagePrompt] Calling API with {len(chat_messages)} messages")

            # Call OpenRouter API
            response: ChatCompletion = await client.chat.completions.create(
                model=openrouter_config.model,
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
                print(f"[OpenRouter ImagePrompt] Raw response: {prompt_text[:200]}...")

            # Process response using inherited method
            return ImagePromptGenerator.process_generation_response(
                prompt_text, context, session_id, debug
            )

        except Exception as e:
            if debug:
                print(f"[OpenRouter ImagePrompt] Error during prompt generation: {str(e)}")
            return None
