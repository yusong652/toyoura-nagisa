"""
OpenRouter-specific title generator.

Generates concise conversation titles using the OpenRouter API.
"""

from typing import Optional, List, Any, cast

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from backend.domain.models.messages import BaseMessage
from backend.config import get_llm_settings
from backend.infrastructure.llm.base.content_generators.title import BaseTitleGenerator
from backend.infrastructure.llm.shared.constants import (
    DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT,
    DEFAULT_TITLE_GENERATION_TEMPERATURE,
    DEFAULT_TITLE_MAX_LENGTH,
)
from backend.infrastructure.llm.shared.utils.text_processing import parse_title_response


class OpenRouterTitleGenerator(BaseTitleGenerator):
    """
    OpenRouter-specific title generation using Chat Completions API.
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
