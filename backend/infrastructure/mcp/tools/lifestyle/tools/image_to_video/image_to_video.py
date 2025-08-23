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
    try:
        # Get configuration
        settings = get_image_to_video_settings()
        config = settings.get_animatediff_config()
        
        # Get motion preset
        motion_preset = settings.motion_presets.get(motion_type, {})
        
        # Prepare API payload for img2img with AnimateDiff
        payload = {
            "init_images": [image_base64],
            "prompt": f"{prompt}, {motion_preset.get('description', '')}",
            "negative_prompt": negative_prompt,
            "steps": config.steps,
            "cfg_scale": motion_preset.get("cfg_scale", config.cfg_scale),
            "denoising_strength": config.denoising_strength,
            "sampler_name": config.sampler_name,
            "seed": config.seed,
            "batch_size": 1,
            "n_iter": 1,
            
            # AnimateDiff specific parameters
            "alwayson_scripts": {
                "AnimateDiff": {
                    "args": [
                        {
                            "enable": True,
                            "video_length": config.frame_count,
                            "fps": config.fps,
                            "loop_number": 0,
                            "closed_loop": motion_preset.get("closed_loop", config.closed_loop),
                            "batch_index": 0,
                            "stride": 1,
                            "overlap": config.context_overlap,
                            "format": config.output_format,
                            "video_quality": config.video_quality,
                            "model": config.motion_module,
                            "motion_scale": motion_preset.get("motion_scale", config.motion_scale)
                        }
                    ]
                }
            }
        }
        
        if config.debug:
            logger.info(f"[DEBUG] AnimateDiff API call:")
            logger.info(f"  - Server: {config.server_url}")
            logger.info(f"  - Motion type: {motion_type}")
            logger.info(f"  - Frames: {config.frame_count}, FPS: {config.fps}")
        
        # Make API call
        async with httpx.AsyncClient() as client:
            endpoint = f"{config.server_url}{config.img2vid_endpoint}"
            response = await client.post(
                endpoint,
                headers={"Content-Type": "application/json"},
                content=json.dumps(payload),
                timeout=600.0  # Longer timeout for video generation
            )
            
            response.raise_for_status()
            result = response.json()
            
            # AnimateDiff returns video in images array
            if "images" in result and result["images"]:
                video_base64 = result["images"][0]
                return {
                    "type": "video_base64",
                    "video": video_base64,
                    "format": config.output_format,
                    "fps": config.fps,
                    "frames": config.frame_count
                }
            else:
                return {"type": "error", "message": "Video generation failed, no video in response"}
                
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error in AnimateDiff API call: {e}")
        return {"type": "error", "message": f"API error: {e.response.status_code}"}
    except Exception as e:
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
    
    Uses LLM to transform static descriptions into dynamic motion descriptions.
    
    Args:
        llm_client: LLM client for prompt optimization
        session_id: Current session ID
        original_prompt: Original static image prompt
        image_base64: Optional base64 image for visual context
    
    Returns:
        Dict with optimized video_prompt and negative_prompt
    """
    try:
        settings = get_image_to_video_settings()
        
        # Build optimization prompt
        system_prompt = settings.video_prompt_system
        
        user_message = f"""Transform this static image prompt into a dynamic video prompt:

Original prompt: {original_prompt}

Add motion descriptions, camera movements, and temporal changes.
Keep the core subject and style, but make it dynamic.
Output format:
VIDEO_PROMPT: <your video prompt>
NEGATIVE_PROMPT: <negative prompt for video>"""

        # Call LLM for optimization
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        # If image is provided, add it for visual context
        if image_base64:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": "Here's the image to animate:"},
                    {"type": "image", "source": {"data": image_base64}}
                ]
            })
        
        response = await llm_client.generate_response(
            messages=messages,
            temperature=settings.video_prompt_temperature,
            max_tokens=500
        )
        
        # Parse response
        response_text = response.get("content", "")
        video_prompt = original_prompt  # Fallback
        negative_prompt = settings.default_motion_negative
        
        for line in response_text.split("\n"):
            if line.startswith("VIDEO_PROMPT:"):
                video_prompt = line.replace("VIDEO_PROMPT:", "").strip()
            elif line.startswith("NEGATIVE_PROMPT:"):
                negative_prompt = line.replace("NEGATIVE_PROMPT:", "").strip()
        
        # Add default motion keywords
        video_prompt = f"{video_prompt}, {settings.default_motion_positive}"
        
        return {
            "video_prompt": video_prompt,
            "negative_prompt": negative_prompt
        }
        
    except Exception as e:
        logger.error(f"Error optimizing prompt for video: {e}")
        # Fallback to adding basic motion keywords
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
        prompt_result = await optimize_prompt_for_video(
            llm_client=llm_client,
            session_id=session_id,
            original_prompt=prompt,
            image_base64=image_base64
        )
        
        video_prompt = prompt_result["video_prompt"]
        negative_prompt = prompt_result["negative_prompt"]
        
        if settings.enable_debug:
            logger.info(f"[DEBUG] Video prompt optimization:")
            logger.info(f"  - Original: {prompt}")
            logger.info(f"  - Optimized: {video_prompt}")
            logger.info(f"  - Motion type: {motion_type}")
        
        # Generate video
        video_result = await call_animatediff_api(
            image_base64=image_base64,
            prompt=video_prompt,
            negative_prompt=negative_prompt,
            motion_type=motion_type
        )
        
        if video_result.get("type") == "error":
            return error_response(
                f"Video generation failed: {video_result.get('message', 'Unknown error')}"
            )
        
        # Calculate generation time
        generation_time = f"{time.time() - start_time:.1f}s"
        
        # Build success response
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


async def find_recent_image_in_messages(chat_service, session_id: str) -> str | None:
    """
    Find the most recent AI-generated image in conversation messages.
    
    Args:
        chat_service: Chat service instance
        session_id: Current session ID
    
    Returns:
        Base64 image data or None if not found
    """
    try:
        recent_messages = await chat_service.get_recent_messages(
            session_id=session_id,
            limit=10
        )
        
        # Look for the most recent image in assistant messages
        for msg in reversed(recent_messages):
            if msg.get("role") == "assistant" and msg.get("files"):
                for file in msg["files"]:
                    if file.get("type", "").startswith("image/"):
                        return file.get("data")
        
        return None
        
    except Exception as e:
        logger.error(f"Error finding recent image: {e}")
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
    chat_service = None
    
    if fastapi_app is not None:
        if hasattr(fastapi_app.state, "llm_client"):
            llm_client = fastapi_app.state.llm_client
        if hasattr(fastapi_app.state, "chat_service"):
            chat_service = fastapi_app.state.chat_service
    
    if llm_client is None:
        return error_response("Video generation failed: LLM client unavailable")
    
    if chat_service is None:
        return error_response("Video generation failed: Chat service unavailable")
    
    try:
        # Find the most recent image
        image_base64 = await find_recent_image_in_messages(chat_service, session_id)
        
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