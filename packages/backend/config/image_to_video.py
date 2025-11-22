"""
Image-to-video configuration module
Contains configurations related to image-to-video generation using ComfyUI AnimateDiff
"""
from __future__ import annotations
from typing import Literal, Dict, Any
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ImageToVideoSettings(BaseSettings):
    """Image-to-video configuration"""
    
    # Server configuration - uses complete URL with endpoint from env
    comfyui_server_url: str = Field(
        default="https://comfyui.ace-taffy.org",
        description="Complete ComfyUI server URL with endpoint",
        validation_alias="ANIMATEDIFF_WEBUI_URL"
    )
    
    # Video generation parameters
    fps: int = Field(default=20, ge=1, le=30, description="Frames per second")
    frame_count: int = Field(default=41, ge=8, le=512, description="Number of frames to generate (120 frames @ 24fps = 5 seconds)")
    seed: int = Field(default=-1, description="Random seed (-1 for random)")
    
    # Video resolution parameters
    width: int = Field(default=640, ge=256, le=1920, description="Video width in pixels")
    height: int = Field(default=960, ge=256, le=1920, description="Video height in pixels")
    
    # Sampling parameters
    steps: int = Field(default=20, ge=10, le=50, description="Number of sampling steps")
    cfg: float = Field(default=4.5, ge=1.0, le=20.0, description="CFG scale for sampling")
    
    # Debug configuration
    debug: bool = Field(default=True, description="Enable debug mode")
    
    # Few-shot learning and context configuration
    few_shot_max_length: int = Field(
        default=12,
        ge=0,
        le=32,
        description="Few-shot example maximum count for video prompt generation"
    )
    
    context_message_count: int = Field(
        default=4,
        ge=1,
        le=50,
        description="Number of recent conversation messages to include for context"
    )

    # Temperature configuration for video prompt generation
    video_prompt_temperature: float = Field(
        default=0.6,
        ge=0.0,
        le=2.0,
        description="Temperature parameter for video prompt generation (higher values = more creative)"
    )
    
    # Model architecture selection
    use_14b_model: bool = Field(
        default=False, 
        description="Use WAN 2.2 14B dual-model architecture (True) or 5B single-model (False)"
    )
    
    # Workflow selection
    workflow_type: Literal["wan22_optimized", "animatediff_standard"] = Field(
        default="wan22_optimized",
        description="Workflow type: wan22_optimized (WAN 2.2 5B high quality) or animatediff_standard (legacy)"
    )
    
    # Motion style descriptions for prompt enhancement
    motion_styles: Dict[str, str] = Field(
        default={
            "gentle": "subtle movement, gentle breeze, slow motion, soft transitions",
            "dynamic": "dynamic motion, energetic movement, action, fast-paced",
            "cinematic": "cinematic camera movement, smooth panning, professional filmmaking, dramatic angles",
            "natural": "natural movement, realistic physics, organic motion",
            "loop": "seamless loop, cyclic motion, repeating pattern, perfect loop"
        },
        description="Motion style descriptions to enhance video prompts"
    )
    
    # Default motion prompts
    default_motion_positive: str = Field(
        default="smooth motion, fluid animation, natural movement, cinematic",
        description="Default positive motion prompt"
    )
    default_motion_negative: str = Field(
        default="static, frozen, stuttering, jittery, abrupt cuts, inconsistent motion",
        description="Default negative motion prompt"
    )
    
    # Video prompt system prompt for LLM
    video_prompt_system: str = Field(
        default=(
            "You are an expert at transforming static image prompts into dynamic video prompts for AI video generation. "
            "Based on the original image prompt and motion type, generate optimized prompts for video creation. "
            "Your response must include both a video prompt and a negative prompt in the specified format:\n\n"
            "<video_prompt>[enhanced prompt with motion descriptions here]</video_prompt>\n"
            "<negative_prompt>[negative prompt for video generation here]</negative_prompt>\n\n"
            "The video prompt should add motion, camera movements, and temporal changes while preserving the core "
            "subject and artistic style. The negative prompt should specify what to avoid in video generation."
        ),
        description="System prompt for LLM when generating video prompts from image context"
    )

    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='_',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )

# Global configuration instance
def get_image_to_video_settings() -> ImageToVideoSettings:
    """Get image-to-video configuration instance"""
    return ImageToVideoSettings()