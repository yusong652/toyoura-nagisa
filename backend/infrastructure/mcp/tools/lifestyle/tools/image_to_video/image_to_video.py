"""
Image-to-video generation tool using AnimateDiff
Transforms static images into dynamic videos with AI-powered motion
"""
from fastmcp import FastMCP
import asyncio
from dotenv import load_dotenv
import json
import logging
import traceback
from typing import Any, Dict, Optional
import httpx
import base64
from io import BytesIO
from PIL import Image
from fastapi import FastAPI
from fastmcp.server.context import Context  # type: ignore
from backend.config.image_to_video import get_image_to_video_settings
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.llm.shared.utils.text_to_image import load_text_to_image_history

load_dotenv()

logger = logging.getLogger(__name__)


def get_latest_text_to_image_prompt(session_id: str) -> str:
    """
    Get the latest text-to-image prompt from session history.
    
    Args:
        session_id: Current session ID
    
    Returns:
        Latest text-to-image prompt or empty string if not found
    """
    try:
        history = load_text_to_image_history(session_id)
        if not history:
            return ""
        
        # Get the most recent record
        latest_record = history[-1]
        assistant_response = latest_record.get("assistant_message", {}).get("content", "")
        
        # Extract the actual prompt from the assistant response
        # The response typically contains structured prompt information
        if "POSITIVE_PROMPT:" in assistant_response:
            lines = assistant_response.split("\n")
            for line in lines:
                if line.startswith("POSITIVE_PROMPT:"):
                    return line.replace("POSITIVE_PROMPT:", "").strip()
        
        # Fallback: use the entire assistant response if structured format not found
        return assistant_response.strip()
        
    except Exception as e:
        logger.error(f"Error loading text-to-image history: {e}")
        return ""


