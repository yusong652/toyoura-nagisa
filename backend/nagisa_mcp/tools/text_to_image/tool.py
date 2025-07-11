from fastmcp import FastMCP
import asyncio
from dotenv import load_dotenv
import json
from backend.config import get_text_to_image_config
from typing import Optional, Dict, Any, List
import httpx
from fastapi import FastAPI
import traceback
from fastmcp.server.context import Context  # type: ignore

load_dotenv()

app = FastAPI()

async def _generate_with_models_lab(prompt: str, negative_prompt: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Internal function to generate an image using the ModelsLab API.
    """
    try:
        models_lab_config = config.get("models_lab", {})
        debug = models_lab_config.get("debug", False)
        if debug:
            print(f"[text_to_image] ModelsLab Config loaded: {models_lab_config}")

        payload = {**models_lab_config, "prompt": prompt, "negative_prompt": negative_prompt}
        if debug:
            print(f"[text_to_image] Request payload: {json.dumps(payload, ensure_ascii=False)}")

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
                data=json.dumps(payload),
                timeout=120.0
            )
            if debug:
                print(f"[text_to_image] Response status: {response.status_code}")
                print(f"[text_to_image] Response content: {response.text[:100]}...")
            
            response.raise_for_status()
            result = response.json()
            status = result.get("status")

            if status == "success" and "output" in result and result["output"]:
                return {"type": "image_url", "image_url": result["output"][0]}
            
            if status == "processing" and result.get("fetch_result") and result.get("id"):
                fetch_url = result["fetch_result"]
                fetch_payload = {"key": models_lab_config.get("key", ""), "request_id": result["id"]}
                
                for attempt in range(max_retries):
                    if debug:
                        print(f"[text_to_image] Fetching result (attempt {attempt+1}/{max_retries})...")
                    
                    fetch_resp = await client.post(fetch_url, headers={"Content-Type": "application/json"}, data=json.dumps(fetch_payload), timeout=30.0)
                    fetch_result = fetch_resp.json()
                    fetch_status = fetch_result.get("status")
                    
                    if debug:
                        print(f"[text_to_image] Fetch status: {fetch_status}")
                    
                    if fetch_status == "success" and "output" in fetch_result and fetch_result["output"]:
                        return {"type": "image_url", "image_url": fetch_result["output"][0]}
                    elif fetch_status == "processing":
                        await asyncio.sleep(retry_interval)
                    else:
                        error_message = fetch_result.get("messege") or fetch_result.get("message") or "Image generation failed, please try again."
                        if debug:
                            print(f"[text_to_image] Error or unexpected fetch status: {fetch_status}, message: {error_message}")
                        return {"type": "error", "message": error_message}
                
                if debug:
                    print(f"[text_to_image] Max retries ({max_retries}) reached without success")
            
            return {"type": "error", "message": "Image generation failed after processing."}
            
    except Exception as e:
        if 'debug' in locals() and debug:
            print(f"[text_to_image] Error occurred: {str(e)}")
            print(f"[text_to_image] Traceback: {traceback.format_exc()}")
        return {"type": "error", "message": str(e)}

async def _generate_with_stable_diffusion(prompt: str, negative_prompt: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Internal function to generate an image using a Stable Diffusion WebUI API.
    """
    try:
        sd_config = config.get("stable_diffusion_webui", {})
        debug = sd_config.get("debug", False)
        server_url = sd_config.get("server_url")

        if not server_url:
            return {"type": "error", "message": "Stable Diffusion server URL is not configured."}
        
        # 1. 获取模型类型和预设
        model_type = sd_config.get("model_type", "illustrious")
        model_preset = sd_config.get("model_presets", {}).get(model_type, {})
        
        if debug:
            print(f"[text_to_image] Using model type: {model_type}")
            print(f"[text_to_image] Using model preset: {json.dumps(model_preset, indent=2)}")

        # 2. 准备基础 payload
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
        
        # 3. 应用模型预设，预设中的值会覆盖基础 payload
        payload.update(model_preset)

        # 4. 构建 override_settings，并从 payload 中移除相应键
        override_settings = {}
        if "sd_model_checkpoint" in payload:
            override_settings["sd_model_checkpoint"] = payload.pop("sd_model_checkpoint")
        if "sd_vae" in payload:
            override_settings["sd_vae"] = payload.pop("sd_vae")
        if "clip_skip" in payload:
            override_settings["CLIP_stop_at_last_layers"] = payload.pop("clip_skip")
            
        if override_settings:
            payload["override_settings"] = override_settings

        if debug:
            print(f"[text_to_image] Request payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")

        async with httpx.AsyncClient() as client:
            endpoint = f"{server_url}"
            response = await client.post(
                endpoint,
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=300.0 
            )
            if debug:
                print(f"[text_to_image] Response status: {response.status_code}")

            response.raise_for_status()
            result = response.json()
            
            if debug:
                print(f"[text_to_image] SD API response keys: {list(result.keys())}")
                if "images" in result:
                    print(f"[text_to_image] Number of images returned: {len(result['images'])}")
                    if result["images"]:
                        print(f"[text_to_image] First image data length: {len(result['images'][0])}")
                        print(f"[text_to_image] Model type used: {model_type}")

            if "images" in result and result["images"]:
                base64_image = result["images"][0]
                if debug:
                    print(f"[text_to_image] Returning base64 image, length: {len(base64_image)}")
                return {"type": "image_base64", "image": base64_image}
            else:
                if debug:
                    print(f"[text_to_image] No images in response or empty images list")
                return {"type": "error", "message": "Image generation failed, no image in response."}
                
    except Exception as e:
        if 'debug' in locals() and debug:
            print(f"[text_to_image] Error occurred: {str(e)}")
            print(f"[text_to_image] Traceback: {traceback.format_exc()}")
        return {"type": "error", "message": str(e)}


async def generate_image_from_description(prompt: str, negative_prompt: str) -> Optional[Dict[str, Any]]:
    """
    Internal function to generate an image using the configured text-to-image API.
    This function is a dispatcher that calls the appropriate provider function.
    
    Args:
        prompt: The text prompt for image generation
        negative_prompt: The negative prompt for image generation
        
    Returns:
        Optional[Dict[str, Any]]: A dictionary containing the generated image data, or None if generation fails
    """
    print(f"[text_to_image] generate_image_from_description called")
    print(f"[text_to_image] Prompt length: {len(prompt)}")
    print(f"[text_to_image] Negative prompt length: {len(negative_prompt)}")
    
    config = get_text_to_image_config()
    provider = config.get("type")
    debug = config.get("debug", False)
    
    print(f"[text_to_image] Selected provider: {provider}")
    print(f"[text_to_image] Debug mode: {debug}")
    print(f"[text_to_image] Config keys: {list(config.keys())}")
    
    if debug:
        print(f"[text_to_image] Full config: {config}")
        print(f"[text_to_image] Prompt: {prompt}")
        print(f"[text_to_image] Negative prompt: {negative_prompt}")

    if provider == "models_lab":
        return await _generate_with_models_lab(prompt, negative_prompt, config)
    elif provider == "stable_diffusion_webui":
        return await _generate_with_stable_diffusion(prompt, negative_prompt, config)
    else:
        error_message = f"Unsupported image generation provider: {provider}"
        if debug:
            print(f"[text_to_image] {error_message}")
        return {"type": "error", "message": error_message}

async def generate_image(context: Context) -> dict[str, Any]:
    """Generate a bespoke illustration that visually represents the current conversation context.

    When to call:
        • The user explicitly asks to *draw*, *paint*, *create*, or *generate* an image, picture, artwork, concept art, anime-style scene, meme, etc.
        • The user implicitly requests a visual representation (e.g. "Show me what that looks like").

    Behaviour:
        1. The tool automatically crafts a rich text-to-image prompt from the most recent user/assistant messages.
        2. It then invokes a high-quality diffusion model to synthesise the image.

    Parameters:
        (none) – all context is inferred automatically.

    Returns:
        On success the tool responds with a short confirmation string such as
        "The image has been generated and saved to your session." 
        On failure it returns a JSON object: { "type": "error", "message": "…" }
    """

    # ------------------------------------------------------------------
    # 1. Resolve runtime dependencies (session ID, app, llm client)
    # ------------------------------------------------------------------
    session_id: str | None = getattr(context, "client_id", None)
    if not session_id:
        return {"type": "error", "message": "Session ID is missing (client_id not provided)."}

    # *context.fastmcp* is the FastMCP instance where we attached the FastAPI app
    fastapi_app = getattr(getattr(context, "fastmcp", None), "app", None)
    llm_client = None
    if fastapi_app is not None and hasattr(fastapi_app.state, "llm_client"):
        llm_client = fastapi_app.state.llm_client

    if llm_client is None:
        return {"type": "error", "message": "LLM client is not available from application context."}

    # ------------------------------------------------------------------
    # 2. Build prompts using the LLM client
    # ------------------------------------------------------------------
    try:
        prompt_result = await llm_client.generate_text_to_image_prompt(session_id)
    except Exception as e:
        return {"type": "error", "message": f"Failed to generate prompts: {e}"}

    if not prompt_result or "text_prompt" not in prompt_result:
        return {"type": "error", "message": "Prompt generation returned empty result."}

    text_prompt = prompt_result["text_prompt"]
    negative_prompt = prompt_result["negative_prompt"]

    # ------------------------------------------------------------------
    # 3. Call the ModelsLab text-to-image API
    # ------------------------------------------------------------------
    try:
        image_result = await generate_image_from_description(text_prompt, negative_prompt)
    except Exception as e:
        return {"type": "error", "message": f"Image generation failed: {e}"}

    if not image_result:
        return {"type": "error", "message": "Image generation failed, please try again."}

    # Propagate detailed message if present
    if image_result.get("type") == "error":
        return {"type": "error", "message": image_result.get("message", "An unknown error occurred.")}
    
    # Handle successful image generation (URL or Base64)
    print(f"[DEBUG] Checking image_result for success...")
    print(f"[DEBUG] image_result type: {image_result.get('type')}")
    print(f"[DEBUG] image_result keys: {list(image_result.keys())}")
    
    if image_result.get("type") == "image_url" and image_result.get("image_url"):
        print(f"[DEBUG] Returning image_url result: {image_result['image_url'][:50]}...")
        return image_result
    elif image_result.get("type") == "image_base64" and image_result.get("image"):
        print(f"[DEBUG] Returning image_base64 result, data length: {len(image_result['image'])}")
        return image_result
    else:
        print(f"[ERROR] Unexpected image result format:")
        print(f"[ERROR] Type: {image_result.get('type')}")
        print(f"[ERROR] Has image_url: {'image_url' in image_result and bool(image_result.get('image_url'))}")
        print(f"[ERROR] Has image: {'image' in image_result and bool(image_result.get('image'))}")

    return {"type": "error", "message": "Image generation failed with an unexpected result format."}

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

