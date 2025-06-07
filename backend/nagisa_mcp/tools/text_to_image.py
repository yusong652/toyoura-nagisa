from fastmcp import FastMCP
from pydantic import Field
import requests
import os
from dotenv import load_dotenv
import json
from backend.config import get_models_lab_config

load_dotenv()

def register_text_to_image_tool(mcp: FastMCP):
    @mcp.tool()
    def text_to_image(
        prompt: str = Field(..., description="A detailed description of the image you want to generate."),
        negative_prompt: str = Field(None, description="Elements you want to avoid in the image.")
    ) -> dict:
        """
        Generate an image based on your description.
        
        - Use the 'prompt' to describe the desired image as clearly and specifically as possible. Include details such as subject, style, mood, color, background, and any other relevant attributes.
        - Use the 'negative_prompt' to specify anything you do NOT want to appear in the image (e.g., "blurry", "text", "extra hands").
        - The more detailed and precise your prompt, the better the generated image will match your expectations.
        - Example: "A futuristic cityscape at sunset, vibrant colors, flying cars, in the style of digital art."
        """
        import time
        cfg = get_models_lab_config()
        api_key = cfg["api_key"]
        model_id = cfg["model_id"]
        print(f"[text_to_image] api_key: {api_key}")
        print(f"[text_to_image] model_id: {model_id}")
        if not api_key:
            print("[text_to_image] ERROR: MODELS_LAB_API_KEY environment variable is not set")
            return {"error": "MODELS_LAB_API_KEY environment variable is not set"}
        if not model_id:
            print("[text_to_image] ERROR: MODELS_LAB_MODEL_ID environment variable is not set")
            return {"error": "MODELS_LAB_MODEL_ID environment variable is not set"}
        url = "https://modelslab.com/api/v6/realtime/text2img"
        extra_keys = [
            "width", "height", "samples", "num_inference_steps", "safety_checker", "safety_checker_type", "enhance_prompt", "style",
            "seed", "guidance_scale", "panorama", "self_attention", "upscale", "lora_model", "tomesd", "use_karras_sigmas", "vae",
            "lora_strength", "scheduler", "webhook", "track_id"
        ]
        # 固定负面提示词
        negative_prompt = "blurry, low quality, distorted, extra limbs, bad anatomy, text, watermark, ugly"
        payload = {
            "key": api_key,
            "model_id": model_id,
            "prompt": prompt,
            "negative_prompt": negative_prompt
        }
        for k in extra_keys:
            v = cfg.get(k, None)
            if v is not None:
                payload[k] = v
        print(f"[text_to_image] Request payload: {json.dumps(payload, ensure_ascii=False)}")
        headers = {"Content-Type": "application/json"}
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            print(f"[text_to_image] HTTP status: {resp.status_code}")
            print(f"[text_to_image] Response text: {resp.text}")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[text_to_image] Exception: {str(e)}")
            return {"error": str(e)}

