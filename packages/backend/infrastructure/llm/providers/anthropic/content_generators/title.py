"""
Anthropic-specific title generator.

Generates concise conversation titles using the Anthropic Claude API.
"""

from typing import Optional, List

from backend.domain.models.messages import BaseMessage
from backend.config import get_llm_settings
from backend.infrastructure.llm.base.content_generators.title import BaseTitleGenerator
from backend.infrastructure.llm.shared.utils.text_processing import parse_title_response
from backend.infrastructure.llm.shared.constants import DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT
from backend.infrastructure.llm.providers.anthropic.config import get_anthropic_client_config
from backend.infrastructure.llm.providers.anthropic.response_processor import AnthropicResponseProcessor


class AnthropicTitleGenerator(BaseTitleGenerator):
    """
    Anthropic-specific title generation using shared logic where possible.
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
            # Use base class validation
            if not BaseTitleGenerator.validate_messages_for_title(latest_messages):
                return None

            # Get Anthropic configuration
            anthropic_config = get_anthropic_client_config()

            # Extract text content from messages and assemble into conversation context
            # This approach avoids sending complex message structures (thinking blocks, etc.)
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

            # Build simple message structure with conversation as context
            # This prevents issues with complex message structures (thinking blocks, etc.)
            messages = [
                {
                    "role": "user",
                    "content": f"Please generate a concise title based on the following conversation:\n\n{conversation_context}"
                }
            ]

            # Use shared system prompt for consistency
            system_prompt = DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT

            # Build API call parameters using the configuration system
            api_kwargs = anthropic_config.get_api_call_kwargs(
                system_prompt=system_prompt,
                messages=messages
            )

            # Override parameters specific to title generation
            api_kwargs.update({
                "max_tokens": 100,  # Sufficient for title generation
                "temperature": 1.0
            })

            # Disable thinking for title generation (simple task, no need for extended thinking)
            if "thinking" in api_kwargs:
                del api_kwargs["thinking"]

            llm_settings = get_llm_settings()
            debug = llm_settings.debug
            if debug:
                print("[DEBUG] Anthropic title generation API kwargs:")
                import pprint
                pprint.pprint(api_kwargs)

            response = await self.client.messages.create(**api_kwargs)

            # Extract text content using ResponseProcessor (skips thinking blocks)
            title_response_text = AnthropicResponseProcessor.extract_text_content(response)

            if title_response_text:
                # Parse title using shared utility function
                # Using max_length=30 to match original Anthropic behavior
                return parse_title_response(title_response_text, max_length=30)
            return None

        except Exception as e:
            print(f"Anthropic title generation error: {str(e)}")
            return None
