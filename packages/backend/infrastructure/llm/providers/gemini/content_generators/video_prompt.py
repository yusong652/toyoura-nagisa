"""
Gemini-specific video prompt generator.

Generates optimized video prompts using the Gemini API.
"""

from typing import Optional, Dict, List, Any
from google.genai import types

from backend.infrastructure.llm.base.content_generators.video_prompt import BaseVideoPromptGenerator
from backend.infrastructure.llm.providers.gemini.config import get_gemini_client_config
from backend.infrastructure.llm.providers.gemini.debug import GeminiDebugger
from backend.infrastructure.llm.providers.gemini.message_formatter import GeminiMessageFormatter
from backend.infrastructure.llm.providers.gemini.response_processor import GeminiResponseProcessor


class GeminiVideoPromptGenerator(BaseVideoPromptGenerator):
    """
    Gemini-specific video prompt generation using direct implementation.
    """

    @staticmethod
    async def generate_video_prompt(
        client,  # Gemini client instance
        original_prompt: str,
        image_base64: Optional[str] = None,
        motion_type: str = "cinematic",
        few_shot_history: Optional[List[Dict[str, Any]]] = None,
        session_id: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        """
        Generate optimized video prompt using Gemini API.

        Args:
            client: Gemini client instance
            original_prompt: Original static image generation prompt (not used directly)
            image_base64: Optional base64 encoded image (not sent to LLM)
            motion_type: Type of motion for the video
            few_shot_history: Optional few-shot examples (loaded from session if not provided)
            session_id: Session ID for context and history

        Returns:
            Dict with 'video_prompt' and 'negative_prompt' keys, or None if failed
        """
        try:
            # Get configuration
            from backend.config import get_llm_settings, get_image_to_video_settings
            llm_settings = get_llm_settings()
            llm_gemini_config = llm_settings.get_gemini_config()
            image_to_video_settings = get_image_to_video_settings()
            gemini_client_config = get_gemini_client_config()
            debug = llm_settings.debug

            # Convert motion_type to motion_style description
            motion_descriptions = {
                "gentle": "subtle, gentle movements like gentle breeze, slow motion, peaceful transitions",
                "dynamic": "energetic, dynamic motion with action sequences and fast movements",
                "cinematic": "cinematic camera movements, smooth panning, professional film-like motion",
                "loop": "seamless looping motion with cyclic, repeating patterns"
            }
            motion_style = motion_descriptions.get(motion_type, motion_descriptions["cinematic"])

            # Prepare context using inherited method
            context = GeminiVideoPromptGenerator.prepare_video_context(
                session_id=session_id,
                motion_style=motion_style,
                llm_provider="gemini",
                llm_model=llm_gemini_config.model
            )

            # Build messages using inherited method
            messages = GeminiVideoPromptGenerator.build_video_messages(context)

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
                print("[image_to_video] Gemini API call configuration:")
                GeminiDebugger.print_request(contents, prompt_config, model)

            # Use async non-streaming for better performance
            response = await client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=prompt_config
            )

            if debug:
                print("[image_to_video] Gemini API response:")
                GeminiDebugger.print_response(response)

            # Extract response text
            prompt_text = GeminiResponseProcessor.extract_text_content(response)

            if prompt_text:
                # Process response using inherited method
                return GeminiVideoPromptGenerator.process_video_response(
                    prompt_text, context, session_id, debug
                )

            return None

        except Exception as e:
            from backend.config import get_llm_settings
            debug = get_llm_settings().debug
            if debug:
                print(f"[image_to_video] Gemini video prompt generation error: {str(e)}")
            raise
