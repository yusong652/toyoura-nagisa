"""
Text-to-image configuration module
Contains configurations related to text-to-image generation using ComfyUI
"""
from __future__ import annotations
from typing import Literal, Optional, Dict, Any, List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ComfyUIConfig(BaseSettings):
    """ComfyUI API configuration for text-to-image generation"""
    
    # Server configuration - Use environment variable or update with your server URL
    comfyui_server_url: str = Field(
        default="http://127.0.0.1:8188",  # Example: Local ComfyUI server
        description="ComfyUI server URL (e.g., http://your-server.com or https://your-server.com)",
        validation_alias="COMFYUI_SERVER_URL"
    )
    
    # Client configuration
    client_id: str = Field(
        default="txt2img_client",
        description="Client ID for ComfyUI session tracking"
    )
    
    # Available samplers in ComfyUI
    available_samplers: List[str] = Field(
        default=["euler", "euler_ancestral", "dpmpp_2m", "dpmpp_2m_sde", "dpmpp_3m_sde"],
        description="Available sampler names in ComfyUI"
    )
    
    # Available schedulers
    available_schedulers: List[str] = Field(
        default=["normal", "karras", "exponential", "sgm_uniform", "simple", "ddim_uniform"],
        description="Available scheduler names"
    )
    
    # Generation parameters
    steps: int = Field(default=20, ge=1, le=150, description="Default sampling steps")
    cfg_scale: float = Field(default=7.0, ge=1.0, le=20.0, description="Default CFG scale")
    seed: int = Field(default=-1, description="Random seed (-1 for random)")
    denoise: float = Field(default=1.0, ge=0.0, le=1.0, description="Denoise strength")
    
    # Model preset configurations
    model_presets: Dict[str, Dict[str, Any]] = Field(
        default={
            "anime": {
                "ckpt_name": "animagineXLV31_v30.safetensors",  # Example anime model
                "width": 1024,
                "height": 1536,
                "cfg_scale": 7.0,
                "steps": 20,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0
            },
            "realistic": {
                "ckpt_name": "juggernautXL_v8Rundiffusion.safetensors",  # Example realistic model
                "width": 1024,
                "height": 1024,
                "cfg_scale": 6.5,
                "steps": 25,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 1.0
            },
            "artistic": {
                "ckpt_name": "sdxl_base_1.0.safetensors",  # Example SDXL base model
                "width": 1024,
                "height": 1024,
                "cfg_scale": 7.5,
                "steps": 30,
                "sampler_name": "dpmpp_2m_sde",
                "scheduler": "karras",
                "denoise": 1.0
            }
        },
        description="Model preset configurations for different styles"
    )
    
    # Current active preset
    active_preset: str = Field(
        default="anime",
        description="Currently active model preset"
    )
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='_',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )
    
    def get_current_preset(self) -> Dict[str, Any]:
        """Get current model preset configuration"""
        return self.model_presets.get(self.active_preset, self.model_presets["anime"])
    
    def generate_workflow(self, positive_prompt: str, negative_prompt: str, seed: Optional[int] = None) -> Dict[str, Any]:
        """Generate ComfyUI workflow from preset and prompts"""
        import random
        
        preset = self.get_current_preset()
        
        # Generate random seed if not provided or if -1 is passed
        if seed is None or seed < 0:
            actual_seed = random.randint(1, 2**32 - 1)
        else:
            actual_seed = seed
        
        workflow = {
            "prompt": {
                "3": {
                    "class_type": "KSampler",
                    "inputs": {
                        "seed": actual_seed,
                        "steps": preset.get("steps", 20),
                        "cfg": preset.get("cfg_scale", 7.0),
                        "sampler_name": preset.get("sampler_name", "euler"),
                        "scheduler": preset.get("scheduler", "normal"),
                        "denoise": preset.get("denoise", 1.0),
                        "model": ["4", 0],
                        "positive": ["6", 0],
                        "negative": ["7", 0],
                        "latent_image": ["5", 0]
                    }
                },
                "4": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {
                        "ckpt_name": preset.get("ckpt_name", "sdxl_base_1.0.safetensors")
                    }
                },
                "5": {
                    "class_type": "EmptyLatentImage",
                    "inputs": {
                        "width": preset.get("width", 1024),
                        "height": preset.get("height", 1024),
                        "batch_size": 1
                    }
                },
                "6": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {
                        "text": positive_prompt,
                        "clip": ["4", 1]
                    }
                },
                "7": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {
                        "text": negative_prompt,
                        "clip": ["4", 1]
                    }
                },
                "8": {
                    "class_type": "VAEDecode",
                    "inputs": {
                        "samples": ["3", 0],
                        "vae": ["4", 2]
                    }
                },
                "9": {
                    "class_type": "SaveImage",
                    "inputs": {
                        "filename_prefix": "ComfyUI",
                        "images": ["8", 0]
                    }
                }
            },
            "client_id": self.client_id
        }
        
        return workflow


class TextToImageSettings(BaseSettings):
    """Text-to-image generation configuration"""
    
    # System configuration for prompt optimization
    text_to_image_system_prompt: str = Field(
        default="You are a professional prompt engineer specializing in AI image generation.",
        description="System prompt for LLM-based prompt optimization"
    )
    
    # Context configuration
    context_message_count: int = Field(
        default=6, 
        ge=1, 
        le=50, 
        description="Number of recent messages to include for context"
    )
    
    # Few-shot learning configuration
    few_shot_max_length: int = Field(
        default=23, 
        ge=0, 
        le=32, 
        description="Maximum number of few-shot examples"
    )
    
    # Default prompts for enhancement
    text_to_image_default_positive_prompt: str = Field(
        default="high quality, detailed, masterpiece, best quality",
        description="Default positive prompt to append"
    )
    text_to_image_default_negative_prompt: str = Field(
        default="blurry, low quality, distorted, bad anatomy, text, watermark, ugly, deformed",
        description="Default negative prompt to append"
    )
    
    # Temperature for prompt generation
    text_to_image_temperature: float = Field(
        default=0.8,
        ge=0.0,
        le=2.0,
        description="Temperature for LLM prompt generation (higher = more creative)"
    )
    
    # Debug configuration
    enable_debug: bool = Field(default=True, description="Enable debug logging")
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='_',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )
    
    def get_current_config(self) -> ComfyUIConfig:
        """Get ComfyUI configuration instance"""
        return ComfyUIConfig()
    
    def validate_current_config(self):
        """Validate ComfyUI configuration"""
        try:
            config = self.get_current_config()
            return config
        except Exception as e:
            raise ValueError(f"ComfyUI configuration validation failed: {e}")


# Global configuration instance
def get_text_to_image_settings() -> TextToImageSettings:
    """Get text-to-image configuration instance"""
    return TextToImageSettings()