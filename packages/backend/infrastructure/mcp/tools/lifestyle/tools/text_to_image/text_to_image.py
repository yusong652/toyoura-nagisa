from fastmcp import FastMCP
from dotenv import load_dotenv
import logging
from typing import Any, Dict
from fastapi import FastAPI
from fastmcp.server.context import Context  # type: ignore
from backend.config.text_to_image import TextToImageSettings
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.llm.content_generators.factory import ContentGeneratorFactory
from .comfyui_client import ComfyUIClient

load_dotenv()

app = FastAPI()


async def generate_image_from_description(prompt: str, negative_prompt: str, seed: int = -1) -> Dict[str, Any]:
    """
    Generate image from text prompts using ComfyUI API.
    
    Creates a ComfyUI workflow from the provided prompts and executes it through
    the ComfyUI client, returning base64 encoded image data.
    
    Args:
        prompt: Positive text prompt for image generation
        negative_prompt: Negative text prompt to avoid unwanted elements
        seed: Random seed for reproducible generation (-1 for random)
        
    Returns:
        Dict[str, Any]: Generation result with structure:
            - type: Literal["image_base64", "error"] - Result type
            - image: str - Base64 image data when successful
            - message: str - Error description when failed
            - prompt_id: Optional[str] - ComfyUI prompt ID for debugging
    """
    try:
        # Get configuration
        settings = TextToImageSettings()
        comfyui_config = settings.get_current_config()
        
        # Generate ComfyUI workflow
        workflow = comfyui_config.generate_workflow(
            positive_prompt=prompt,
            negative_prompt=negative_prompt,
            seed=seed
        )
        
        # Create ComfyUI client and generate image
        client = ComfyUIClient(
            server_url=comfyui_config.comfyui_server_url,
            client_id=comfyui_config.client_id
        )
        
        # Execute workflow with progress logging
        def progress_callback(data: Dict[str, Any]) -> None:
            if data.get('type') == 'progress':
                progress_data = data.get('data', {})
                current = progress_data.get('value', 0)
                total = progress_data.get('max', 100)
                logging.info(f"ComfyUI progress: {current}/{total}")
        
        result = await client.generate_image(workflow, progress_callback)
        
        if result["type"] == "image_base64":
            logging.info(f"Successfully generated image with prompt_id: {result.get('prompt_id')}")
        else:
            logging.error(f"Image generation failed: {result.get('message')}")
            
        return result
                
    except Exception as e:
        logging.error(f"ComfyUI generation error: {e}")
        return {"type": "error", "message": f"ComfyUI generation failed: {str(e)}"}

async def generate_image(context: Context) -> dict[str, Any]:
    """Generate a bespoke illustration that visually represents the current conversation context.
    
    Automatically analyzes recent conversation messages to create compelling visual content.
    Extracts themes and artistic requirements from the discussion to generate contextually relevant images.
    """
    import time
    start_time = time.time()

    # Resolve runtime dependencies (session ID, app, llm client)
    # Architecture guarantee: tool_manager.py always injects _meta.client_id
    session_id = context.client_id

    fastapi_app = getattr(getattr(context, "fastmcp", None), "app", None)
    llm_client = None
    if fastapi_app is not None and hasattr(fastapi_app.state, "llm_client"):
        llm_client = fastapi_app.state.llm_client

    if llm_client is None:
        return error_response(
            "Image generation failed: LLM client unavailable"
        )

    # Build prompts using ContentGeneratorFactory
    try:
        prompt_result = await ContentGeneratorFactory.generate_text_to_image_prompt(
            llm_client,
            session_id=session_id
        )
    except Exception as e:
        return error_response(
            "Image generation failed: Prompt generation failed"
        )

    if not prompt_result or "text_prompt" not in prompt_result:
        return error_response(
            "Image generation failed: Empty prompt result"
        )

    text_prompt = prompt_result["text_prompt"]
    negative_prompt = prompt_result["negative_prompt"]
    seed = prompt_result.get("seed", -1)  # Extract seed from prompt result

    # Generate image using ComfyUI
    try:
        image_result = await generate_image_from_description(text_prompt, negative_prompt, seed)
    except Exception as e:
        return error_response(
            f"ComfyUI image generation failed: {str(e)}"
        )

    if not image_result:
        return error_response(
            "Image generation failed: No image result"
        )

    # Handle error response
    if image_result.get("type") == "error":
        return error_response(
            f"Image generation failed: {image_result.get('message', 'Unknown error occurred')}"
        )
    
    # Calculate generation time
    generation_time = f"{time.time() - start_time:.1f}s"
    
    # Handle successful image generation
    if image_result.get("type") == "image_base64" and image_result.get("image"):
        return success_response(
            message="Image generated successfully",
            llm_content={
                "parts": [
                    {"type": "text", "text": f"Successfully generated image in {generation_time}"}
                ]
            },
            image_type="image_base64",
            generation_time=generation_time,
            image_base64=image_result["image"]
        )
    else:
        return error_response(
            "Image generation failed: Unexpected result format"
        )

def register_text_to_image_tools(mcp: FastMCP):
    """
    Register the ComfyUI text-to-image generation tool with proper tags synchronization.
    
    Updates tool registration to reflect ComfyUI backend integration while maintaining
    the same external interface for consistent tool ecosystem compatibility.
    
    Args:
        mcp: The FastMCP instance to register the tool with
    """
    mcp.tool(
        tags={"image", "generation", "ai", "creative", "media", "comfyui"}, 
        annotations={
            "category": "media", 
            "tags": ["image", "generation", "ai", "creative", "media", "comfyui"],
            "backend": "comfyui",
            "workflow_based": True
        }
    )(generate_image)

