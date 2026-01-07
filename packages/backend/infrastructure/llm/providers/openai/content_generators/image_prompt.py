"""
OpenAI-specific image prompt generator.

Generates high-quality text-to-image prompts using the OpenAI API.
"""

from typing import Optional, Dict

from openai.types.responses import Response

from backend.config import get_llm_settings
from backend.infrastructure.llm.base.content_generators.image_prompt import BaseImagePromptGenerator
from backend.infrastructure.llm.providers.openai.response_processor import OpenAIResponseProcessor
from backend.infrastructure.llm.providers.openai.message_formatter import OpenAIMessageFormatter
from backend.infrastructure.llm.providers.openai.debug import OpenAIDebugger


class OpenAIImagePromptGenerator(BaseImagePromptGenerator):
    """
    OpenAI-specific image prompt generation using direct implementation.
    """

    async def generate_text_to_image_prompt(
        self,
        session_id: Optional[str] = None,
        debug: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Generate high-quality text-to-image prompts using recent conversation context.

        Args:
            session_id: Optional session ID for conversation context
            debug: Enable debug output

        Returns:
            Dictionary with 'text_prompt' and 'negative_prompt' keys, or None if failed
        """
        try:
            # Get OpenAI configuration for model info
            llm_settings = get_llm_settings()
            llm_openai_config = llm_settings.get_openai_config()

            # Prepare generation context using inherited method with provider info
            context = OpenAIImagePromptGenerator.prepare_generation_context(
                session_id=session_id,
                llm_provider="openai",
                llm_model=llm_openai_config.model
            )

            # Build messages using inherited method
            messages = OpenAIImagePromptGenerator.build_messages_for_generation(context)

            # Format messages to Responses API input
            input_items = OpenAIMessageFormatter.format_messages(messages)

            model_for_text_to_image = context.get('model', llm_openai_config.model)

            api_kwargs = {
                "model": model_for_text_to_image,
                "instructions": context['system_prompt'],
                "input": input_items,
                "temperature": context.get('temperature', 1.0),
                "max_output_tokens": 1024
            }

            if debug:
                OpenAIDebugger.print_debug_request_payload(api_kwargs)

            response: Response = await self.client.responses.create(**api_kwargs)

            if debug:
                OpenAIDebugger.log_raw_response(response)

            prompt_text = OpenAIResponseProcessor.extract_text_content(response)

            if not prompt_text:
                return None

            if debug:
                print(f"[text_to_image] Raw response: {prompt_text[:200]}...")

            # Process response using inherited method
            return OpenAIImagePromptGenerator.process_generation_response(
                prompt_text, context, session_id, debug
            )

        except Exception as e:
            if debug:
                print(f"[text_to_image] Error during prompt generation: {str(e)}")
            return None
