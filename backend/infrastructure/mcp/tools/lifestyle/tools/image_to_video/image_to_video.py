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
from typing import Dict, Optional, Any
import httpx
import base64
from io import BytesIO
from PIL import Image
from fastapi import FastAPI
from fastmcp.server.context import Context  # type: ignore
from backend.config.image_to_video import get_image_to_video_settings
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from .wan22_workflow import get_wan22_high_quality_workflow

load_dotenv()

logger = logging.getLogger(__name__)

async def call_wan22_api(
    image_base64: str,
    prompt: str,
    negative_prompt: str
) -> Dict[str, Any]:
    """
    Call ComfyUI API to generate video using optimized WAN 2.2 image-to-video workflow.
    
    Uses the official WAN 2.2 workflow structure to avoid noise-to-image artifacts
    and generate high-quality anime-style videos.
    
    Args:
        image_base64: Base64 encoded input image for video generation
        prompt: Positive prompt with motion descriptions
        negative_prompt: Negative prompt
    
    Returns:
        Dict containing video result or error
    """
    print(f"[DEBUG] Starting WAN 2.2 generation")
    
    try:
        # Get configuration
        settings = get_image_to_video_settings()
        
        # Generate client ID
        import uuid
        client_id = str(uuid.uuid4())
        
        # Get workflow based on configuration
        workflow = get_wan22_high_quality_workflow(
            image_base64=image_base64,
            prompt=prompt,
            negative_prompt=negative_prompt
        )
        print(f"[DEBUG] Using optimized WAN 2.2 workflow")
        
        
        # Prepare payload with optimized workflow
        payload = {
            "prompt": workflow,
            "client_id": client_id
            # Remove return_base64 - might not be supported by proxy
        }
        
        # Make API call
        endpoint = settings.server_url
        
        print(f"[DEBUG] Sending request to ComfyUI server: {endpoint}")
        print(f"[DEBUG] Payload size: {len(json.dumps(payload))} bytes")
        
        # Configure client with extended timeout for video generation
        # Video generation can take 5-10 minutes, so we need very long timeouts
        timeout = httpx.Timeout(
            connect=120.0,  # 2 minutes for connection (should be plenty)
            read=600.0,     # 10 minutes for read (video generation time)
            write=120.0,    # 2 minutes for write (large payload upload)
            pool=120.0      # 2 minutes pool timeout
        )
        
        import time as time_module
        start_time = time_module.time()
        
        async with httpx.AsyncClient(timeout=timeout, limits=httpx.Limits(max_keepalive_connections=5)) as client:
            print(f"[DEBUG] Sending POST request to {endpoint}...")
            print(f"[DEBUG] Request started at: {time_module.strftime('%Y-%m-%d %H:%M:%S')}")
            
            try:
                response = await client.post(
                    endpoint,
                    headers={"Content-Type": "application/json"},
                    content=json.dumps(payload)
                )
                elapsed = time_module.time() - start_time
                print(f"[DEBUG] Request completed in {elapsed:.1f} seconds")
            except Exception as e:
                elapsed = time_module.time() - start_time
                print(f"[DEBUG] Request failed after {elapsed:.1f} seconds")
                raise
            
            print(f"[DEBUG] Response status: {response.status_code}")
            response.raise_for_status()
            
            # Check response size before parsing
            content_length = response.headers.get('content-length', 'unknown')
            print(f"[DEBUG] Response content-length: {content_length}")
            
            result = response.json()
            
            print(f"[DEBUG] ComfyUI response keys: {list(result.keys())}")
            print(f"[DEBUG] Looking for video data in response...")
            
            # Extract video data from response
            video_base64 = result.get("47") or result.get("video") or (result.get("videos") and result["videos"][0] if result.get("videos") else None)
            
            if video_base64:
                # Return WEBM format from SaveWEBM node
                video_format = "webm"
                note = "Generated high-quality WEBM video with WAN 2.2 image-to-video"
                
                # Get actual parameters from config
                actual_frames = settings.frame_count
                actual_fps = float(settings.fps)
                
                return {
                    "type": "video_base64",
                    "video": video_base64,
                    "format": video_format,
                    "fps": actual_fps,
                    "frames": actual_frames,
                    "length": round(actual_frames / actual_fps, 2),
                    "note": note,
                    "quality": "high",
                    "resolution": "1280x704"
                }
            else:
                print(f"[DEBUG] No video in response. Available keys: {list(result.keys())}")
                return {"type": "error", "message": "No video data in response from optimized workflow"}
                
    except (httpx.TimeoutException, httpx.ReadError, httpx.ConnectError):
        return {"type": "error", "message": "Video generation timeout due to Cloudflare limits. Consider using async polling for longer tasks."}
    except httpx.HTTPStatusError as e:
        return {"type": "error", "message": f"Server error: {e.response.status_code}"}
    except Exception as e:
        logger.error(f"Video generation error: {e}")
        return {"type": "error", "message": "Video generation failed"}