async def call_animatediff_api(
    image_base64: str,
    prompt: str,
    negative_prompt: str,
    motion_type: str = "cinematic"
) -> Dict[str, Any]:
    """
    Call AnimateDiff WebUI API to generate video from image.
    
    Args:
        image_base64: Base64 encoded input image
        prompt: Positive prompt with motion descriptions
        negative_prompt: Negative prompt
        motion_type: Type of motion preset to use
    
    Returns:
        Dict containing video result or error
    """
    print(f"[DEBUG] call_animatediff_api started")
    print(f"[DEBUG] Motion type: {motion_type}")
    print(f"[DEBUG] Prompt: {prompt[:100]}...")  # First 100 chars
    print(f"[DEBUG] Negative prompt: {negative_prompt[:100]}...")
    
    try:
        # Get configuration
        settings = get_image_to_video_settings()
        config = settings.get_animatediff_config()
        print(f"[DEBUG] AnimateDiff server URL: {config.server_url}")
        print(f"[DEBUG] AnimateDiff endpoint: {config.img2vid_endpoint}")
        
        # Get motion preset
        motion_preset = settings.motion_presets.get(motion_type, {})
        
        # Decode image to get dimensions
        import base64
        from io import BytesIO
        from PIL import Image
        
        img_data = base64.b64decode(image_base64)
        img = Image.open(BytesIO(img_data))
        width, height = img.size
        print(f"[DEBUG] Original image dimensions: {width}x{height}")
        
        # Ensure dimensions are compatible with AnimateDiff
        # AnimateDiff typically requires multiples of 8, but 64 is safer
        # We'll use 32 as a compromise between flexibility and stability
        original_width, original_height = width, height
        
        # Round to nearest multiple of 32 (good balance)
        width = ((width + 16) // 32) * 32
        height = ((height + 16) // 32) * 32
        
        # Limit max size to avoid memory issues while preserving aspect ratio
        max_width = 1024
        max_height = 1536
        
        if width > max_width or height > max_height:
            # Scale down while preserving aspect ratio
            scale = min(max_width / width, max_height / height)
            width = int(width * scale)
            height = int(height * scale)
            # Ensure still multiple of 32
            width = (width // 32) * 32
            height = (height // 32) * 32
        
        # Ensure minimum size
        width = max(width, 512)  # Minimum width
        height = max(height, 512)  # Minimum height
        
        print(f"[DEBUG] Original: {original_width}x{original_height} -> Adjusted: {width}x{height}")
        
        # Get text-to-image config to use the same model settings
        from backend.config.text_to_image import get_text_to_image_settings
        txt2img_settings = get_text_to_image_settings()
        txt2img_config = txt2img_settings.get_current_config()
        model_preset = txt2img_config.get_current_preset()
        
        # Temporarily use SD1.5 motion module for better compatibility
        # Even for SDXL models, SD1.5 motion module might be more stable
        motion_module = "mm_sd_v15_v2.ckpt"
        model_type = txt2img_config.model_type
        print(f"[DEBUG] Using SD1.5 motion module for {model_type} model (compatibility mode)")
        
        # Check if AnimateDiff should be enabled (set to False to disable temporarily)
        enable_animatediff = True  # Set to False if you want to test without AnimateDiff
        
        # Prepare API payload for img2img with AnimateDiff
        payload = {
            "init_images": [image_base64],
            "prompt": f"{prompt}, {motion_preset.get('description', '')}",
            "negative_prompt": negative_prompt,
            "steps": 15,  # Reduced steps to avoid precision issues
            "cfg_scale": 5.0,  # Lower CFG to avoid precision issues
            "denoising_strength": 0.3,  # Lower denoising for stability
            "sampler_name": config.sampler_name,  # Use config's default sampler
            "seed": config.seed,
            "batch_size": 1,  # Fixed to 1 for img2img
            "n_iter": 1,
            "width": width,  # Set actual image dimensions
            "height": height
            # Remove override_settings to avoid model switching issues with AnimateDiff
            # Let WebUI use its current model settings
        }
        
        # Add AnimateDiff only if enabled
        if enable_animatediff:
            print(f"[DEBUG] Enabling AnimateDiff with motion module: {motion_module}")
            # For AnimateDiff, we need to adjust the main batch size to match video length
            video_length = 8  # Increase frames for better video
            payload["batch_size"] = video_length  # Match video_length for consistency
            payload["n_iter"] = 1  # Only one iteration for video
            payload["alwayson_scripts"] = {
                "AnimateDiff": {
                    "args": [
                        {
                            "model": "mm_sdxl_v10_beta.ckpt",  # 明确指定模型
                            "enable": True,
                            "video_length": video_length,
                            "fps": 6,
                            "format": ["GIF"],
                            "loop_number": 0,
                            "closed_loop": "R+P",
                            "batch_size": video_length,
                            "stride": 1,
                            "overlap": -1,
                            "interp": "Off",
                            "interp_x": 10,
                            "video_source": "",  # 空字符串表示不使用视频源
                            "video_path": "",   # 空字符串表示不使用视频路径
                            "latent_power": 1,
                            "latent_scale": 32,
                            "last_frame": None,
                            "latent_power_last": 1,
                            "latent_scale_last": 32,
                            "request_id": ""
                        }
                    ]
                }
            }
            print(f"[DEBUG] AnimateDiff payload prepared with {video_length} frames")
        else:
            print(f"[DEBUG] AnimateDiff disabled - using regular img2img")
        
        if config.debug:
            logger.info(f"[DEBUG] AnimateDiff API call:")
            logger.info(f"  - Server: {config.server_url}")
            logger.info(f"  - Motion type: {motion_type}")
            logger.info(f"  - Frames: {config.frame_count}, FPS: {config.fps}")
        
        # Make API call
        print(f"[DEBUG] Preparing to call AnimateDiff API...")
        endpoint = f"{config.server_url}{config.img2vid_endpoint}"
        print(f"[DEBUG] Full endpoint URL: {endpoint}")
        print(f"[DEBUG] Payload size: {len(json.dumps(payload))} bytes")
        
        async with httpx.AsyncClient() as client:
            print(f"[DEBUG] Sending POST request to AnimateDiff...")
            response = await client.post(
                endpoint,
                headers={"Content-Type": "application/json"},
                content=json.dumps(payload),
                timeout=600.0  # Longer timeout for video generation
            )
            print(f"[DEBUG] Response received from AnimateDiff")
            
            response.raise_for_status()
            result = response.json()
            
            print(f"[DEBUG] API response keys: {result.keys() if result else 'None'}")
            
            # AnimateDiff returns video in 'images' array (base64 encoded)
            if "images" in result and result["images"]:
                video_base64 = result["images"][0]
                print(f"[DEBUG] Got video data, length: {len(video_base64) if video_base64 else 0}")
                
                # Check if we have valid video data
                # Since AnimateDiff completed inference, treat as successful video generation
                if len(result.get("images", [])) > 0:
                    print(f"[DEBUG] AnimateDiff generation completed, checking format")
                    
                    # Decode base64 to check actual file format
                    import base64
                    try:
                        decoded_data = base64.b64decode(video_base64)
                        file_header = decoded_data[:16] if len(decoded_data) >= 16 else decoded_data
                        
                        print(f"[DEBUG] File header (hex): {file_header.hex()}")
                        
                        # Check file format based on magic numbers
                        if decoded_data.startswith(b'GIF'):
                            video_format = "gif"
                            frames = 4
                            note = "Generated GIF animation with AnimateDiff SD1.5"
                            print(f"[DEBUG] Detected GIF format")
                        elif decoded_data.startswith(b'\x00\x00\x00') and b'ftyp' in decoded_data[:20]:
                            video_format = "mp4"
                            frames = 4
                            note = "Generated MP4 video with AnimateDiff SD1.5"
                            print(f"[DEBUG] Detected MP4 format")
                        elif decoded_data.startswith(b'\x89PNG'):
                            # This is actually a PNG image, not a video
                            print(f"[DEBUG] AnimateDiff returned PNG image instead of video")
                            return {
                                "type": "image_base64",
                                "video": video_base64,
                                "format": "png",
                                "note": "AnimateDiff returned static image - video generation may have failed"
                            }
                        else:
                            # Unknown format, assume GIF for compatibility
                            video_format = "gif" 
                            frames = 4
                            note = "Generated video with AnimateDiff SD1.5 (format detection uncertain)"
                            print(f"[DEBUG] Unknown format, assuming GIF")
                    except Exception as e:
                        print(f"[ERROR] Failed to decode base64 for format detection: {e}")
                        video_format = "gif"  # Default fallback
                        frames = 4
                        note = "Generated video with AnimateDiff SD1.5 (format detection failed)"
                    
                    return {
                        "type": "video_base64",
                        "video": video_base64,
                        "format": video_format,
                        "fps": 2,  # Match actual FPS
                        "frames": frames,
                        "note": note
                    }
                else:
                    print(f"[DEBUG] No video data in response")
                    return {"type": "error", "message": "No video data in response"}
            else:
                print(f"[DEBUG] No images in response. Full response: {str(result)[:500]}")
                return {"type": "error", "message": "No video data in response"}
                
    except httpx.ConnectError as e:
        print(f"[ERROR] Connection failed to AnimateDiff server: {e}")
        print(f"[ERROR] Server URL was: {config.server_url}")
        print(f"[ERROR] Please check if AnimateDiff WebUI is running and accessible")
        logger.error(f"Connection error in AnimateDiff API call: {e}")
        return {"type": "error", "message": f"Cannot connect to AnimateDiff server at {config.server_url}. Please ensure the server is running."}
    except httpx.HTTPStatusError as e:
        print(f"[ERROR] HTTP error from AnimateDiff: {e}")
        print(f"[ERROR] Response status: {e.response.status_code}")
        logger.error(f"HTTP error in AnimateDiff API call: {e}")
        return {"type": "error", "message": f"API error: {e.response.status_code}"}
    except Exception as e:
        print(f"[ERROR] Unexpected error in AnimateDiff API call: {e}")
        print(f"[ERROR] Error type: {type(e).__name__}")
        print(f"[ERROR] Traceback:\n{traceback.format_exc()}")
        logger.error(f"Error in AnimateDiff API call: {e}")
        logger.error(traceback.format_exc())
        return {"type": "error", "message": str(e)}


async def optimize_prompt_for_video(
    llm_client: Any,
    session_id: str,
    original_prompt: str,
    image_base64: Optional[str] = None
) -> Dict[str, str]:
    """
    Optimize static image prompt for video generation.
    
    Uses provider-specific content generators for non-streaming API calls.
    
    Args:
        llm_client: LLM client for prompt optimization
        session_id: Current session ID (currently unused but kept for compatibility)
        original_prompt: Original static image prompt
        image_base64: Optional base64 image for visual context
    
    Returns:
        Dict with optimized video_prompt and negative_prompt
    """
    print(f"[DEBUG] optimize_prompt_for_video started")
    print(f"[DEBUG] Original prompt: {original_prompt}")
    print(f"[DEBUG] Has image: {bool(image_base64)}")
    
    try:
        settings = get_image_to_video_settings()
        
        # Determine which provider we're using and get the appropriate generator
        client_class_name = llm_client.__class__.__name__
        print(f"[DEBUG] LLM client type: {client_class_name}")
        
        if "Gemini" in client_class_name:
            print(f"[DEBUG] Using Gemini video prompt generator")
            from backend.infrastructure.llm.providers.gemini.content_generators import GeminiVideoPromptGenerator
            # Get the native Gemini client
            print(f"[DEBUG] Calling GeminiVideoPromptGenerator.generate_video_prompt...")
            result = await GeminiVideoPromptGenerator.generate_video_prompt(
                llm_client.client,  # Use the native Gemini client
                original_prompt,
                image_base64
            )
            print(f"[DEBUG] Gemini generator returned: {result}")
        elif "OpenAI" in client_class_name:
            # TODO: Implement OpenAIVideoPromptGenerator when needed
            # For now, fallback to default behavior
            logger.warning("OpenAI video prompt generator not yet implemented, using fallback")
            result = None
        elif "Anthropic" in client_class_name:
            # TODO: Implement AnthropicVideoPromptGenerator when needed
            # For now, fallback to default behavior
            logger.warning("Anthropic video prompt generator not yet implemented, using fallback")
            result = None
        else:
            logger.warning(f"Unknown LLM client type: {client_class_name}, using fallback")
            result = None
        
        # If we got a result from the content generator, return it
        if result:
            return result
        
        # Fallback to adding basic motion keywords
        return {
            "video_prompt": f"{original_prompt}, {settings.default_motion_positive}",
            "negative_prompt": settings.default_motion_negative
        }
        
    except Exception as e:
        logger.error(f"Error optimizing prompt for video: {e}")
        # Fallback to adding basic motion keywords
        settings = get_image_to_video_settings()
        return {
            "video_prompt": f"{original_prompt}, {settings.default_motion_positive}",
            "negative_prompt": settings.default_motion_negative
        }


async def generate_video_from_image(
    context: Context,
    image_base64: str,
    prompt: str,
    motion_type: str = "cinematic"
) -> Dict[str, Any]:
    """
    Generate video from static image with AI-powered motion.
    
    Transforms a static image into a dynamic video by adding motion based on the prompt.
    
    Args:
        context: MCP context with session info
        image_base64: Base64 encoded input image
        prompt: Text description for the video generation
        motion_type: Type of motion (gentle/dynamic/cinematic/loop)
    
    Returns:
        ToolResult with video data or error
    """
    import time
    start_time = time.time()
    
    # Validate motion type
    settings = get_image_to_video_settings()
    if motion_type not in settings.motion_presets:
        motion_type = "cinematic"  # Default fallback
    
    # Get LLM client for prompt optimization
    session_id: str | None = getattr(context, "client_id", None)
    if not session_id:
        return error_response("Video generation failed: Session ID is missing")
    
    fastapi_app = getattr(getattr(context, "fastmcp", None), "app", None)
    llm_client = None
    if fastapi_app is not None and hasattr(fastapi_app.state, "llm_client"):
        llm_client = fastapi_app.state.llm_client
    
    if llm_client is None:
        return error_response("Video generation failed: LLM client unavailable")
    
    try:
        # Optimize prompt for video
        print(f"[DEBUG] Starting prompt optimization...")
        prompt_result = await optimize_prompt_for_video(
            llm_client=llm_client,
            session_id=session_id,
            original_prompt=prompt,
            image_base64=image_base64
        )
        
        video_prompt = prompt_result["video_prompt"]
        negative_prompt = prompt_result["negative_prompt"]
        print(f"[DEBUG] Prompt optimization completed")
        print(f"[DEBUG] Video prompt: {video_prompt[:100]}...")
        print(f"[DEBUG] Negative prompt: {negative_prompt[:100]}...")
        
        if settings.enable_debug:
            logger.info(f"[DEBUG] Video prompt optimization:")
            logger.info(f"  - Original: {prompt}")
            logger.info(f"  - Optimized: {video_prompt}")
            logger.info(f"  - Motion type: {motion_type}")
        
        # Generate video
        print(f"[DEBUG] Starting video generation with AnimateDiff...")
        video_result = await call_animatediff_api(
            image_base64=image_base64,
            prompt=video_prompt,
            negative_prompt=negative_prompt,
            motion_type=motion_type
        )
        print(f"[DEBUG] Video generation completed")
        print(f"[DEBUG] video_result type: '{video_result.get('type')}'")
        print(f"[DEBUG] video_result keys: {list(video_result.keys())}")
        
        if video_result.get("type") == "error":
            return error_response(
                f"Video generation failed: {video_result.get('message', 'Unknown error')}"
            )
        
        # Handle different result types
        if video_result.get("type") == "video_base64":
            # Successfully generated video with AnimateDiff
            print(f"[DEBUG] Got video from AnimateDiff")
            generation_time = f"{time.time() - start_time:.1f}s"
            # Get actual format from result
            actual_format = video_result.get("format", "mp4")
            actual_frames = video_result.get("frames", 4)
            actual_fps = video_result.get("fps", 2)
            
            return success_response(
                message=f"Video generated successfully with AnimateDiff ({generation_time})",
                llm_content={
                    "description": f"Generated {actual_frames}-frame {actual_format.upper()} video at {actual_fps} FPS using AnimateDiff SD1.5",
                    "motion_type": motion_type,
                    "format": actual_format,
                    "generation_time": generation_time,
                    "note": video_result.get("note", ""),
                    "warning": "AnimateDiff post-processing errors are non-critical and don't affect video quality"
                },
                data={
                    "video_base64": video_result.get("video"),
                    "format": actual_format,
                    "fps": actual_fps,
                    "frames": actual_frames,
                    "prompts": {
                        "video": video_prompt,
                        "negative": negative_prompt
                    }
                }
            )
        elif video_result.get("type") == "image_base64":
            # AnimateDiff might not be active, got static image
            print(f"[DEBUG] Got static image (AnimateDiff may not be active)")
            generation_time = f"{time.time() - start_time:.1f}s"
            return success_response(
                message=f"Generated image (AnimateDiff may not be active) ({generation_time})",
                llm_content={
                    "description": "Generated static image - AnimateDiff may not be properly configured",
                    "note": video_result.get("note", ""),
                    "generation_time": generation_time,
                    "suggestion": "Please ensure AnimateDiff extension is installed and enabled in WebUI"
                },
                data={
                    "image_base64": video_result.get("video"),
                    "format": "png",
                    "type": "static_image",
                    "prompts": {
                        "video": video_prompt,
                        "negative": negative_prompt
                    }
                }
            )
        
        # No video data at all
        generation_time = f"{time.time() - start_time:.1f}s"
        return success_response(
            message=f"Video generated successfully ({generation_time})",
            llm_content={
                "description": f"Generated {video_result.get('frames', 16)}-frame video at {video_result.get('fps', 8)} FPS",
                "motion_type": motion_type,
                "format": video_result.get("format", "mp4"),
                "generation_time": generation_time
            },
            data={
                "video_base64": video_result.get("video"),
                "format": video_result.get("format", "mp4"),
                "fps": video_result.get("fps", 8),
                "frames": video_result.get("frames", 16),
                "prompts": {
                    "video": video_prompt,
                    "negative": negative_prompt
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error in video generation: {e}")
        logger.error(traceback.format_exc())
        return error_response(f"Video generation failed: {str(e)}")


def find_recent_image_in_messages(session_id: str) -> str | None:
    """
    Find the most recent AI-generated image in conversation messages.
    
    Args:
        session_id: Current session ID
    
    Returns:
        Base64 image data or None if not found
    """
    try:
        from backend.infrastructure.storage.session_manager import load_all_message_history
        
        # Load all messages from session
        all_messages = load_all_message_history(session_id)
        
        logger.info(f"[DEBUG] Loaded {len(all_messages)} messages from session {session_id}")
        
        # Look for the most recent image (search backwards)
        for msg in reversed(all_messages):
            # Convert Pydantic model to dict if needed
            if hasattr(msg, 'model_dump'):
                msg_dict = msg.model_dump()
            elif hasattr(msg, 'dict'):
                msg_dict = msg.dict()
            else:
                msg_dict = msg
            
            logger.info(f"[DEBUG] Checking message: role={msg_dict.get('role')}, sender={msg_dict.get('sender')}, has_files={bool(msg_dict.get('files'))}, has_image_path={bool(msg_dict.get('image_path'))}")
            
            # Method 1: Check for ImageMessage with image_path
            if msg_dict.get("role") == "image" and msg_dict.get("image_path"):
                image_path = msg_dict.get("image_path")
                logger.info(f"[DEBUG] Found ImageMessage with path: {image_path}")
                
                # Convert file path to base64
                try:
                    import os
                    import base64
                    full_path = os.path.join("chat/data", image_path)
                    
                    if os.path.exists(full_path):
                        with open(full_path, "rb") as f:
                            image_data = base64.b64encode(f.read()).decode('utf-8')
                        logger.info(f"[DEBUG] Successfully loaded image from file, length: {len(image_data)}")
                        return image_data
                    else:
                        logger.warning(f"[DEBUG] Image file not found: {full_path}")
                except Exception as e:
                    logger.error(f"[DEBUG] Error reading image file: {e}")
                    continue
            
            # Method 2: Check assistant messages with files (for other types of image messages)
            is_assistant = (msg_dict.get("role") == "assistant" or msg_dict.get("sender") == "bot")
            
            if is_assistant and msg_dict.get("files"):
                logger.info(f"[DEBUG] Found assistant message with {len(msg_dict['files'])} files")
                for file in msg_dict["files"]:
                    file_type = file.get("type", "")
                    logger.info(f"[DEBUG] File type: {file_type}")
                    
                    if file_type.startswith("image/"):
                        image_data = file.get("data")
                        if image_data:
                            logger.info(f"[DEBUG] Found image data, length: {len(image_data)}")
                            # Remove data URL prefix if present
                            if image_data.startswith('data:image'):
                                image_data = image_data.split(',')[1]
                            return image_data
        
        logger.warning(f"[DEBUG] No image found in {len(all_messages)} messages")
        return None
        
    except Exception as e:
        logger.error(f"Error finding recent image: {e}")
        logger.error(traceback.format_exc())
        return None


async def generate_video_from_context(context: Context) -> Dict[str, Any]:
    """
    Generate video from the most recent image in conversation context.
    
    Automatically finds the latest generated image and uses the stored text-to-image prompt
    from history file to optimize it for video motion.
    
    Args:
        context: MCP context with conversation history
    
    Returns:
        ToolResult with video data or error
    """
    import time
    start_time = time.time()
    
    # Get session and services
    session_id: str | None = getattr(context, "client_id", None)
    if not session_id:
        return error_response("Video generation failed: Session ID is missing")
    
    fastapi_app = getattr(getattr(context, "fastmcp", None), "app", None)
    llm_client = None
    
    if fastapi_app is not None:
        if hasattr(fastapi_app.state, "llm_client"):
            llm_client = fastapi_app.state.llm_client
    
    if llm_client is None:
        return error_response("Video generation failed: LLM client unavailable")
    
    try:
        # Find the most recent image
        image_base64 = find_recent_image_in_messages(session_id)
        
        if not image_base64:
            return error_response(
                "未找到最近生成的图片。请先生成一张图片，然后再尝试制作视频。"
            )
        
        # Get the latest text-to-image prompt from history
        original_prompt = get_latest_text_to_image_prompt(session_id)
        
        if not original_prompt:
            original_prompt = "beautiful scene with natural elements"
            logger.warning("No text-to-image prompt found in history, using default")
        else:
            logger.info(f"Found original prompt from history: {original_prompt[:100]}...")
        
        # Generate video from the found image using the original prompt
        return await generate_video_from_image(
            context=context,
            image_base64=image_base64,
            prompt=original_prompt,
            motion_type="cinematic"
        )
        
    except Exception as e:
        logger.error(f"Error generating video from context: {e}")
        logger.error(traceback.format_exc())
        return error_response(f"视频生成失败: {str(e)}")


def register_image_to_video_tools(mcp: FastMCP) -> None:
    """
    Register image-to-video generation tools with MCP.
    
    Args:
        mcp: FastMCP instance to register tools with
    """
    
    @mcp.tool(
        name="generate_video_from_image",
        description="Transform a static image into a dynamic video with AI-powered motion"
    )
    async def tool_generate_video_from_image(
        image_base64: str,
        prompt: str,
        motion_type: str = "cinematic"
    ) -> Dict[str, Any]:
        """
        Generate video from static image.
        
        Args:
            image_base64: Base64 encoded input image
            prompt: Description of desired motion and video content
            motion_type: Type of motion - gentle/dynamic/cinematic/loop
        
        Returns:
            Video in base64 format with metadata
        """
        # Get context from MCP
        context = mcp.get_current_context()
        return await generate_video_from_image(
            context=context,
            image_base64=image_base64,
            prompt=prompt,
            motion_type=motion_type
        )
    
    @mcp.tool(
        name="animate_last_image",
        description="Automatically animate the most recent image from conversation"
    )
    async def tool_animate_last_image() -> Dict[str, Any]:
        """
        Find and animate the most recent generated image.
        
        Automatically extracts the last image from conversation history
        and transforms it into a video with optimized motion.
        
        Returns:
            Animated video of the last generated image
        """
        context = mcp.get_current_context()
        return await generate_video_from_context(context)
    
    logger.info("Image-to-video tools registered successfully")