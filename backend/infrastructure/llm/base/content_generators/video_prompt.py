"""
Base video prompt generator for image-to-video generation.

Transforms static image descriptions into dynamic video prompts with motion.
"""

from abc import abstractmethod
from typing import Optional, Dict, Any
from backend.infrastructure.llm.shared.utils.image_to_video import save_video_prompt_generation
from backend.infrastructure.llm.shared.constants.prompts import DEFAULT_VIDEO_PROMPT_SYSTEM_PROMPT
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
    def create_video_prompt_request(original_prompt: str, motion_type: str = "cinematic") -> str:
        """
        Create the user message for video prompt generation.
        
        Args:
            original_prompt: Original static image prompt
            motion_type: Type of motion for the video
            
        Returns:
            Formatted request message
        """
        motion_descriptions = {
            "gentle": "subtle, gentle movements like gentle breeze, slow motion, peaceful transitions",
            "dynamic": "energetic, dynamic motion with action sequences and fast movements", 
            "cinematic": "cinematic camera movements, smooth panning, professional film-like motion",
            "loop": "seamless looping motion with cyclic, repeating patterns"
        }
        
        motion_desc = motion_descriptions.get(motion_type, motion_descriptions["cinematic"])
        
        return f"""Transform this static image prompt into a dynamic video prompt with {motion_type} style:

Original prompt: {original_prompt}

Add {motion_desc} to enhance the scene."""
    
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
        
        # Try to extract using XML tags first
        video_match = re.search(VIDEO_PROMPT_PATTERN, response_text, re.DOTALL)
        negative_match = re.search(NEGATIVE_PROMPT_PATTERN, response_text, re.DOTALL)
        
        if video_match:
            video_prompt = video_match.group(1).strip()
        else:
            # Fallback to old format for backward compatibility
            video_prompt = original_prompt
            for line in response_text.split("\n"):
                if line.startswith("VIDEO_PROMPT:"):
                    video_prompt = line.replace("VIDEO_PROMPT:", "").strip()
                    break
        
        if negative_match:
            negative_prompt = negative_match.group(1).strip()
        else:
            # Fallback to old format for backward compatibility
            negative_prompt = settings.default_motion_negative
            for line in response_text.split("\n"):
                if line.startswith("NEGATIVE_PROMPT:"):
                    negative_prompt = line.replace("NEGATIVE_PROMPT:", "").strip()
                    break
        
        # Add default motion keywords
        video_prompt = f"{video_prompt}, {settings.default_motion_positive}"
        
        return {
            "video_prompt": video_prompt,
            "negative_prompt": negative_prompt
        }
    
    @staticmethod
    def process_video_generation_response(
        response_text: str,
        original_prompt: str,
        motion_type: str = "cinematic",
        session_id: Optional[str] = None,
        debug: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Process the raw video generation response and extract prompts.
        Similar to BaseImagePromptGenerator.process_generation_response pattern.
        
        Args:
            response_text: Raw response text from LLM (with XML tags)
            original_prompt: Original static image prompt
            motion_type: Type of motion for the video
            session_id: Optional session ID for saving history
            debug: Enable debug output
            
        Returns:
            Dictionary with 'video_prompt' and 'negative_prompt' keys, or None if failed
        """
        if not response_text:
            return None
        
        # Parse the response
        parsed_result = BaseVideoPromptGenerator.parse_video_prompt_response(
            response_text, original_prompt
        )
        
        if not parsed_result:
            return None
        
        # Save to history for future few-shot learning
        if session_id:
            try:
                # Create user request message (same format as create_video_prompt_request)
                user_request = BaseVideoPromptGenerator.create_video_prompt_request(
                    original_prompt, motion_type
                )
                
                # Save with the original LLM response (already contains XML tags)
                save_video_prompt_generation(
                    session_id=session_id,
                    user_request=user_request,
                    assistant_response=response_text  # Save raw LLM response with XML tags
                )
                if debug:
                    print(f"[video_prompt] Saved generation to history for session {session_id}")
            except Exception as e:
                if debug:
                    print(f"[video_prompt] Warning: Failed to save generation to history: {e}")
        
        return parsed_result