async def optimize_prompt_for_video(
    llm_client: Any,
    session_id: str,
    original_prompt: str,
    motion_style: Optional[str] = None
) -> Optional[Dict[str, str]]:
    """
    Optimize static image prompt for WAN 2.2 video generation with few-shot learning.
    
    Uses provider-specific content generators and few-shot examples for better results.
    
    Args:
        llm_client: LLM client for prompt optimization
        session_id: Current session ID for few-shot history
        original_prompt: Original static image prompt
        image_base64: Optional base64 image for visual context
        motion_style: Optional motion style description to add to the prompt
    
    Returns:
        Dict with optimized video_prompt and negative_prompt for WAN 2.2
    """
    print(f"[DEBUG] optimize_prompt_for_video started")
    print(f"[DEBUG] Original prompt: {original_prompt}")
    print(f"[DEBUG] Motion style: {motion_style}")
    
    # Load few-shot history
    from backend.infrastructure.llm.shared.utils.image_to_video import load_video_prompt_history
    few_shot_history = load_video_prompt_history(session_id) if session_id else []
    
    try:
        settings = get_image_to_video_settings()
        
        # Determine which provider we're using and get the appropriate generator
        client_class_name = llm_client.__class__.__name__
        print(f"[DEBUG] LLM client type: {client_class_name}")
        
        if "Gemini" in client_class_name:
            print(f"[DEBUG] Using Gemini video prompt generator with few-shot")
            from backend.infrastructure.llm.providers.gemini.content_generators import GeminiVideoPromptGenerator
            
            # Limit few-shot examples based on config
            max_few_shot = settings.video_few_shot_max_length
            limited_few_shot_history = few_shot_history[-max_few_shot:] if max_few_shot > 0 else []
            print(f"[DEBUG] Using {len(limited_few_shot_history)} few-shot examples")
            
            # Get the native Gemini client
            print(f"[DEBUG] Calling GeminiVideoPromptGenerator.generate_video_prompt...")
            # Add motion style to prompt if provided
            enhanced_prompt = original_prompt
            if motion_style:
                enhanced_prompt = f"{original_prompt}. Motion style: {motion_style}"
            
            result = await GeminiVideoPromptGenerator.generate_video_prompt(
                llm_client.client,  # Use the native Gemini client
                enhanced_prompt,
                image_base64=None,  # Don't send image to LLM
                motion_type="cinematic",  # Default for compatibility with existing generator
                few_shot_history=limited_few_shot_history
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
        
        # If we got a result from the content generator, save it and return
        if result:
            # Save to few-shot history (same format as text-to-image)
            from backend.infrastructure.llm.shared.utils.image_to_video import save_video_prompt_generation
            try:
                # Create user request in same format as BaseVideoPromptGenerator.create_video_prompt_request
                motion_desc = f" with {motion_style}" if motion_style else ""
                user_request = f"Transform this static image prompt into a dynamic video prompt{motion_desc}:\n\nOriginal prompt: {original_prompt}\n\nAdd motion descriptions, camera movements, and temporal changes."
                
                # Create assistant response in XML format
                assistant_response = f"<video_prompt>{result.get('video_prompt', '')}</video_prompt>\n<negative_prompt>{result.get('negative_prompt', '')}</negative_prompt>"
                
                save_video_prompt_generation(
                    session_id=session_id,
                    user_request=user_request,
                    assistant_response=assistant_response
                )
                print(f"[DEBUG] Saved video prompt to few-shot history")
            except Exception as e:
                print(f"[WARNING] Failed to save video prompt to history: {e}")
            
            return result
        
        # No result from API
        print(f"[DEBUG] API returned None, skipping video prompt generation")
        return None
        
    except Exception as e:
        logger.error(f"Error optimizing prompt for video: {e}")
        print(f"[DEBUG] Exception occurred during prompt optimization, returning None")
        return None


async def generate_video_from_image(
    context: Context,
    image_base64: str,
    prompt: str,
    motion_style: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate video from static image using WAN 2.2 image-to-video.
    
    Transforms a static image into a dynamic video by adding motion based on the prompt.
    
    Args:
        context: MCP context with session info
        image_base64: Base64 encoded input image
        prompt: Text description for the video generation
        motion_style: Optional motion style description (e.g., 'cinematic camera movement')
    
    Returns:
        ToolResult with video data or error
    """
    import time
    start_time = time.time()
    
    # Get settings
    settings = get_image_to_video_settings()
    
    # Use default motion style if not specified
    if not motion_style:
        # Use cinematic as default from motion_styles config
        motion_style = settings.motion_styles.get("cinematic", "cinematic camera movement")
    
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
            motion_style=motion_style
        )
        
        if prompt_result:
            video_prompt = prompt_result["video_prompt"]
            negative_prompt = prompt_result["negative_prompt"]
            print(f"[DEBUG] Prompt optimization completed")
            print(f"[DEBUG] Video prompt: {video_prompt[:100]}...")
            print(f"[DEBUG] Negative prompt: {negative_prompt[:100]}...")
        else:
            # LLM optimization failed, skip video generation
            print(f"[DEBUG] LLM optimization failed, skipping video generation")
            return error_response("Video generation skipped: LLM prompt optimization failed")
        
        if settings.debug:
            logger.info(f"[DEBUG] Video prompt optimization:")
            logger.info(f"  - Original: {prompt}")
            logger.info(f"  - Optimized: {video_prompt}")
            logger.info(f"  - Motion style: {motion_style}")
        
        # Generate video
        print(f"[DEBUG] Starting video generation with WAN 2.2...")
        video_result = await call_wan22_api(
            image_base64=image_base64,
            prompt=video_prompt,
            negative_prompt=negative_prompt
        )
        print(f"[DEBUG] Video generation completed")
        print(f"[DEBUG] video_result type: '{video_result.get('type')}'")
        print(f"[DEBUG] video_result keys: {list(video_result.keys())}")
        
        if video_result.get("type") == "error":
            return error_response(
                f"Video generation failed: {video_result.get('message', 'Unknown error')}"
            )
        
        # Successfully generated video with optimized WAN 2.2 workflow
        print(f"[DEBUG] Got video from optimized WAN 2.2 workflow")
        generation_time = f"{time.time() - start_time:.1f}s"
        # Get essential info from result
        actual_format = video_result.get("format", "webm")
        actual_length = video_result.get("length", 3.375)
        
        return success_response(
            message=f"Video generated successfully ({generation_time})",
            llm_content={
                "description": f"Generated a {actual_length}s video"
            },
            data={
                "video_base64": video_result.get("video"),
                "format": actual_format,
                "length": actual_length
            }
        )
        
    except Exception as e:
        logger.error(f"Error in video generation: {e}")
        logger.error(traceback.format_exc())
        return error_response(f"Video generation failed: {str(e)}")

def register_image_to_video_tools(mcp: FastMCP) -> None:
    """
    Register image-to-video generation tools with MCP.
    
    Args:
        mcp: FastMCP instance to register tools with
    """
    
    @mcp.tool(
        name="generate_video_from_image",
        description="Generate dynamic video with AI-powered motion using WAN 2.2 image-to-video"
    )
    async def _tool_generate_video_from_image(
        image_base64: str,
        prompt: str,
        motion_style: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate video from static image.
        
        Args:
            image_base64: Base64 encoded input image
            prompt: Description of desired motion and video content
            motion_style: Optional motion style (e.g., 'cinematic camera movement')
        
        Returns:
            Video in base64 format with metadata
        """
        # Get context from MCP
        context = mcp.get_current_context()
        return await generate_video_from_image(
            context=context,
            image_base64=image_base64,
            prompt=prompt,
            motion_style=motion_style
        )
    
    logger.info("Image-to-video tools registered successfully")