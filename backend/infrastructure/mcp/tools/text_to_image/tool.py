from fastmcp import FastMCP
import asyncio
from dotenv import load_dotenv
import json
import logging
import traceback
from typing import Optional, Dict, Any, List
import httpx
from fastapi import FastAPI
from fastmcp.server.context import Context  # type: ignore
from backend.config import get_text_to_image_config
from backend.infrastructure.mcp.utils.tool_result import ToolResult

load_dotenv()

app = FastAPI()

def _error(message: str, error_details: Optional[str] = None) -> dict:
    """Create standardized error response."""
    data = {"error": message}
    if error_details:
        data["details"] = error_details
    
    return ToolResult(
        status="error",
        message=f"Image generation failed: {message}",
        llm_content={
            "operation": "generate_image",
            "result": "failed",
            "summary": f"Unable to generate image: {message}"
        },
        data=data
    ).model_dump()

def _success(image_type: str, generation_time: Optional[str] = None) -> dict:
    """Create standardized success response."""
    message_parts = ["Successfully generated image"]
    if generation_time:
        message_parts.append(f"in {generation_time}")
    
    return ToolResult(
        status="success", 
        message="Image generated successfully",
        llm_content={
            "operation": "generate_image",
            "result": "success",
            "summary": " ".join(message_parts)
        },
        data={
            "image_type": image_type,
            "generation_time": generation_time
        }
    ).model_dump()

async def _generate_with_models_lab(prompt: str, negative_prompt: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Internal function to generate an image using the ModelsLab API.
    """
    try:
        models_lab_config = config.get("models_lab", {})
        debug = models_lab_config.get("debug", False)

        payload = {**models_lab_config, "prompt": prompt, "negative_prompt": negative_prompt}

        async with httpx.AsyncClient() as client:
            if models_lab_config.get("realtime", False):
                endpoint = "https://modelslab.com/api/v6/realtime/text2img"
            else:
                endpoint = "https://modelslab.com/api/v6/images/text2img"
            
            max_retries = 60
            retry_interval = 4  # seconds
            
            response = await client.post(
                endpoint,
                headers={"Content-Type": "application/json"},
                content=json.dumps(payload),
                timeout=120.0
            )
            
            response.raise_for_status()
            result = response.json()
            status = result.get("status")

            if status == "success" and "output" in result and result["output"]:
                return {"type": "image_url", "image_url": result["output"][0]}
            
            if status == "processing" and result.get("fetch_result") and result.get("id"):
                fetch_url = result["fetch_result"]
                fetch_payload = {"key": models_lab_config.get("key", ""), "request_id": result["id"]}
                
                for attempt in range(max_retries):
                    fetch_resp = await client.post(fetch_url, headers={"Content-Type": "application/json"}, content=json.dumps(fetch_payload), timeout=30.0)
                    fetch_result = fetch_resp.json()
                    fetch_status = fetch_result.get("status")
                    
                    if fetch_status == "success" and "output" in fetch_result and fetch_result["output"]:
                        return {"type": "image_url", "image_url": fetch_result["output"][0]}
                    elif fetch_status == "processing":
                        await asyncio.sleep(retry_interval)
                    else:
                        error_message = fetch_result.get("messege") or fetch_result.get("message") or "Image generation failed, please try again."
                        return {"type": "error", "message": error_message}
                
                return {"type": "error", "message": "Image generation timed out after processing."}
            
            return {"type": "error", "message": "Image generation failed after processing."}
            
    except Exception as e:
        return {"type": "error", "message": str(e)}

async def _generate_with_stable_diffusion(prompt: str, negative_prompt: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Internal function to generate an image using a Stable Diffusion WebUI API.
    """
    try:
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


async def generate_image_from_description(prompt: str, negative_prompt: str):
    """Generate image from text prompts using configured image generation service."""
    try:
        # Get configuration
        config = get_text_to_image_config()
        provider = config.get("provider")
        
        if provider == "models_lab":
            return await _generate_with_models_lab(prompt, negative_prompt, config)
        elif provider == "stable_diffusion_webui":
            return await _generate_with_stable_diffusion(prompt, negative_prompt, config)
        else:
            return {"type": "error", "message": f"Unsupported image generation provider: {provider}"}
            
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
        return _error("Session ID is missing", "client_id not provided in context")

    fastapi_app = getattr(getattr(context, "fastmcp", None), "app", None)
    llm_client = None
    if fastapi_app is not None and hasattr(fastapi_app.state, "llm_client"):
        llm_client = fastapi_app.state.llm_client

    if llm_client is None:
        return _error("LLM client unavailable", "Cannot access LLM client from application context")

    # Build prompts using the LLM client
    try:
        prompt_result = await llm_client.generate_text_to_image_prompt(session_id)
    except Exception as e:
        return _error("Prompt generation failed", str(e))

    if not prompt_result or "text_prompt" not in prompt_result:
        return _error("Empty prompt result", "Prompt generation returned no usable content")

    text_prompt = prompt_result["text_prompt"]
    negative_prompt = prompt_result["negative_prompt"]

    # Generate image using configured provider
    try:
        image_result = await generate_image_from_description(text_prompt, negative_prompt)
    except Exception as e:
        return _error("Image generation failed", str(e))

    if not image_result:
        return _error("No image result", "Image generation returned empty result")

    # Handle error response
    if image_result.get("type") == "error":
        return _error(image_result.get("message", "Unknown error occurred"))
    
    # Calculate generation time
    generation_time = f"{time.time() - start_time:.1f}s"
    
    # Handle successful image generation
    if image_result.get("type") == "image_url" and image_result.get("image_url"):
        success_response = _success("image", generation_time)
        success_response["image_url"] = image_result["image_url"]
        return success_response
    elif image_result.get("type") == "image_base64" and image_result.get("image"):
        success_response = _success("image", generation_time)
        success_response["image_base64"] = image_result["image"]
        return success_response
    else:
        return _error("Unexpected result format", f"Got type: {image_result.get('type')}")

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

