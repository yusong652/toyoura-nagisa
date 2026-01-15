"""
Moonshot-specific image prompt generator.

Generates high-quality text-to-image prompts using the Moonshot (Moonshot) API.
"""

from typing import Optional, Dict, Any, cast

from openai.types.chat import ChatCompletion

from backend.config import get_llm_settings
from backend.infrastructure.llm.base.content_generators.image_prompt import BaseImagePromptGenerator


class MoonshotImagePromptGenerator(BaseImagePromptGenerator):
    """
    Moonshot-specific image prompt generation using Chat Completions API.
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
            # Get Moonshot configuration
            llm_settings = get_llm_settings()
            moonshot_config = llm_settings.get_moonshot_config()

            # Prepare generation context using inherited method
            context = MoonshotImagePromptGenerator.prepare_generation_context(
                session_id=session_id,
                llm_provider="moonshot",
                llm_model=moonshot_config.model
            )

            # Build messages using inherited method
            messages = MoonshotImagePromptGenerator.build_messages_for_generation(context)

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
                print(f"[Moonshot ImagePrompt] Calling API with {len(chat_messages)} messages")

            # Call Moonshot API (direct async call)
            response: ChatCompletion = await self.client.chat.completions.create(
                model=moonshot_config.model,
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
                print(f"[Moonshot ImagePrompt] Raw response: {prompt_text[:200]}...")

            # Process response using inherited method
            return MoonshotImagePromptGenerator.process_generation_response(
                prompt_text, context, session_id, debug
            )

        except Exception as e:
            if debug:
                print(f"[Moonshot ImagePrompt] Error during prompt generation: {str(e)}")
            return None
