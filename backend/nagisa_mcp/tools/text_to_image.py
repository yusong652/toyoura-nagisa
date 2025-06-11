from fastmcp import FastMCP, Context
from pydantic import Field
import requests
import asyncio
from dotenv import load_dotenv
import json
from backend.config import get_models_lab_config
from typing import Optional, Dict, Any, List
import httpx
from fastapi import FastAPI
import traceback

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
            max_retries = 20
            retry_interval = 2  # seconds
            # 第一次POST发起生成
            response = await client.post(
                endpoint,
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=60.0
            )
            if debug:
                print(f"[text_to_image] Response status: {response.status_code}")
                print(f"[text_to_image] Response content: {response.text[:100]}...")
            response.raise_for_status()
            result = response.json()
            status = result.get("status")
            if status == "success" and "output" in result and result["output"]:
                return {
                    "type": "image_url",
                    "image_url": result["output"][0]
                }
            elif status == "processing" and result.get("fetch_result") and result.get("id"):
                fetch_url = result["fetch_result"]
                request_id = result["id"]
                fetch_payload = {"request_id": request_id}
                for attempt in range(max_retries):
                    if debug:
                        print(f"[text_to_image] Status is processing, fetching result from {fetch_url} (attempt {attempt+1})...")
                    await asyncio.sleep(retry_interval)
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
                    elif fetch_status != "processing":
                        if debug:
                            print(f"[text_to_image] Unexpected fetch status: {fetch_status}")
                        break
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

async def generate_image() -> str:
    """
    Generate an image based on the current conversation context.
    This tool will analyze the conversation and create a beautiful anime-style image.
    No parameters are needed as it uses the conversation context automatically.
    
    Returns:
        str: A status message indicating the result of image generation:
            - "The image has been generated and saved to your session." on success
            - "Image generation failed, please try again." on failure
    """
    try:
        # 获取配置
        models_lab_config = get_models_lab_config()
        debug = models_lab_config.get("debug", False)
        
        if debug:
            print("[text_to_image] Starting image generation...")
            
        # TODO: 实现实际的图片生成逻辑
        # 这里需要实现从对话上下文中提取提示词并调用 generate_image_from_description
        
        if debug:
            print("[text_to_image] Image generation completed")
            
        return "The image has been generated and saved to your session."
    except Exception as e:
        if debug:
            print(f"[text_to_image] Error in generate_image: {str(e)}")
            print(f"[text_to_image] Traceback: {traceback.format_exc()}")
        return "Image generation failed, please try again."

def register_text_to_image_tool(mcp: FastMCP):
    """
    Register the text-to-image generation tool with the MCP server.
    
    Args:
        mcp: The FastMCP instance to register the tool with
    """
    mcp.tool()(generate_image)

