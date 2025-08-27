"""
Image-to-video configuration module
Contains configurations related to image-to-video generation using AnimateDiff
"""
from __future__ import annotations
from typing import Literal, Optional, Dict, Any
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AnimateDiffConfig(BaseSettings):
    """AnimateDiff WebUI configuration"""
    
    # Server configuration
    server_url: str = Field(
        default="http://127.0.0.1:7860",
        description="AnimateDiff WebUI server URL",
        validation_alias="ANIMATEDIFF_WEBUI_URL"
    )
    
    # API endpoints
    img2vid_endpoint: str = Field(
        default="/sdapi/v1/img2img",
        description="Image-to-video API endpoint"
    )
    
    # Video generation parameters
    fps: int = Field(default=8, ge=1, le=30, description="Frames per second")
    frame_count: int = Field(default=16, ge=8, le=32, description="Number of frames to generate")
    motion_module: str = Field(
        default="mm_sd_v15_v2.ckpt",
        description="Motion module checkpoint"
    )
    
    # Generation parameters (inherited from SD)
    steps: int = Field(default=20, ge=1, le=150, description="Sampling steps")
    sampler_name: str = Field(default="DPM++ 2M Karras", description="Sampler name")
    cfg_scale: float = Field(default=7.0, ge=1.0, le=20.0, description="CFG scale")
    denoising_strength: float = Field(default=0.75, ge=0.0, le=1.0, description="Denoising strength for img2img")
    seed: int = Field(default=-1, description="Random seed")
    
    # Motion parameters
    motion_scale: float = Field(default=1.0, ge=0.0, le=2.0, description="Motion intensity scale")
    context_overlap: int = Field(default=4, ge=0, le=8, description="Context frame overlap")
    closed_loop: bool = Field(default=False, description="Enable closed loop animation")
    
    # Output configuration
    output_format: Literal["gif", "mp4", "webm"] = Field(
        default="mp4",
        description="Output video format"
    )
    video_quality: int = Field(default=95, ge=1, le=100, description="Video quality (1-100)")
    
    # Debug configuration
    debug: bool = Field(default=True, description="Enable debug mode")
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='_',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )
    
    def __init__(self, **kwargs):
        """Initialize configuration with debug information"""
        import os
        if kwargs.get('debug', True):
            print(f"[DEBUG] AnimateDiffConfig initialization:")
            print(f"[DEBUG] - Environment variable ANIMATEDIFF_WEBUI_URL: {os.environ.get('ANIMATEDIFF_WEBUI_URL', 'NOT_SET')}")
        super().__init__(**kwargs)
        if self.debug:
            print(f"[DEBUG] - Final config server_url: {self.server_url}")
            print(f"[DEBUG] - Final config fps: {self.fps}, frames: {self.frame_count}")


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
    
    # Temperature for prompt generation
    video_prompt_temperature: float = Field(
        default=0.8,
        ge=0.0,
        le=2.0,
        description="Temperature for video prompt generation"
    )
    
    # Debug configuration
    enable_debug: bool = Field(default=True, description="Enable debug mode")
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='_',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )
    
    def get_animatediff_config(self) -> AnimateDiffConfig:
        """Get AnimateDiff configuration"""
        return AnimateDiffConfig()
    
    def validate_config(self):
        """Validate AnimateDiff configuration"""
        try:
            config = self.get_animatediff_config()
            return config
        except Exception as e:
            raise ValueError(f"AnimateDiff configuration validation failed: {e}")


# Global image-to-video configuration instance
def get_image_to_video_settings() -> ImageToVideoSettings:
    """Get image-to-video configuration instance"""
    return ImageToVideoSettings()