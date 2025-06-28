from fastmcp import FastMCP
import asyncio
from dotenv import load_dotenv
import json
from backend.config import get_models_lab_config
from typing import Optional, Dict, Any, List
import httpx
from fastapi import FastAPI
import traceback
from fastmcp.server.context import Context  # type: ignore

load_dotenv()

app = FastAPI()

async def generate_image_from_description(prompt: str, negative_prompt: str) -> Optional[Dict[str, Any]]:
    """
    Internal function to generate an image using the text-to-image API.
    This function is called by the wrapper function after getting the prompts.
    
    Args:
        prompt: The text prompt for image generation
        negative_prompt: The negative prompt for image generation
        
    Returns:
        Optional[Dict[str, Any]]: A dictionary containing the generated image data, or None if generation fails
    """
    try:
        if not prompt:
            return None
        
        models_lab_config = get_models_lab_config()
        debug = models_lab_config.get("debug", False)
        if debug:
            print(f"[text_to_image] Config loaded: {models_lab_config}")
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
            
            # 第一次POST发起生成
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
            
            # 无论第一次请求是否成功，都需要进入fetch流程
            if status == "success" and "output" in result and result["output"]:
                return {
                    "type": "image_url",
                    "image_url": result["output"][0]
                }
            
            # 如果是processing状态，进入循环获取结果
            if status == "processing" and result.get("fetch_result") and result.get("id"):
                fetch_url = result["fetch_result"]
                request_id = result["id"]
                fetch_payload = {
                    "key": models_lab_config.get("key", ""),
                    "request_id": request_id
                }
                
                for attempt in range(max_retries):
                    if debug:
                        print(f"[text_to_image] Fetching result (attempt {attempt+1}/{max_retries})...")
                    
                    fetch_resp = await client.post(
                        fetch_url,
                        headers={"Content-Type": "application/json"},
                        data=json.dumps(fetch_payload),
                        timeout=30.0
                    )
                    fetch_result = fetch_resp.json()
                    fetch_status = fetch_result.get("status")
                    
                    if debug:
                        print(f"[text_to_image] Fetch status: {fetch_status}")
                    
                    if fetch_status == "success" and "output" in fetch_result and fetch_result["output"]:
                        return {
                            "type": "image_url",
                            "image_url": fetch_result["output"][0]
                        }
                    elif fetch_status == "processing":
                        await asyncio.sleep(retry_interval)
                        continue
                    else:
                        if debug:
                            print(f"[text_to_image] Error or unexpected fetch status: {fetch_status}, message: {fetch_result.get('messeg', fetch_result.get('message', ''))}")
                        return {
                            "type": "error",
                            "message": fetch_result.get("messege") or fetch_result.get("message") or "Image generation failed, please try again."
                        }
                
                if debug:
                    print(f"[text_to_image] Max retries ({max_retries}) reached without success")
                return None
            else:
                if debug:
                    print(f"[text_to_image] Unexpected status or empty output: {status}")
                return None
    except Exception as e:
        if 'debug' in locals() and debug:
            print(f"[text_to_image] Error occurred: {str(e)}")
            print(f"[text_to_image] Traceback: {traceback.format_exc()}")
        return None

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

    if not image_result or image_result.get("type") != "image_url" or not image_result.get("image_url"):
        # Propagate detailed message if present
        if isinstance(image_result, dict) and image_result.get("message"):
            return {"type": "error", "message": image_result.get("message")}
        return {"type": "error", "message": "Image generation failed, please try again."}

    return image_result

def register_text_to_image_tools(mcp: FastMCP):
    """
    Register the text-to-image generation tool with the MCP server.
    
    Args:
        mcp: The FastMCP instance to register the tool with
    """
    mcp.tool(tags={"image"}, annotations={"category": "media"})(generate_image)

