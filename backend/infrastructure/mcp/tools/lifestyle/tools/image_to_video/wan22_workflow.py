"""
Optimized WAN 2.2 ComfyUI workflow for high-quality image-to-video generation.

Based on the official WAN 2.2 workflow structure to avoid noise-to-image artifacts
and generate proper anime-style videos.
"""
import random
from typing import Dict, Any


def get_wan22_optimized_workflow(
    image_base64: str,
    prompt: str,
    negative_prompt: str,
    width: int = 360,
    height: int = 640,
    video_frames: int = 61,
    fps: float = 15.0,
    seed: int = -1,
    steps: int = 30,
    cfg_scale: float = 5.0
) -> Dict[str, Any]:
    """
    Generate optimized WAN 2.2 ComfyUI workflow for image-to-video generation.
    
    This workflow structure is based on the official WAN 2.2 implementation
    and avoids the noise-to-image artifact by using the correct node sequence.
    
    Args:
        image_base64: Base64 encoded input image
        prompt: Positive prompt for video generation
        negative_prompt: Negative prompt
        width: Video width (recommended: 1280)
        height: Video height (recommended: 704)
        video_frames: Number of frames (recommended: 41-121)
        fps: Frames per second (recommended: 24)
        seed: Random seed (-1 for random)
        steps: Sampling steps (recommended: 30)
        cfg_scale: CFG scale (recommended: 5.0)
    
    Returns:
        Dict containing the complete ComfyUI workflow
    """
    if seed == -1:
        seed = random.randint(0, 2147483647)
    
    # Official WAN 2.2 workflow structure
    workflow = {
        # Load CLIP Text Encoder
        "38": {
            "inputs": {
                "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                "type": "wan",
                "device": "default"
            },
            "class_type": "CLIPLoader",
            "_meta": {
                "title": "CLIPLoader"
            }
        },
        
        # Load WAN 2.2 5B Model
        "37": {
            "inputs": {
                "unet_name": "wan2.2_ti2v_5B_fp16.safetensors",
                "weight_dtype": "default"
            },
            "class_type": "UNETLoader",
            "_meta": {
                "title": "UNETLoader"
            }
        },
        
        # Load VAE
        "39": {
            "inputs": {
                "vae_name": "wan2.2_vae.safetensors"
            },
            "class_type": "VAELoader",
            "_meta": {
                "title": "VAELoader"
            }
        },
        
        # Load Input Image
        "57": {
            "inputs": {
                "image": image_base64,
                "upload": "image"
            },
            "class_type": "LoadImage",
            "_meta": {
                "title": "LoadImage"
            }
        },
        
        # Model Sampling Configuration
        "48": {
            "inputs": {
                "model": ["37", 0],
                "shift": 8.0
            },
            "class_type": "ModelSamplingSD3",
            "_meta": {
                "title": "ModelSamplingSD3"
            }
        },
        
        # Positive Prompt Encoding
        "6": {
            "inputs": {
                "text": prompt,
                "clip": ["38", 0]
            },
            "class_type": "CLIPTextEncode",
            "_meta": {
                "title": "CLIP Text Encode (Positive Prompt)"
            }
        },
        
        # Negative Prompt Encoding
        "7": {
            "inputs": {
                "text": negative_prompt,
                "clip": ["38", 0]
            },
            "class_type": "CLIPTextEncode",
            "_meta": {
                "title": "CLIP Text Encode (Negative Prompt)"
            }
        },
        
        # WAN 2.2 Image to Video Latent (Key Node!)
        "55": {
            "inputs": {
                "vae": ["39", 0],
                "start_image": ["57", 0],
                "width": width,
                "height": height,
                "length": video_frames,
                "batch_size": 1
            },
            "class_type": "Wan22ImageToVideoLatent",
            "_meta": {
                "title": "Wan22ImageToVideoLatent"
            }
        },
        
        # Sampling
        "3": {
            "inputs": {
                "seed": seed,
                "control_after_generate": "randomize",
                "steps": steps,
                "cfg": cfg_scale,
                "sampler_name": "uni_pc",
                "scheduler": "simple",
                "denoise": 1.0,
                "model": ["48", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["55", 0]
            },
            "class_type": "KSampler",
            "_meta": {
                "title": "KSampler"
            }
        },
        
        # Decode Video
        "8": {
            "inputs": {
                "samples": ["3", 0],
                "vae": ["39", 0]
            },
            "class_type": "VAEDecode",
            "_meta": {
                "title": "VAEDecode"
            }
        },
        
        # Save as WEBM Video
        "47": {
            "inputs": {
                "images": ["8", 0],
                "filename_prefix": "wan22_i2v_optimized",
                "codec": "vp9",
                "fps": fps,
                "crf": 16.111083984375
            },
            "class_type": "SaveWEBM",
            "_meta": {
                "title": "SaveWEBM"
            }
        }
    }
    
    return workflow


def get_wan22_high_quality_workflow(
    image_base64: str,
    prompt: str,
    negative_prompt: str
) -> Dict[str, Any]:
    """
    Get high-quality WAN 2.2 workflow with parameters from config.
    
    All parameters are read from the configuration file to ensure consistency
    and avoid hardcoded values.
    
    Args:
        image_base64: Base64 encoded input image
        prompt: Positive prompt for video generation
        negative_prompt: Negative prompt
    
    Returns:
        Dict containing the optimized workflow
    """
    # Import config inside function to avoid circular import
    from backend.config.image_to_video import get_image_to_video_settings
    
    settings = get_image_to_video_settings()
    
    # Use unified configuration from settings
    # Default resolution for WAN 2.2 optimal performance
    width = getattr(settings, 'width', 640)
    height = getattr(settings, 'height', 960)
    
    # Get sampling parameters with sensible defaults
    steps = getattr(settings, 'steps', 20)
    cfg_scale = getattr(settings, 'cfg', 4.5)
    
    return get_wan22_optimized_workflow(
        image_base64=image_base64,
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        video_frames=settings.frame_count,
        fps=float(settings.fps),
        seed=settings.seed,
        steps=steps,
        cfg_scale=cfg_scale
    )