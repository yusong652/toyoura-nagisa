"""
Gemini-specific image prompt generator.

Generates high-quality text-to-image prompts using the Gemini API.
"""

from typing import Optional, Dict
from google.genai import types

from backend.infrastructure.llm.base.content_generators.image_prompt import BaseImagePromptGenerator
from backend.infrastructure.llm.providers.gemini.config import get_gemini_client_config
from backend.infrastructure.llm.providers.gemini.debug import GeminiDebugger
from backend.infrastructure.llm.providers.gemini.message_formatter import GeminiMessageFormatter
from backend.infrastructure.llm.providers.gemini.response_processor import GeminiResponseProcessor


class GeminiImagePromptGenerator(BaseImagePromptGenerator):
    """
    Gemini-specific image prompt generation using direct implementation.
    """

    @staticmethod
    async def generate_text_to_image_prompt(
        client,  # Gemini client instance
        session_id: Optional[str] = None,
        debug: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Generate high-quality text-to-image prompts using Gemini API.

        Args:
            client: Gemini client instance
            session_id: Optional session ID for conversation context
            debug: Enable debug output

        Returns:
            Dictionary with 'text_prompt' and 'negative_prompt' keys, or None if failed
        """
        try:
            # Get configuration
            from backend.config import get_llm_settings, get_text_to_image_settings
            llm_settings = get_llm_settings()
            llm_gemini_config = llm_settings.get_gemini_config()
            text_to_image_settings = get_text_to_image_settings()
            gemini_client_config = get_gemini_client_config()

            # Prepare context using inherited method
            context = GeminiImagePromptGenerator.prepare_generation_context(
                session_id=session_id,
                llm_provider="gemini",
                llm_model=llm_gemini_config.model
            )

            # Build messages using inherited method
            messages = GeminiImagePromptGenerator.build_messages_for_generation(context)

            # Format messages using Gemini formatter
            contents = GeminiMessageFormatter.format_messages(messages)

            # Create API call configuration
            config_kwargs = {
                "system_instruction": context['system_prompt'],
                "safety_settings": gemini_client_config.safety_settings.to_gemini_format(),
                "temperature": context['temperature'],
                "max_output_tokens": gemini_client_config.model_settings.max_output_tokens
            }

            # Use model from context
            model = context.get('model', llm_gemini_config.model)

            # Add thinking configuration based on model version
            if gemini_client_config.model_settings.enable_thinking:
                if model.startswith("gemini-3"):
                    config_kwargs["thinking_config"] = types.ThinkingConfig(
                        thinking_level=types.ThinkingLevel.HIGH,
                        include_thoughts=gemini_client_config.model_settings.include_thoughts_in_response
                    )
                elif model.startswith("gemini-2.5"):
                    config_kwargs["thinking_config"] = types.ThinkingConfig(
                        thinking_budget=-1,
                        include_thoughts=gemini_client_config.model_settings.include_thoughts_in_response
                    )

            prompt_config = types.GenerateContentConfig(**config_kwargs)

            if debug:
                print("[text_to_image] Gemini API call configuration:")
                GeminiDebugger.print_request(contents, prompt_config, model)

            # Use async non-streaming for better performance
            response = await client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=prompt_config
            )

            if debug:
                print("[text_to_image] Gemini API response:")
                GeminiDebugger.print_response(response)

            # Extract response text
            prompt_text = GeminiResponseProcessor.extract_text_content(response)

            if prompt_text:
                # Process response using inherited method
                return GeminiImagePromptGenerator.process_generation_response(
                    prompt_text, context, session_id, debug
                )

            return None

        except Exception as e:
            if debug:
                print(f"[text_to_image] Gemini prompt generation error: {str(e)}")
            raise
