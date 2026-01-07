"""
OpenRouter-specific video prompt generator.

Generates optimized video prompts using the OpenRouter API.
"""

from typing import Optional, Dict, List, Any, cast

from openai.types.chat import ChatCompletion

from backend.config import get_llm_settings
from backend.infrastructure.llm.base.content_generators.video_prompt import BaseVideoPromptGenerator


class OpenRouterVideoPromptGenerator(BaseVideoPromptGenerator):
    """
    OpenRouter-specific video prompt generation using Chat Completions API.
    """

    async def generate_video_prompt(
        self,
        original_prompt: str,
        image_base64: Optional[str] = None,
        motion_type: str = "cinematic",
        few_shot_history: Optional[List[Dict[str, Any]]] = None,
        session_id: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        """
        Generate optimized video prompt using OpenRouter API.

        Args:
            original_prompt: Original static image generation prompt (not used directly)
            image_base64: Optional base64 encoded image (not sent to LLM)
            motion_type: Type of motion for the video
            few_shot_history: Optional few-shot examples (loaded from session if not provided)
            session_id: Session ID for context and history

        Returns:
            Dict with 'video_prompt' and 'negative_prompt' keys, or None if failed
        """
        # Get configuration
        llm_settings = get_llm_settings()
        try:
            
            openrouter_config = llm_settings.get_openrouter_config()
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
            context = OpenRouterVideoPromptGenerator.prepare_video_context(
                session_id=session_id,
                motion_style=motion_style,
                llm_provider="openrouter",
                llm_model=openrouter_config.model
            )

            # Build messages using inherited method
            messages = OpenRouterVideoPromptGenerator.build_video_messages(context)

            # Build chat messages for Chat Completions API
            chat_messages = [
                {"role": "system", "content": context['system_prompt']}
            ]

            for msg in messages:
                role = getattr(msg, 'role', 'user')
                content = getattr(msg, 'content', '')

                # Handle content list or string
                if isinstance(content, list):
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
                print(f"[OpenRouter VideoPrompt] Calling API with {len(chat_messages)} messages")

            # Call OpenRouter API
            response: ChatCompletion = await self.client.chat.completions.create(
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
                print(f"[OpenRouter VideoPrompt] Raw response: {prompt_text[:200]}...")

            # Process response using inherited method
            return OpenRouterVideoPromptGenerator.process_video_response(
                prompt_text, context, session_id, debug
            )

        except Exception as e:
            if llm_settings.debug:
                print(f"[OpenRouter VideoPrompt] Error during prompt generation: {str(e)}")
            raise
