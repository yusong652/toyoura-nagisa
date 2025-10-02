"""
Image Service - Business logic for image generation.

This service handles AI-powered image generation based on conversation
context and text prompts.
"""
from typing import Dict, Any
from backend.infrastructure.storage.image_storage import (
    save_image_from_url,
    save_image_from_base64
)
from backend.infrastructure.mcp.tools.lifestyle.tools.text_to_image import (
    generate_image_from_description
)


class ImageService:
    """
    Service layer for image generation operations.

    Provides AI-powered image generation by analyzing conversation context
    and generating appropriate visual content.
    """

    async def generate_image_for_session(
        self,
        session_id: str,
        llm_client: Any
    ) -> Dict[str, Any]:
        """
        Generate an image based on session conversation context.

        This operation:
        1. Uses LLM to analyze conversation and generate prompts
        2. Calls text-to-image service with generated prompts
        3. Saves the generated image to session folder

        Args:
            session_id: Session UUID for context
            llm_client: LLM client for prompt generation

        Returns:
            Dict[str, Any]: Image generation result:
                - success: bool - Operation success flag
                - image_path: str - Local path to saved image (if successful)
                - error: str - Error message (if failed)
        """
        try:
            # Step 1: Generate image prompts from conversation
            prompt_result = await llm_client.generate_text_to_image_prompt(session_id)

            if not prompt_result:
                return {
                    "success": False,
                    "error": "Failed to generate image prompts from conversation"
                }

            # Step 2: Generate image from prompts
            image_result = await generate_image_from_description(
                prompt=prompt_result["text_prompt"],
                negative_prompt=prompt_result["negative_prompt"]
            )

            print(f"[DEBUG] Image generation result type: {type(image_result)}")
            print(f"[DEBUG] Image generation result keys: {list(image_result.keys()) if isinstance(image_result, dict) else 'Not a dict'}")

            if not image_result:
                print("[ERROR] Image generation returned empty result")
                return {
                    "success": False,
                    "error": "Image generation failed"
                }

            # Step 3: Check for error in result
            if image_result.get("type") == "error":
                error_message = image_result.get("message", "Unknown error occurred during image generation")
                print(f"[ERROR] Image generation failed: {error_message}")
                return {
                    "success": False,
                    "error": error_message
                }

            # Step 4: Save image based on result type
            local_path = None

            if image_result.get("type") == "image_url" and image_result.get("image_url"):
                print("[DEBUG] Processing image_url result type")
                local_path = save_image_from_url(image_result["image_url"], session_id)

            elif image_result.get("type") == "image_base64" and image_result.get("image"):
                print("[DEBUG] Processing image_base64 result type")
                print(f"[DEBUG] Base64 data length: {len(image_result['image'])}")
                try:
                    local_path = save_image_from_base64(image_result["image"], session_id)
                    print(f"[DEBUG] Successfully saved base64 image to: {local_path}")
                except Exception as e:
                    print(f"[ERROR] Failed to save base64 image: {e}")
                    return {
                        "success": False,
                        "error": f"Failed to save image: {str(e)}"
                    }
            else:
                print(f"[ERROR] Unknown image result type: {image_result.get('type')}")
                print(f"[ERROR] Available keys in result: {list(image_result.keys())}")
                return {
                    "success": False,
                    "error": f"Unknown result type: {image_result.get('type')}"
                }

            if not local_path:
                print("[ERROR] No local path returned from image saving")
                return {
                    "success": False,
                    "error": "Failed to save generated image"
                }

            print(f"[DEBUG] Image successfully processed and saved to: {local_path}")
            return {
                "success": True,
                "image_path": local_path
            }

        except Exception as e:
            import traceback
            print(f"[ERROR] Image generation exception: {e}")
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }
