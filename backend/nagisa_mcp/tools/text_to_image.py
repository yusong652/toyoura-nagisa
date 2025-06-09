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
            print("[text_to_image] No prompt provided")
            return None

        # 获取配置
        models_lab_config = get_models_lab_config()

        # 构造 payload，优先用函数参数，其余用 config
        payload = {**models_lab_config, "prompt": prompt, "negative_prompt": negative_prompt}
        print(f"[text_to_image][DEBUG] Request payload: {json.dumps(payload, ensure_ascii=False)}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://modelslab.com/api/v6/images/text2img",
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=60.0
            )
            print(f"[text_to_image][DEBUG] Response status: {response.status_code}")
            print(f"[text_to_image][DEBUG] Response content: {response.text}")
            response.raise_for_status()
            result = response.json()
            
            if "output" not in result or not result["output"]:
                print("[text_to_image] No images in response")
                return None
                
            # 返回第一张生成的图片链接
            return {
                "type": "image_url",
                "image_url": result["output"][0]
            }
            
    except Exception as e:
        print(f"[text_to_image] Error generating image: {str(e)}")
        traceback.print_exc()
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
    return ""  # This is just a placeholder, the actual implementation is in handle_function_call

def register_text_to_image_tool(mcp: FastMCP):
    """
    Register the text-to-image generation tool with the MCP server.
    
    Args:
        mcp: The FastMCP instance to register the tool with
    """
    mcp.tool()(generate_image)

