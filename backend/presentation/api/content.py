"""
Content Generation API Routes.

This module handles content generation endpoints including title generation
and image generation following Clean Architecture principles.
"""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Request
from backend.presentation.models.api_models import GenerateImageRequest, GenerateVideoRequest
from backend.domain.services.content_service import ContentService
from backend.infrastructure.llm.base.client import LLMClientBase

router = APIRouter(tags=["content"])


def get_content_service() -> ContentService:
    """
    Dependency injection for ContentService.
    
    Returns:
        ContentService: Content generation service instance
    """
    return ContentService()


def get_llm_client(request: Request) -> LLMClientBase:
    """
    Get LLM client from app state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        LLMClientBase: LLM client instance
    """
    return request.app.state.llm_client


@router.post("/history/generate-title", response_model=dict)
async def generate_title(
    request: Request,
    service: ContentService = Depends(get_content_service),
    llm_client: LLMClientBase = Depends(get_llm_client)
) -> Dict[str, Any]:
    """
    Generate a descriptive title for a chat session based on conversation history.
    
    This endpoint:
    1. Validates the session exists
    2. Analyzes conversation history
    3. Uses LLM to generate a contextual title
    4. Updates session metadata with new title
    
    Args:
        request: FastAPI request containing session_id in JSON body
        
    Returns:
        Dict[str, Any]: Title generation result with structure:
            - session_id: str - Session that received new title
            - title: str - Generated title text
            - success: bool - Operation success flag
    
    Raises:
        HTTPException: 
            - 400 if no session_id provided or no valid messages for title generation
            - 404 if session not found
            - 500 if title generation fails
    """
    try:
        # Parse request body
        data = await request.json()
        session_id = data.get('session_id')
        
        if not session_id:
            raise HTTPException(
                status_code=400,
                detail="session_id not provided in request"
            )
        
        # Generate title using service
        result = await service.generate_title_for_session(
            session_id=session_id,
            llm_client=llm_client
        )
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
        
        if result.get("error"):
            raise HTTPException(
                status_code=400,
                detail=result["error"]
            )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate title: {str(e)}"
        )


@router.post("/generate-image", response_model=dict)
async def generate_image(
    request: GenerateImageRequest,
    service: ContentService = Depends(get_content_service),
    llm_client: LLMClientBase = Depends(get_llm_client)
) -> Dict[str, Any]:
    """
    Generate an image based on recent conversation context.
    
    This endpoint:
    1. Analyzes recent session messages
    2. Generates appropriate image prompts using LLM
    3. Creates image using text-to-image service
    4. Saves generated image to session folder
    
    Args:
        request: Image generation request with session_id
        
    Returns:
        Dict[str, Any]: Image generation result with structure:
            - success: bool - Operation success flag
            - image_path: str - Local path to saved image (if successful)
            - error: str - Error message (if failed)
    
    Raises:
        HTTPException: 500 if image generation fails
    """
    try:
        result = await service.generate_image_for_session(
            session_id=request.session_id,
            llm_client=llm_client
        )
        
        if not result.get("success"):
            error_msg = result.get("error", "Image generation failed")
            print(f"[ERROR] Image generation failed: {error_msg}")
            
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/generate-video", response_model=dict)
async def generate_video(
    request: GenerateVideoRequest,
    service: ContentService = Depends(get_content_service),
    llm_client: LLMClientBase = Depends(get_llm_client)
) -> Dict[str, Any]:
    """
    Generate a video from the most recent image in conversation context.
    
    This endpoint:
    1. Finds the most recent generated image in the session
    2. Extracts the original text-to-image prompt from history
    3. Optimizes the prompt for video motion using LLM
    4. Generates video using image-to-video service
    5. Saves generated video to session folder
    
    Args:
        request: Video generation request with session_id and optional motion_style
        
    Returns:
        Dict[str, Any]: Video generation result with structure:
            - success: bool - Operation success flag
            - video_path: str - Local path to saved video (if successful)
            - error: str - Error message (if failed)
    
    Raises:
        HTTPException: 500 if video generation fails
    """
    try:
        result = await service.generate_video_for_session(
            session_id=request.session_id,
            motion_style=request.motion_style,
            llm_client=llm_client
        )
        
        if not result.get("success"):
            error_msg = result.get("error", "Video generation failed")
            print(f"[ERROR] Video generation failed: {error_msg}")
            
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }