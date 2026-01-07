"""
Anthropic-specific image prompt generator.

Generates high-quality text-to-image prompts using the Anthropic Claude API.
"""

from typing import Optional, Dict, Any, cast

import anthropic

from backend.config import get_llm_settings
from backend.infrastructure.llm.base.content_generators.image_prompt import BaseImagePromptGenerator
from backend.infrastructure.llm.providers.anthropic.message_formatter import MessageFormatter


class AnthropicImagePromptGenerator(BaseImagePromptGenerator):
    """
    Anthropic-specific image prompt generation using direct implementation.
    """

    @staticmethod
    async def generate_text_to_image_prompt(
        client: anthropic.AsyncAnthropic,
        session_id: Optional[str] = None,
        debug: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Generate high-quality text-to-image prompts using recent conversation context.

        Args:
            client: Anthropic Claude client instance for API calls
            session_id: Optional session ID for conversation context
            debug: Enable debug output

        Returns:
            Dictionary with 'text_prompt' and 'negative_prompt' keys, or None if failed
        """
        try:
            # Get Anthropic configuration for model info
            llm_settings = get_llm_settings()
            llm_anthropic_config = llm_settings.get_anthropic_config()

            # Prepare generation context using inherited method with provider info
            context = AnthropicImagePromptGenerator.prepare_generation_context(
                session_id=session_id,
                llm_provider="anthropic",
                llm_model=llm_anthropic_config.model
            )

            # Build messages using inherited method
            messages = AnthropicImagePromptGenerator.build_messages_for_generation(context)

            # Use MessageFormatter for message format conversion
            formatted_messages = MessageFormatter.format_messages(messages)

            # Use the model from context (which now correctly uses Anthropic's model)
            model_for_text_to_image = context.get('model', llm_anthropic_config.model)

            response = await client.messages.create(
                model=model_for_text_to_image,
                max_tokens=4096,
                temperature=context.get('temperature', 1.0),
                system=context['system_prompt'],
                messages=cast(Any, formatted_messages)
            )

            if response.content and len(response.content) > 0:
                # Handle different content block types safely
                first_content = response.content[0]
                prompt_text = getattr(first_content, 'text', str(first_content))

                # Process response using inherited method
                return AnthropicImagePromptGenerator.process_generation_response(
                    prompt_text, context, session_id, debug
                )
            return None

        except Exception as e:
            if debug:
                print(f"[text_to_image] Error during prompt generation: {str(e)}")
            return None
