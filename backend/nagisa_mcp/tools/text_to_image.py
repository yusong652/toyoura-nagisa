from fastmcp import FastMCP
from pydantic import Field
import requests
from dotenv import load_dotenv
import json
from backend.config import get_models_lab_config

load_dotenv()

def register_text_to_image_tool(mcp: FastMCP):
    @mcp.tool()
    def generate_image_from_description(
        prompt: str = Field(..., description="A detailed and specific description of the image you want to generate. The more detailed your description, the better the image quality will be. Include specific details about: subject, style, mood, colors, lighting, composition, and any other relevant visual elements.")
    ) -> dict:
        """
        Generate a high-quality image based on your detailed description.
        
        Important guidelines for best results:
        - Your prompt MUST be detailed and specific to achieve high-quality results
        - Include specific details about:
          * Main subject and its characteristics
          * Artistic style (e.g., photorealistic, anime, oil painting)
          * Mood and atmosphere
          * Color palette and lighting
          * Composition and perspective
          * Background elements
          * Any special effects or details
        - Example of a good prompt: "A photorealistic portrait of a young woman with long silver hair, wearing a flowing white dress, standing in a misty forest at dawn. Soft golden light filtering through trees, ethereal atmosphere, detailed facial features, 8k resolution, cinematic lighting."
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

