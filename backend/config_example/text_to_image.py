"""
Text-to-image configuration module
Contains configurations related to text-to-image generation
"""
from __future__ import annotations
from typing import Literal, Optional, Dict, Any
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict



class ModelPreset(BaseSettings):
    """Model preset configuration"""
    
    sd_model_checkpoint: str = Field(description="Stable Diffusion model checkpoint")
    sd_vae: str = Field(description="VAE model")
    width: int = Field(ge=64, le=2048, description="Image width")
    height: int = Field(ge=64, le=2048, description="Image height")
    cfg_scale: float = Field(ge=1.0, le=20.0, description="CFG scale")
    clip_skip: int = Field(ge=1, le=12, description="CLIP skip layers")
    sampler_name: str = Field(description="Sampler name")
    
    model_config = SettingsConfigDict(extra='allow')


class StableDiffusionWebUIConfig(BaseSettings):
    """Stable Diffusion WebUI configuration"""
    
    # Server configuration
    server_url: str = Field(
        default="http://127.0.0.1:7860/sdapi/v1/txt2img",
        description="Stable Diffusion WebUI server URL",
        validation_alias="STABLE_DIFFUSION_WEBUI_URL"
    )
    
    # Generation parameters
    steps: int = Field(default=23, ge=1, le=150, description="Sampling steps")  # Increased to avoid undersampling
    sampler_name: str = Field(default="DPM++ 2M Karras", description="Sampler name")
    cfg_scale: float = Field(default=6.5, ge=1.0, le=20.0, description="CFG scale")
    seed: int = Field(default=-1, description="Random seed")
    
    # High-resolution fix configuration
    enable_hr: bool = Field(default=False, description="Enable high-resolution fix")
    hr_scale: float = Field(default=2.0, ge=1.0, le=4.0, description="High-resolution scale")
    hr_upscaler: str = Field(default="4x-UltraSharp", description="High-resolution upscaler")
    denoising_strength: float = Field(default=0.5, ge=0.0, le=1.0, description="Denoising strength")
    
    # Model configuration
    model_type: Literal["illustrious", "sdxl", "sd15"] = Field(
        default="illustrious",
        description="Model type preset"
    )
    debug: bool = Field(default=True, description="Enable debug mode")
    
    # Model preset configurations
    model_presets: Dict[str, Dict[str, Any]] = Field(
        default={
            "illustrious": {
                "sd_model_checkpoint": "illustriousXLPersonalMerge_v10.safetensors",
                "sd_vae": "sdxl_vae.safetensors",
                "width": 1024,
                "height": 1536,
                "cfg_scale": 7.0,
                "clip_skip": 2,
                "sampler_name": "Euler a"
            },
            "sdxl": {
                "sd_model_checkpoint": "sd_xl_base_1.0.safetensors",
                "sd_vae": "sdxl_vae.safetensors",
                "width": 1024,
                "height": 1536,
                "cfg_scale": 6.0,
                "clip_skip": 2,
                "sampler_name": "DPM++ 2M Karras"
            },
            "sd15": {
                "sd_model_checkpoint": "v1-5-pruned-emaonly.safetensors",
                "sd_vae": "vae-ft-mse-840000-ema-pruned.safetensors",  # Try "None" or "Automatic" if generating noise
                "width": 512,
                "height": 768,
                "cfg_scale": 6.5,  # Lower CFG to avoid over-guidance, try 5.0-8.0 range
                "clip_skip": 1,
                "sampler_name": "DPM++ 2M Karras"  # More stable sampler, replaces DPM++ SDE Karras
            }
        },
        description="Model preset configurations"
    )
    
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
        print(f"[DEBUG] StableDiffusionWebUIConfig initialization:")
        print(f"[DEBUG] - Environment variable STABLE_DIFFUSION_WEBUI_URL: {os.environ.get('STABLE_DIFFUSION_WEBUI_URL', 'NOT_SET')}")
        super().__init__(**kwargs)
        print(f"[DEBUG] - Final config server_url: {self.server_url}")
        print(f"[DEBUG] - Final config debug: {self.debug}")
    
    def get_current_preset(self) -> Dict[str, Any]:
        """Get current model preset"""
        return self.model_presets.get(self.model_type, {})


class TextToImageSettings(BaseSettings):
    """Text-to-image general configuration"""
    
    # System configuration
    text_to_image_system_prompt: str = Field(
        default="You are a professional prompt engineer specializing in AI image generation.",
        description="System prompt"
    )
    context_message_count: int = Field(default=6, ge=1, le=50, description="Context message count")
    
    # Few-shot learning configuration
    few_shot_max_length: int = Field(default=23, ge=0, le=32, description="Few-shot example maximum count")
    
    # Default prompt configuration
    text_to_image_default_positive_prompt: str = Field(
        default="high quality, detailed, masterpiece, best quality",
        description="Default positive prompt"
    )
    text_to_image_default_negative_prompt: str = Field(
        default="blurry, low quality, distorted, bad anatomy, text, watermark, ugly, deformed",
        description="Default negative prompt"
    )
    
    # Temperature configuration for text-to-image prompt generation
    text_to_image_temperature: float = Field(
        default=2.0,
        ge=0.0,
        le=2.0,
        description="Temperature parameter for text-to-image prompt generation"
    )
    
    # Debug configuration
    enable_debug: bool = Field(default=True, description="Enable debug mode")
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='_',
        case_sensitive=False,
        env_prefix='',  # Remove prefix!
        extra='ignore'
    )
    
    
    def get_current_config(self) -> StableDiffusionWebUIConfig:
        """Get Stable Diffusion WebUI configuration"""
        return StableDiffusionWebUIConfig()
    
    def validate_current_config(self):
        """Validate Stable Diffusion WebUI configuration - implements fail fast"""
        try:
            config = self.get_current_config()
            # This will trigger configuration validation
            return config
        except Exception as e:
            raise ValueError(f"Stable Diffusion WebUI configuration validation failed: {e}")


# Global text-to-image configuration instance
def get_text_to_image_settings() -> TextToImageSettings:
    """Get text-to-image configuration instance"""
    return TextToImageSettings()