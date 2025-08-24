"""
Content Service - Business logic for content generation.

This service handles content generation operations including title generation
and image generation based on conversation context.
"""
from typing import Dict, Any, Optional
from backend.infrastructure.storage.session_manager import (
    get_all_sessions,
    update_session_title
)
from backend.infrastructure.storage.image_storage import (
    save_image_from_url,
    save_image_from_base64
)
from backend.infrastructure.mcp.tools.lifestyle.tools.text_to_image import (
    generate_image_from_description
)
from backend.infrastructure.mcp.tools.lifestyle.tools.image_to_video.image_to_video import (
    generate_video_from_context as mcp_generate_video_from_context,
    get_latest_text_to_image_prompt,
    find_recent_image_in_messages
)
from backend.shared.utils.helpers import generate_title_for_session as generate_title_helper


class ContentService:
    """
    Service layer for content generation operations.
    
    Provides high-level operations for generating content based on
    conversation context, including titles and images.
    """
    
    async def generate_title_for_session(
        self,
        session_id: str,
        llm_client: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a descriptive title for a chat session.
        
        This operation:
        1. Validates the session exists
        2. Analyzes conversation history
        3. Uses LLM to generate appropriate title
        4. Updates session metadata
        
        Args:
            session_id: Session UUID to generate title for
            llm_client: LLM client for title generation
            
        Returns:
            Optional[Dict[str, Any]]: Title generation result or None if session not found:
                - session_id: str - Session that received new title
                - title: str - Generated title text
                - success: bool - Always True if successful
                - error: str - Error message if generation failed
        """
        # Validate session exists
        sessions = get_all_sessions()
        session = next((s for s in sessions if s['id'] == session_id), None)
        
        if not session:
            return None
        
        try:
            # Generate title using helper function
            new_title = await generate_title_helper(session_id, llm_client)
            
            if new_title is None:
                return {
                    "error": "No valid user message or pure text assistant message found for title generation",
                    "success": False
                }
            
            if not new_title:
                return {
                    "error": "Title generation failed",
                    "success": False
                }
            
            # Update session title
            update_success = update_session_title(session_id, new_title)
            
            if not update_success:
                return {
                    "error": "Failed to update session title",
                    "success": False
                }
            
            return {
                "session_id": session_id,
                "title": new_title,
                "success": True
            }
        except Exception as e:
            print(f"[ERROR] Title generation error: {e}")
            return {
                "error": str(e),
                "success": False
            }
    
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
            print(f"[DEBUG] Generating image prompts for session {session_id}")
            prompt_result = await llm_client.generate_text_to_image_prompt(session_id)
            
            if not prompt_result:
                return {
                    "success": False,
                    "error": "Failed to generate image prompts from conversation"
                }
            
            print(f"[DEBUG] Text prompt: {prompt_result['text_prompt'][:100]}...")
            print(f"[DEBUG] Negative prompt: {prompt_result['negative_prompt'][:100]}...")
            
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
    
    async def generate_video_for_session(
        self,
        session_id: str,
        motion_type: str = "cinematic",
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
            motion_type: Type of motion for video (gentle/dynamic/cinematic/loop)
            llm_client: LLM client for prompt optimization
            
        Returns:
            Dict[str, Any]: Video generation result:
                - success: bool - Operation success flag
                - video_path: str - Local path to saved video (if successful)
                - error: str - Error message (if failed)
        """
        try:
            # For now, we'll directly call the MCP tool function
            # This could be refactored to use a proper video service later
            from fastmcp.server.context import Context
            
            # Create a mock context for the MCP tool
            # In a real implementation, this would be cleaner
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
            
            # Call the MCP tool
            result = await mcp_generate_video_from_context(context)
            
            if result.get("status") == "error":
                return {
                    "success": False,
                    "error": result.get("message", "Video generation failed")
                }
            
            # Extract video data from the successful result
            video_data = result.get("data", {}).get("video_base64")
            if not video_data:
                return {
                    "success": False,
                    "error": "No video data in generation result"
                }
            
            # Save video to session folder (similar to how images are saved)
            from backend.infrastructure.storage.video_storage import save_video_from_base64
            
            try:
                local_path = save_video_from_base64(video_data, session_id)
                print(f"[DEBUG] Successfully saved video to: {local_path}")
                
                return {
                    "success": True,
                    "video_path": local_path
                }
            except Exception as e:
                print(f"[ERROR] Failed to save video: {e}")
                return {
                    "success": False,
                    "error": f"Failed to save video: {str(e)}"
                }
            
        except Exception as e:
            import traceback
            print(f"[ERROR] Video generation exception: {e}")
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }