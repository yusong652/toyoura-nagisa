"""
Text-to-image configuration module
Contains configurations related to text-to-image generation
"""
from __future__ import annotations
from typing import Literal, Optional, Dict, Any, List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict



class ComfyUIWorkflowNode(BaseSettings):
    """ComfyUI workflow node configuration"""
    
    class_type: str = Field(description="Node class type")
    inputs: Dict[str, Any] = Field(description="Node inputs")
    
    model_config = SettingsConfigDict(extra='allow')


class ComfyUIModelPreset(BaseSettings):
    """ComfyUI model preset configuration"""
    
    ckpt_name: str = Field(description="Checkpoint model filename")
    width: int = Field(ge=64, le=2048, description="Image width")
    height: int = Field(ge=64, le=2048, description="Image height")
    cfg_scale: float = Field(ge=1.0, le=20.0, description="CFG scale")
    steps: int = Field(ge=1, le=150, description="Sampling steps")
    sampler_name: str = Field(description="Sampler name")
    scheduler: str = Field(description="Scheduler name")
    denoise: float = Field(ge=0.0, le=1.0, description="Denoise strength")
    
    model_config = SettingsConfigDict(extra='allow')


class ComfyUIConfig(BaseSettings):
    """ComfyUI API configuration"""
    
    # Server configuration
    comfyui_server_url: str = Field(
        default="http://127.0.0.1:8188",
        description="ComfyUI server URL",
        validation_alias="COMFYUI_SERVER_URL"
    )
    
    # Available samplers
    available_samplers: List[str] = Field(
        default=["euler", "euler_ancestral", "dpmpp_2m", "dpmpp_2m_sde", "dpmpp_3m_sde"],
        description="Available sampler names"
    )
    
    # Available schedulers
    available_schedulers: List[str] = Field(
        default=["normal", "karras", "exponential", "simple", "ddim_uniform"],
        description="Available scheduler names"
    )
    
    # Available checkpoints
    available_checkpoints: List[str] = Field(
        default=[
            "hassakuXLIllustrious_v30.safetensors",
            "novaAnimeXL_ilV90.safetensors",
            "waiNSFWIllustrious_v140.safetensors",
            "JANKUV4NSFWTrainedNoobaiEPS_v40.safetensors",
            "sd_xl_base_1.0.safetensors"
        ],
        description="Available checkpoint models"
    )
    
    # Model configuration
    model_type: Literal["hassaku", "nova", "janku", "wai"] = Field(
        default="nova",
        description="Model type preset"
    )
    debug: bool = Field(default=True, description="Enable debug mode")
    
    # Default generation parameters
    default_seed: int = Field(default=-1, description="Default random seed")
    client_id: str = Field(default="ainagisa_client", description="ComfyUI client ID")
    return_base64: bool = Field(default=True, description="Return images as base64")
    
    # Model preset configurations
    model_presets: Dict[str, Dict[str, Any]] = Field(
        default={
            "hassaku": {
                "ckpt_name": "hassakuXLIllustrious_v30.safetensors",
                "width": 1024,
                "height": 1536,
                "cfg_scale": 7.5,
                "steps": 24,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0
            },
            "nova": {
                "ckpt_name": "novaAnimeXL_ilV90.safetensors",
                "width": 1024,
                "height": 1536,
                "cfg_scale": 6.5,  # 提高CFG以增强prompt遵循度
                "steps": 52,  # 增加步数提升细节质量
                "sampler_name": "dpmpp_2m_sde",  # 更适合动漫风格的采样器
                "scheduler": "karras",  # Karras调度器通常效果更好
                "denoise": 1.0
            },
            "janku": {
                "ckpt_name": "JANKUV4NSFWTrainedNoobaiEPS_v40.safetensors",
                "width": 1024,
                "height": 1536,
                "cfg_scale": 7.0,
                "steps": 28,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0
            },
            "wai": {
                "ckpt_name": "waiNSFWIllustrious_v140.safetensors",
                "width": 1024,
                "height": 1536,
                "cfg_scale": 6.0,
                "steps": 23,
                "sampler_name": "euler",
                "scheduler": "karras",
                "denoise": 1.0
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
        print(f"[DEBUG] ComfyUIConfig initialization:")
        print(f"[DEBUG] - Environment variable COMFYUI_SERVER_URL: {os.environ.get('COMFYUI_SERVER_URL', 'NOT_SET')}")
        super().__init__(**kwargs)
        print(f"[DEBUG] - Final config server_url: {self.comfyui_server_url}")
        print(f"[DEBUG] - Final config debug: {self.debug}")
    
    def get_current_preset(self) -> Dict[str, Any]:
        """Get current model preset"""
        return self.model_presets.get(self.model_type, {})
    
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
                        "steps": preset.get("steps", 30),
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
                        "ckpt_name": preset.get("ckpt_name", "sd_xl_base_1.0.safetensors")
                    }
                },
                "5": {
                    "class_type": "EmptyLatentImage",
                    "inputs": {
                        "width": preset.get("width", 1024),
                        "height": preset.get("height", 1536),
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
                        "filename_prefix": "aiNagisa",
                        "images": ["8", 0]
                    }
                }
            },
            "client_id": self.client_id,
            "return_base64": self.return_base64
        }
        
        return workflow


class TextToImageSettings(BaseSettings):
    """Text-to-image general configuration"""
    
    # System configuration
    text_to_image_system_prompt: str = Field(
        default="You are a professional prompt engineer specializing in AI image generation.",
        description="System prompt"
    )
    context_message_count: int = Field(default=23, ge=1, le=50, description="Context message count")
    
    # Few-shot learning configuration
    few_shot_max_length: int = Field(default=2, ge=0, le=32, description="Few-shot example maximum count")
    
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
        default=0.7,
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
    
    
    def get_current_config(self) -> ComfyUIConfig:
        """Get ComfyUI configuration"""
        return ComfyUIConfig()
    
    def validate_current_config(self):
        """Validate ComfyUI configuration - implements fail fast"""
        try:
            config = self.get_current_config()
            # This will trigger configuration validation
            return config
        except Exception as e:
            raise ValueError(f"ComfyUI configuration validation failed: {e}")


# Global text-to-image configuration instance
def get_text_to_image_settings() -> TextToImageSettings:
    """Get text-to-image configuration instance"""
    return TextToImageSettings() 