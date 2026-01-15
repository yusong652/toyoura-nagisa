"""
Moonshot-specific title generator.

Generates concise conversation titles using the Moonshot (Moonshot) API.
"""

from typing import Optional, List, Any, cast

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


class MoonshotTitleGenerator(BaseTitleGenerator):
    """
    Moonshot-specific title generation using Chat Completions API.
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

            # Get Moonshot configuration
            llm_settings = get_llm_settings()
            moonshot_config = llm_settings.get_moonshot_config()

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

            # Call Moonshot API using Chat Completions format (direct async call)
            response: ChatCompletion = await self.client.chat.completions.create(
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
