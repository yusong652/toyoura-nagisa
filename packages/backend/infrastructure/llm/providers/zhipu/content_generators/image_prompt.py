"""
Zhipu-specific image prompt generator.

Generates high-quality text-to-image prompts using the Zhipu (智谱) API.
"""

from typing import Optional, Dict, cast
import asyncio

from zai import ZhipuAiClient
from zai.types.chat import Completion

from backend.config import get_llm_settings
from backend.infrastructure.llm.base.content_generators.image_prompt import BaseImagePromptGenerator


class ZhipuImagePromptGenerator(BaseImagePromptGenerator):
    """
    Zhipu-specific image prompt generation using Chat Completions API.
    """

    @staticmethod
    async def generate_text_to_image_prompt(
        client: ZhipuAiClient,  # Zhipu uses synchronous client
        session_id: Optional[str] = None,
        debug: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Generate high-quality text-to-image prompts using recent conversation context.

        Args:
            client: Zhipu ZhipuAiClient instance (synchronous)
            session_id: Optional session ID for conversation context
            debug: Enable debug output

        Returns:
            Dictionary with 'text_prompt' and 'negative_prompt' keys, or None if failed
        """
        try:
            # Get Zhipu configuration
            llm_settings = get_llm_settings()
            zhipu_config = llm_settings.get_zhipu_config()

            # Prepare generation context using inherited method
            context = ZhipuImagePromptGenerator.prepare_generation_context(
                session_id=session_id,
                llm_provider="zhipu",
                llm_model=zhipu_config.model
            )

            # Build messages using inherited method
            messages = ZhipuImagePromptGenerator.build_messages_for_generation(context)

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
                    # Extract text from content blocks (skip thinking blocks for prompt generation)
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict):
                            block_type = block.get('type')
                            if block_type == 'text':
                                text_parts.append(block.get('text', ''))
                            # Skip thinking blocks - they contain reasoning, not conversation content
                    content_str = '\n'.join(text_parts)
                else:
                    content_str = str(content)

                chat_messages.append({
                    "role": role,
                    "content": content_str
                })

            if debug:
                print(f"[Zhipu ImagePrompt] Calling API with {len(chat_messages)} messages")

            # Call Zhipu API (wrap synchronous call with asyncio.to_thread)
            response: Completion = cast(
                Completion,
                await asyncio.to_thread(
                    client.chat.completions.create,
                    model=zhipu_config.model,
                    messages=chat_messages,
                    temperature=context.get('temperature', 1.0),
                    max_tokens=1024,
                    stream=False
                )
            )

            if not response.choices:
                return None

            prompt_text = response.choices[0].message.content or ""

            if not prompt_text:
                return None

            if debug:
                print(f"[Zhipu ImagePrompt] Raw response: {prompt_text[:200]}...")

            # Process response using inherited method
            return ZhipuImagePromptGenerator.process_generation_response(
                prompt_text, context, session_id, debug
            )

        except Exception as e:
            if debug:
                print(f"[Zhipu ImagePrompt] Error during prompt generation: {str(e)}")
            return None
