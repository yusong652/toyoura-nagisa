"""
Video Service - Business logic for video generation.

This service handles AI-powered video generation from images,
including motion style optimization and video synthesis.
"""
from typing import Dict, Any, Optional
from backend.shared.utils.session_helpers import find_latest_image_in_session, get_latest_text_to_image_prompt


class VideoService:
    """
    Service layer for video generation operations.

    Provides AI-powered video generation from images by analyzing
    context and applying motion styles for dynamic visual content.
    """

    async def generate_video_for_session(
        self,
        session_id: str,
        motion_style: Optional[str] = None,
        llm_client: Any = None
    ) -> Dict[str, Any]:
        """
        Generate a video from the most recent image in session context.

        This operation:
        1. Finds the most recent generated image in the session
        2. Extracts the original text-to-image prompt from history
        3. Optimizes the prompt for video motion using LLM
        4. Generates video using image-to-video service
        5. Saves the generated video to session folder

        Args:
            session_id: Session UUID for context
            motion_style: Optional motion style description (e.g., 'cinematic camera movement')
            llm_client: LLM client for prompt optimization

        Returns:
            Dict[str, Any]: Video generation result:
                - success: bool - Operation success flag
                - video_path: str - Local path to saved video (if successful)
                - error: str - Error message (if failed)
        """
        # Use the MCP tool directly for video generation
        from backend.infrastructure.mcp.tools.lifestyle.tools.image_to_video.image_to_video import generate_video_from_image

        try:
            # Find the most recent image in the session
            try:
                image_base64 = find_latest_image_in_session(session_id)
            except ValueError as e:
                return {
                    "success": False,
                    "error": str(e)
                }

            # Get the latest text-to-image prompt for better video generation
            original_prompt = get_latest_text_to_image_prompt(session_id)
            if not original_prompt:
                original_prompt = "Generate a dynamic video with natural motion and cinematic quality"

            # Create a mock context for the MCP tool
            class MockContext:
                def __init__(self, session_id: str, llm_client):
                    self.client_id = session_id
                    self.fastmcp = type('MockFastMCP', (), {
                        'app': type('MockApp', (), {
                            'state': type('MockState', (), {
                                'llm_client': llm_client
                            })()
                        })()
                    })()

            context = MockContext(session_id, llm_client)

            # Generate video using the MCP tool with original image prompt
            result = await generate_video_from_image(
                context=context,
                image_base64=image_base64,
                prompt=original_prompt,
                motion_style=motion_style
            )

            if result.get("status") == "error":
                return {
                    "success": False,
                    "error": result.get("message", "Video generation failed")
                }

            # Extract video data and save it
            data = result.get("data", {})

            # Check if video_base64 is in nested data structure
            video_data = None
            if isinstance(data.get("data"), dict):
                video_data = data["data"].get("video_base64")
                video_format = data["data"].get("format", "webm")
            else:
                video_data = data.get("video_base64")
                video_format = data.get("format", "webm")

            print(f"[DEBUG] VideoService data keys: {list(data.keys()) if data else 'None'}")
            print(f"[DEBUG] Has nested data: {isinstance(data.get('data'), dict)}")
            print(f"[DEBUG] Has video_base64: {bool(video_data)}")
            print(f"[DEBUG] Video format: {video_format}")

            if not video_data:
                data_summary = {k: f"<{type(v).__name__}>" if k == "data" and isinstance(v, dict) else v
                               for k, v in data.items() if k != "video_base64"}
                print(f"[DEBUG] No video_base64 found in structure. Keys: {list(data.keys())}, Summary: {data_summary}")
                return {
                    "success": False,
                    "error": "No video data in generation result"
                }

            # Save video to session folder
            from backend.infrastructure.storage.video_storage import save_video_from_base64

            try:
                print(f"[DEBUG] Saving video with format: {video_format}")
                local_path = save_video_from_base64(video_data, session_id, output_dir_base="chat/data", format=video_format)
                print(f"[DEBUG] Video saved successfully to: {local_path}")

                return {
                    "success": True,
                    "video_path": local_path,
                    "data": data
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to save video: {str(e)}"
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Video generation failed: {str(e)}"
            }
