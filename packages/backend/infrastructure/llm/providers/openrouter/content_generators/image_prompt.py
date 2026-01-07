"""
OpenRouter-specific image prompt generator.

Generates high-quality text-to-image prompts using the OpenRouter API.
"""

from typing import Optional, Dict, Any, cast

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from backend.config import get_llm_settings
from backend.infrastructure.llm.base.content_generators.image_prompt import BaseImagePromptGenerator


class OpenRouterImagePromptGenerator(BaseImagePromptGenerator):
    """
    OpenRouter-specific image prompt generation using Chat Completions API.
    """

    @staticmethod
    async def generate_text_to_image_prompt(
        client: AsyncOpenAI,
        session_id: Optional[str] = None,
        debug: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Generate high-quality text-to-image prompts using recent conversation context.

        Args:
            client: Async OpenRouter OpenAI client instance
            session_id: Optional session ID for conversation context
            debug: Enable debug output

        Returns:
            Dictionary with 'text_prompt' and 'negative_prompt' keys, or None if failed
        """
        try:
            # Get OpenRouter configuration
            llm_settings = get_llm_settings()
            openrouter_config = llm_settings.get_openrouter_config()

            # Prepare generation context using inherited method
            context = OpenRouterImagePromptGenerator.prepare_generation_context(
                session_id=session_id,
                llm_provider="openrouter",
                llm_model=openrouter_config.model
            )

            # Build messages using inherited method
            messages = OpenRouterImagePromptGenerator.build_messages_for_generation(context)

            # Build chat messages for Chat Completions API
            chat_messages = [
                {"role": "system", "content": context['system_prompt']}
            ]

            for msg in messages:
                # Get role - all message types should have this
                role = getattr(msg, 'role', 'user')
                content = getattr(msg, 'content', '')

                # Handle content list or string
                if isinstance(content, list):
                    # Extract text from content blocks
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get('type') == 'text':
                            text_parts.append(block.get('text', ''))
                    content_str = '\n'.join(text_parts)
                else:
                    content_str = str(content)

                chat_messages.append({
                    "role": role,
                    "content": content_str
                })

            if debug:
                print(f"[OpenRouter ImagePrompt] Calling API with {len(chat_messages)} messages")

            # Call OpenRouter API
            response: ChatCompletion = await client.chat.completions.create(
                model=openrouter_config.model,
                messages=cast(Any, chat_messages),
                temperature=context.get('temperature', 1.0),
                max_tokens=1024
            )

            if not response.choices:
                return None

            prompt_text = response.choices[0].message.content or ""

            if not prompt_text:
                return None

            if debug:
                print(f"[OpenRouter ImagePrompt] Raw response: {prompt_text[:200]}...")

            # Process response using inherited method
            return OpenRouterImagePromptGenerator.process_generation_response(
                prompt_text, context, session_id, debug
            )

        except Exception as e:
            if debug:
                print(f"[OpenRouter ImagePrompt] Error during prompt generation: {str(e)}")
            return None
