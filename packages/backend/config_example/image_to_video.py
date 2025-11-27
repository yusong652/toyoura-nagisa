"""
Image-to-video configuration module
Contains configurations related to image-to-video generation using ComfyUI WAN 2.2
"""
from __future__ import annotations
from typing import Literal, Dict, Any
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ImageToVideoSettings(BaseSettings):
    """Image-to-video generation configuration"""
    
    # Server configuration - Use environment variable or update with your server URL
    comfyui_server_url: str = Field(
        default="http://127.0.0.1:8188",  # Example: Local ComfyUI server
        description="ComfyUI server URL for video generation (e.g., http://your-server.com)",
        validation_alias="ANIMATEDIFF_WEBUI_URL"  # Can use env var for compatibility
    )
    
    # Video generation parameters
    fps: int = Field(
        default=24, 
        ge=1, 
        le=60, 
        description="Frames per second for video output"
    )
    
    frame_count: int = Field(
        default=41, 
        ge=8, 
        le=512, 
        description="Number of frames to generate (41 frames @ 24fps = ~1.7 seconds)"
    )
    
    seed: int = Field(
        default=-1, 
        description="Random seed for generation (-1 for random)"
    )
    
    # Video resolution parameters (optimal for WAN 2.2)
    width: int = Field(
        default=1280, 
        ge=256, 
        le=1920, 
        description="Video width in pixels (1280 recommended for WAN 2.2)"
    )
    
    height: int = Field(
        default=704, 
        ge=256, 
        le=1920, 
        description="Video height in pixels (704 recommended for WAN 2.2)"
    )
    
    # Sampling parameters
    steps: int = Field(
        default=30, 
        ge=10, 
        le=50, 
        description="Number of sampling steps"
    )
    
    cfg: float = Field(
        default=5.0, 
        ge=1.0, 
        le=20.0, 
        description="CFG scale for sampling"
    )
    
    # Debug configuration
    debug: bool = Field(
        default=True, 
        description="Enable debug logging for troubleshooting"
    )
    
    # Few-shot learning and context configuration
    few_shot_max_length: int = Field(
        default=15,
        ge=0,
        le=32,
        description="Maximum number of few-shot examples for video prompt generation"
    )
    
    context_message_count: int = Field(
        default=4,
        ge=1,
        le=50,
        description="Number of recent conversation messages to include for context"
    )
    
    # Temperature configuration for video prompt generation
    video_prompt_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Temperature for LLM video prompt generation (higher = more creative)"
    )
    
    # Model architecture selection
    use_14b_model: bool = Field(
        default=False, 
        description="Use WAN 2.2 14B dual-model architecture (True) or 5B single-model (False)"
    )
    
    # Workflow selection
    workflow_type: Literal["wan22_optimized", "animatediff_standard"] = Field(
        default="wan22_optimized",
        description="Workflow type: wan22_optimized (WAN 2.2 high quality) or animatediff_standard (legacy)"
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