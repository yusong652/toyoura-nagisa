"""
Zhipu-specific title generator.

Generates concise conversation titles using the Zhipu (智谱) API.
"""

from typing import Optional, List, cast
import asyncio

from zai.types.chat import Completion

from backend.domain.models.messages import BaseMessage
from backend.config import get_llm_settings
from backend.infrastructure.llm.base.content_generators.title import BaseTitleGenerator
from backend.infrastructure.llm.shared.constants import (
    DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT,
    DEFAULT_TITLE_GENERATION_TEMPERATURE,
    DEFAULT_TITLE_MAX_LENGTH,
)
from backend.infrastructure.llm.shared.utils.text_processing import parse_title_response


class ZhipuTitleGenerator(BaseTitleGenerator):
    """
    Zhipu-specific title generation using Chat Completions API.
    """

    async def generate_title_from_messages(
        self,
        latest_messages: List[BaseMessage]
    ) -> Optional[str]:
        """
        Generate a concise conversation title based on recent messages.

        Args:
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
                    self.client.chat.completions.create,
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
