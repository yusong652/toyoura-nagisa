"""
Image-to-video configuration module
Contains configurations related to image-to-video generation using ComfyUI WAN 2.2
"""
from __future__ import annotations
from typing import Literal, Dict, Any
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ImageToVideoSettings(BaseSettings):
    """Image-to-video general configuration"""
    
    # Workflow selection
    workflow_type: Literal["wan22_optimized", "animatediff_standard"] = Field(
        default="wan22_optimized",
        description="Workflow type: wan22_optimized (WAN 2.2 5B high quality) or animatediff_standard (legacy)"
    )
    
    # WAN 2.2 workflow parameters - complete workflow configurations
    wan22_workflows: Dict[str, Dict[str, Any]] = Field(
        default={
            "gentle": {
                "width": 360,
                "height": 640,
                "frames": 25,
                "fps": 16.0,
                "steps": 15,
                "cfg": 4.0
            },
            "dynamic": {
                "width": 360,
                "height": 640,
                "frames": 33,
                "fps": 20.0,
                "steps": 18,
                "cfg": 5.0
            },
            "cinematic": {
                "width": 360,
                "height": 640,
                "frames": 41,
                "fps": 24.0,
                "steps": 20,
                "cfg": 4.5
            },
            "loop": {
                "width": 360,
                "height": 640,
                "frames": 25,
                "fps": 20.0,
                "steps": 15,
                "cfg": 4.0
            }
        },
        description="WAN 2.2 workflow configurations for different motion types"
    )
    
    # System configuration for prompt optimization
    video_prompt_system: str = Field(
        default=(
            "You are an expert at transforming static image prompts into dynamic video prompts for AI video generation. "
            "Your task is to enhance static descriptions with motion, camera movements, and temporal changes while "
            "preserving the core subject and artistic style. Focus on adding cinematic motion descriptions that bring "
            "the scene to life. Always maintain the original subject and composition while adding dynamic elements."
        ),
        description="System prompt for LLM when generating video prompts from image context"
    )
    
    # Context configuration
    context_message_count: int = Field(default=4, ge=1, le=20, description="Context message count")
    
    # Default motion prompts
    default_motion_positive: str = Field(
        default="smooth motion, fluid animation, natural movement, cinematic",
        description="Default positive motion prompt"
    )
    default_motion_negative: str = Field(
        default="static, frozen, stuttering, jittery, abrupt cuts, inconsistent motion",
        description="Default negative motion prompt"
    )
    
    # Motion type presets
    motion_presets: Dict[str, Dict[str, Any]] = Field(
        default={
            "gentle": {
                "motion_scale": 0.5,
                "description": "subtle movement, gentle breeze, slow motion",
                "cfg_scale": 7.0
            },
            "dynamic": {
                "motion_scale": 1.2,
                "description": "dynamic motion, energetic movement, action",
                "cfg_scale": 8.0
            },
            "cinematic": {
                "motion_scale": 1.0,
                "description": "cinematic camera movement, smooth panning, professional",
                "cfg_scale": 7.5
            },
            "loop": {
                "motion_scale": 0.8,
                "description": "seamless loop, cyclic motion, repeating pattern",
                "cfg_scale": 7.0,
                "closed_loop": True
            }
        },
        description="Motion type presets"
    )
    
    # Temperature configuration for video prompt generation
    video_prompt_temperature: float = Field(
        default=0.8,
        ge=0.0,
        le=2.0,
        description="Temperature parameter for video prompt generation (higher values = more creative)"
    )
    
    # Few-shot learning configuration
    video_few_shot_max_length: int = Field(
        default=15,
        ge=0,
        le=32,
        description="Few-shot example maximum count for video prompt generation"
    )
    
    # Server configuration
    server_url: str = Field(
        default="http://localhost:8188/prompt",
        description="ComfyUI server URL with endpoint",
        validation_alias="COMFYUI_SERVER_URL"
    )
    
    # Debug configuration
    debug: bool = Field(default=True, description="Enable debug mode")
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='_',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )


# Global image-to-video configuration instance
def get_image_to_video_settings() -> ImageToVideoSettings:
    """Get image-to-video configuration instance"""
    return ImageToVideoSettings()