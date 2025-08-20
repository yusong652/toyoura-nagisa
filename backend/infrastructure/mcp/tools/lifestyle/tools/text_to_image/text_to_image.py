from fastmcp import FastMCP
import asyncio
from dotenv import load_dotenv
import json
import logging
import traceback
from typing import Any
import httpx
from fastapi import FastAPI
from fastmcp.server.context import Context  # type: ignore
from backend.config import get_text_to_image_config
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response

load_dotenv()

app = FastAPI()


async def generate_image_from_description(prompt: str, negative_prompt: str):
    """Generate image from text prompts using Stable Diffusion WebUI API."""
    try:
        # Get configuration
        config = get_text_to_image_config()
        provider = config.get("provider")
        
        if provider != "stable_diffusion_webui":
            return {"type": "error", "message": f"Unsupported image generation provider: {provider}"}
            
        sd_config = config.get("stable_diffusion_webui", {})
        server_url = sd_config.get("server_url")

        if not server_url:
            return {"type": "error", "message": "Stable Diffusion server URL is not configured."}
        
        # Get model type and preset
        model_type = sd_config.get("model_type", "illustrious")
        model_preset = sd_config.get("model_presets", {}).get(model_type, {})

        # Prepare base payload
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "steps": sd_config.get("steps", 25),
            "seed": sd_config.get("seed", -1),
            "enable_hr": sd_config.get("enable_hr", False),
            "hr_scale": sd_config.get("hr_scale", 2.0),
            "hr_upscaler": sd_config.get("hr_upscaler", "4x-UltraSharp"),
            "denoising_strength": sd_config.get("denoising_strength", 0.5),
        }
        
        # Apply model preset, values from preset will override base payload
        payload.update(model_preset)

        # Build override_settings and remove corresponding keys from payload
        override_settings = {}
        if "sd_model_checkpoint" in payload:
            override_settings["sd_model_checkpoint"] = payload.pop("sd_model_checkpoint")
        if "sd_vae" in payload:
            override_settings["sd_vae"] = payload.pop("sd_vae")
        if "clip_skip" in payload:
            override_settings["CLIP_stop_at_last_layers"] = payload.pop("clip_skip")
            
        if override_settings:
            payload["override_settings"] = override_settings

        async with httpx.AsyncClient() as client:
            endpoint = f"{server_url}"
            response = await client.post(
                endpoint,
                headers={"Content-Type": "application/json"},
                content=json.dumps(payload),
                timeout=300.0 
            )

            response.raise_for_status()
            result = response.json()

            if "images" in result and result["images"]:
                base64_image = result["images"][0]
                return {"type": "image_base64", "image": base64_image}
            else:
                return {"type": "error", "message": "Image generation failed, no image in response."}
                
    except Exception as e:
        return {"type": "error", "message": str(e)}

async def generate_image(context: Context) -> dict[str, Any]:
    """Generate a bespoke illustration that visually represents the current conversation context.
    
    Automatically analyzes recent conversation messages to create compelling visual content.
    Extracts themes and artistic requirements from the discussion to generate contextually relevant images.
    """
    import time
    start_time = time.time()

    # Resolve runtime dependencies (session ID, app, llm client)
    session_id: str | None = getattr(context, "client_id", None)
    if not session_id:
        return error_response(
            message="Image generation failed: Session ID is missing",
            error="client_id not provided in context"
        )

    fastapi_app = getattr(getattr(context, "fastmcp", None), "app", None)
    llm_client = None
    if fastapi_app is not None and hasattr(fastapi_app.state, "llm_client"):
        llm_client = fastapi_app.state.llm_client

    if llm_client is None:
        return error_response(
            message="Image generation failed: LLM client unavailable",
            error="Cannot access LLM client from application context"
        )

    # Build prompts using the LLM client
    try:
        prompt_result = await llm_client.generate_text_to_image_prompt(session_id)
    except Exception as e:
        return error_response(
            message="Image generation failed: Prompt generation failed",
            error=str(e)
        )

    if not prompt_result or "text_prompt" not in prompt_result:
        return error_response(
            message="Image generation failed: Empty prompt result",
            error="Prompt generation returned no usable content"
        )

    text_prompt = prompt_result["text_prompt"]
    negative_prompt = prompt_result["negative_prompt"]

    # Generate image using configured provider
    try:
        image_result = await generate_image_from_description(text_prompt, negative_prompt)
    except Exception as e:
        return error_response(
            message="Image generation failed",
            error=str(e)
        )

    if not image_result:
        return error_response(
            message="Image generation failed: No image result",
            error="Image generation returned empty result"
        )

    # Handle error response
    if image_result.get("type") == "error":
        return error_response(
            message=f"Image generation failed: {image_result.get('message', 'Unknown error occurred')}",
            error=image_result.get("message", "Unknown error occurred")
        )
    
    # Calculate generation time
    generation_time = f"{time.time() - start_time:.1f}s"
    
    # Handle successful image generation
    if image_result.get("type") == "image_base64" and image_result.get("image"):
        return success_response(
            message="Image generated successfully",
            llm_content={
                "operation": "generate_image",
                "result": "success",
                "summary": f"Successfully generated image in {generation_time}"
            },
            image_type="image_base64",
            generation_time=generation_time,
            image_base64=image_result["image"]
        )
    else:
        return error_response(
            message="Image generation failed: Unexpected result format",
            error=f"Got type: {image_result.get('type')}"
        )

def register_text_to_image_tools(mcp: FastMCP):
    """
    Register the text-to-image generation tool with proper tags synchronization.
    
    Args:
        mcp: The FastMCP instance to register the tool with
    """
    mcp.tool(
        tags={"image", "generation", "ai", "creative", "media"}, 
        annotations={"category": "media", "tags": ["image", "generation", "ai", "creative", "media"]}
    )(generate_image)

