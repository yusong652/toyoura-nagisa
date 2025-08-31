"""
Base video prompt generator for image-to-video generation.

Transforms static image descriptions into dynamic video prompts with motion.
"""

from abc import abstractmethod
from typing import Optional, Dict, Any
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
    
