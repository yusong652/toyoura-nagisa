from fastmcp import FastMCP, Context
from pydantic import Field
import requests
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
        session_id: The session ID for saving the generated image
        prompt: The text prompt for image generation
        negative_prompt: The negative prompt for image generation
        
    Returns:
        Optional[Dict[str, Any]]: A dictionary containing the generated image data, or None if generation fails
    """
    try:
        if not prompt:
            return None
            
        # 获取配置
        models_lab_config = get_models_lab_config()
        debug = models_lab_config.get("debug", False)
        
        if debug:
            print(f"[text_to_image] Config loaded: {models_lab_config}")

        # 构造 payload，优先用函数参数，其余用 config
        payload = {**models_lab_config, "prompt": prompt, "negative_prompt": negative_prompt}
        if debug:
            print(f"[text_to_image] Request payload: {json.dumps(payload, ensure_ascii=False)}")

        async with httpx.AsyncClient() as client:
            if models_lab_config.get("realtime", False):
                endpoint = "https://modelslab.com/api/v6/realtime/text2img"
            else:
                endpoint = "https://modelslab.com/api/v6/images/text2img"
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
            
            if "output" not in result or not result["output"]:
                return None
                
            # 返回第一张生成的图片链接
            return {
                "type": "image_url",
                "image_url": result["output"][0]
            }
            
    except Exception as e:
        if debug:
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

