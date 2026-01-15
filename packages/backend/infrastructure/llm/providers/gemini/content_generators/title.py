"""
Gemini-specific title generator.

Generates concise conversation titles using the Gemini API.
"""

from typing import Optional, List
from google.genai import types

from backend.domain.models.messages import BaseMessage
from backend.config import get_llm_settings
from backend.infrastructure.llm.base.content_generators.title import BaseTitleGenerator
from backend.infrastructure.llm.shared.utils.text_processing import parse_title_response
from backend.infrastructure.llm.shared.constants.defaults import (
    DEFAULT_TITLE_MAX_LENGTH,
    DEFAULT_TITLE_GENERATION_TEMPERATURE,
)
from backend.infrastructure.llm.shared.constants.prompts import (
    DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT,
)
from backend.infrastructure.llm.providers.gemini.config import get_gemini_client_config
from backend.infrastructure.llm.providers.gemini.response_processor import GeminiResponseProcessor


class GeminiTitleGenerator(BaseTitleGenerator):
    """
    Gemini-specific title generation using shared logic where possible.
    """

    async def generate_title_from_messages(
        self,
        latest_messages: List[BaseMessage],
    ) -> Optional[str]:
        """
        Generate a concise conversation title based on recent messages.

        Args:
            latest_messages: Recent conversation messages to generate title from

        Returns:
            Generated title string, or None if generation fails
        """
        try:
            # Explicit validation before base class validation
            if latest_messages is None or not latest_messages:
                return None

            # Use base class validation
            if not BaseTitleGenerator.validate_messages_for_title(latest_messages):
                return None

            # Read Gemini configuration
            gemini_config = get_gemini_client_config()

            system_prompt = DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT

            # Extract text content from messages and assemble into conversation context
            # This unified approach is consistent with other providers (Anthropic, OpenAI, Moonshot, OpenRouter)
            conversation_parts = []
            for msg in latest_messages:
                role = getattr(msg, 'role', 'user')
                content = getattr(msg, 'content', '')

                # Handle content list or string
                if isinstance(content, list):
                    # Extract text from content blocks (skip thinking blocks, tool_use, tool_result)
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict):
                            block_type = block.get('type')
                            if block_type == 'text':
                                text_parts.append(block.get('text', ''))
                    content_str = '\n'.join(text_parts)
                else:
                    content_str = str(content) if content else ''

                # Skip messages with no text content
                if not content_str or not content_str.strip():
                    continue

                # Add to conversation with role label
                role_label = "User" if role == "user" else "Assistant"
                conversation_parts.append(f"{role_label}: {content_str}")

            # Ensure we have at least some conversation content
            if not conversation_parts:
                return None

            # Combine conversation into single context
            conversation_context = '\n'.join(conversation_parts)

            # Build simple content with conversation as context
            # This prevents issues with complex message structures
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part(text=f"Please generate a concise title based on the following conversation:\n\n{conversation_context}")]
                )
            ]

            # Configure title generation parameters
            title_config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=DEFAULT_TITLE_GENERATION_TEMPERATURE,
                max_output_tokens=2048  # Large buffer for non-thinking models
            )

            # Get model from configuration
            llm_settings = get_llm_settings()
            gemini_config = llm_settings.get_gemini_config()

            # Use a reliable non-thinking model for title generation
            # Thinking models (gemini-2.5-pro, gemini-exp-*) may refuse or return
            # empty responses for simple tasks like title generation
            title_generation_model = "gemini-2.0-flash"

            # Use async non-streaming for better performance
            response = await self.client.aio.models.generate_content(
                model=title_generation_model,
                contents=contents,
                config=title_config
            )

            # Extract response text using ResponseProcessor
            title_response_text = GeminiResponseProcessor.extract_text_content(response)

            # Parse title using shared utility function
            return parse_title_response(title_response_text, max_length=DEFAULT_TITLE_MAX_LENGTH)

        except Exception as e:
            print(f"Gemini title generation error: {str(e)}")
            return None
