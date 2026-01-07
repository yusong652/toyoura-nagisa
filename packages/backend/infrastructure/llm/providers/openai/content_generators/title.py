"""
OpenAI-specific title generator.

Generates concise conversation titles using the OpenAI API.
"""

from typing import Optional, List

from openai.types.responses import Response

from backend.domain.models.messages import BaseMessage, UserMessage
from backend.infrastructure.llm.base.content_generators.title import BaseTitleGenerator
from backend.infrastructure.llm.shared.constants import DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT
from backend.infrastructure.llm.shared.utils.text_processing import parse_title_response
from backend.infrastructure.llm.providers.openai.response_processor import OpenAIResponseProcessor
from backend.infrastructure.llm.providers.openai.message_formatter import OpenAIMessageFormatter
from backend.infrastructure.llm.providers.openai.constants import (
    DEFAULT_TITLE_MODEL,
    TITLE_GENERATION_TEMPERATURE,
    TITLE_MAX_LENGTH,
)


class OpenAITitleGenerator(BaseTitleGenerator):
    """
    OpenAI-specific title generation using shared logic where possible.
    """

    @staticmethod
    async def generate_title_from_messages(
        client,  # OpenAI client instance
        latest_messages: List[BaseMessage]
    ) -> Optional[str]:
        """
        Generate a concise conversation title based on recent messages.

        Args:
            client: OpenAI client instance for API calls
            latest_messages: Recent conversation messages to generate title from

        Returns:
            Generated title string, or None if generation fails
        """
        try:
            # Use base class validation
            if not BaseTitleGenerator.validate_messages_for_title(latest_messages):
                return None

            # Use shared system prompt for title generation
            system_prompt = DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT

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

            # Create simple message with conversation as context
            simple_message = UserMessage(
                role="user",
                content=f"Please generate a concise title based on the following conversation:\n\n{conversation_context}"
            )

            # Format message to Responses API input
            input_items = OpenAIMessageFormatter.format_messages([simple_message])

            api_kwargs = {
                "model": DEFAULT_TITLE_MODEL,
                "instructions": system_prompt,
                "input": input_items,
                "temperature": TITLE_GENERATION_TEMPERATURE,
                "max_output_tokens": 100
            }

            response: Response = await client.responses.create(**api_kwargs)

            if not response.output:
                return None

            title_response_text = OpenAIResponseProcessor.extract_text_content(response)

            # Parse title using shared utility function
            return parse_title_response(title_response_text, max_length=TITLE_MAX_LENGTH)

        except Exception as e:
            print(f"OpenAI title generation error: {str(e)}")
            return None
