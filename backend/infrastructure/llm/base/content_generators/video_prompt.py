"""
Base video prompt generator for image-to-video generation.

Transforms static image descriptions into dynamic video prompts with motion.
"""

from abc import abstractmethod
from typing import Optional, Dict, Any, List
from backend.domain.models.messages import BaseMessage, UserMessage
from backend.infrastructure.storage.session_manager import get_latest_n_messages
from backend.infrastructure.llm.shared.utils.text_processing import extract_text_content
from backend.infrastructure.llm.shared.utils.image_to_video import load_video_prompt_history, save_video_prompt_generation
from backend.infrastructure.llm.shared.constants.defaults import DEFAULT_FEW_SHOT_MAX_LENGTH, DEFAULT_CONTEXT_MESSAGE_COUNT
from backend.infrastructure.llm.shared.constants.prompts import DEFAULT_VIDEO_PROMPT_SYSTEM_PROMPT, CONVERSATION_VIDEO_PROMPT_PREFIX
from .base import BaseContentGenerator


class BaseVideoPromptGenerator(BaseContentGenerator):
    """
    Abstract base class for video prompt generation from static image prompts.
    
    Transforms static image descriptions into dynamic video prompts with motion,
    camera movements, and temporal changes for AI video generation models.
    """
    
    @staticmethod
    @abstractmethod
    async def generate_video_prompt(
        client,  # LLM client instance (provider-specific)
        original_prompt: str,
        image_base64: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        """
        Generate optimized video prompt from static image prompt.
        
        Args:
            client: Provider-specific LLM client instance
            original_prompt: Original static image generation prompt
            image_base64: Optional base64 encoded image for visual context
            
        Returns:
            Dict with 'video_prompt' and 'negative_prompt' keys, or None if failed
        """
        pass
    
    @staticmethod
    def prepare_video_context(
        session_id: Optional[str] = None,
        motion_style: Optional[str] = None,
        few_shot_max_length: int = DEFAULT_FEW_SHOT_MAX_LENGTH,
        context_message_count: int = DEFAULT_CONTEXT_MESSAGE_COUNT,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Prepare context data for video prompt generation.

        Args:
            session_id: Optional session ID for conversation context
            motion_style: Description of desired motion style
            few_shot_max_length: Maximum number of few-shot examples
            context_message_count: Number of recent messages to include
            llm_provider: Optional LLM provider name
            llm_model: Optional LLM model name

        Returns:
            Dictionary containing prepared context data
        """
        from backend.config import get_image_to_video_settings
        image_to_video_settings = get_image_to_video_settings()

        # Get latest conversation messages
        latest_messages = get_latest_n_messages(session_id, context_message_count) if session_id else tuple([None] * context_message_count)

        # Load few-shot history
        few_shot_history = load_video_prompt_history(session_id) if session_id else []

        # Build conversation context
        conversation_text = CONVERSATION_VIDEO_PROMPT_PREFIX
        for msg in latest_messages:
            if msg is not None:
                text_content = extract_text_content(msg.content)
                if text_content:
                    role_label = "User" if msg.role == "user" else "Assistant"
                    conversation_text += f"\n{role_label}: {text_content}"

        # Build few-shot examples
        few_shot_text = ""
        if few_shot_history:
            few_shot_text = "\n\nPrevious examples for reference:\n"
            for i, example in enumerate(few_shot_history[:few_shot_max_length], 1):
                few_shot_text += f"\nExample {i}:\n"
                few_shot_text += f"Context: {example.get('conversation_text', 'N/A')}\n"
                few_shot_text += f"Generated: {example.get('generated_prompt', 'N/A')}\n"

        # Build system prompt
        system_prompt = DEFAULT_VIDEO_PROMPT_SYSTEM_PROMPT
        if motion_style:
            system_prompt += f"\n\nDesired motion style: {motion_style}"
        if llm_provider and llm_model:
            system_prompt += f"\n\nLLM: {llm_provider} ({llm_model})"

        return {
            'system_prompt': system_prompt,
            'conversation_text': conversation_text,
            'few_shot_history': few_shot_history,
            'few_shot_text': few_shot_text,
            'motion_style': motion_style or "cinematic camera movements, smooth panning, professional film-like motion",
            'temperature': 1.0,
            'model': llm_model
        }

    @staticmethod
    def build_video_messages(context: Dict[str, Any]) -> List[BaseMessage]:
        """
        Build message sequence for video prompt generation.

        Args:
            context: Context dictionary from prepare_video_context

        Returns:
            List of messages ready for LLM API
        """
        user_content = context['conversation_text']
        if context.get('few_shot_text'):
            user_content += context['few_shot_text']
        if context.get('motion_style'):
            user_content += f"\n\nMotion style: {context['motion_style']}"

        return [UserMessage(role="user", content=[{"type": "text", "text": user_content}])]

    @staticmethod
    def process_video_response(
        response_text: str,
        context: Dict[str, Any],
        session_id: Optional[str] = None,
        debug: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Process video prompt generation response.

        Args:
            response_text: Raw LLM response text
            context: Context dictionary from prepare_video_context
            session_id: Optional session ID for saving history
            debug: Enable debug output

        Returns:
            Dictionary with 'video_prompt' and 'negative_prompt' keys, or None if failed
        """
        if not response_text:
            return None

        # Parse using existing method
        result = BaseVideoPromptGenerator.parse_video_prompt_response(
            response_text,
            original_prompt=context.get('conversation_text', '')
        )

        # Save to history for future few-shot learning
        if session_id:
            try:
                save_video_prompt_generation(
                    session_id,
                    context['conversation_text'],
                    response_text
                )
            except Exception as e:
                if debug:
                    print(f"[image_to_video] Warning: Failed to save generation to history: {e}")

        return result

    @staticmethod
    def parse_video_prompt_response(response_text: str, original_prompt: str) -> Dict[str, str]:
        """
        Parse the LLM response to extract video and negative prompts using XML tags.
        
        Args:
            response_text: Raw LLM response text
            original_prompt: Original prompt as fallback
            
        Returns:
            Dict with 'video_prompt' and 'negative_prompt'
        """
        import re
        from backend.config import get_image_to_video_settings
        from backend.infrastructure.llm.shared.constants.prompts import VIDEO_PROMPT_PATTERN, NEGATIVE_PROMPT_PATTERN
        
        settings = get_image_to_video_settings()
        
        # Clean up markdown code blocks if present
        cleaned_text = response_text
        if "```" in response_text:
            # Remove markdown code block markers
            cleaned_text = re.sub(r'```(?:text|xml|html)?\n?', '', response_text)
        
        # Try to extract using XML tags first
        video_match = re.search(VIDEO_PROMPT_PATTERN, cleaned_text, re.DOTALL)
        negative_match = re.search(NEGATIVE_PROMPT_PATTERN, cleaned_text, re.DOTALL)
        
        if video_match:
            video_prompt = video_match.group(1).strip()
        else:
            # Fallback to old format for backward compatibility
            video_prompt = original_prompt
            for line in cleaned_text.split("\n"):
                if line.startswith("VIDEO_PROMPT:"):
                    video_prompt = line.replace("VIDEO_PROMPT:", "").strip()
                    break
        
        if negative_match:
            negative_prompt = negative_match.group(1).strip()
        else:
            # Fallback to old format for backward compatibility
            negative_prompt = settings.default_motion_negative
            for line in cleaned_text.split("\n"):
                if line.startswith("NEGATIVE_PROMPT:"):
                    negative_prompt = line.replace("NEGATIVE_PROMPT:", "").strip()
                    break
        
        # Add default motion keywords
        video_prompt = f"{video_prompt}, {settings.default_motion_positive}"
        
        return {
            "video_prompt": video_prompt,
            "negative_prompt": negative_prompt
        }
    
