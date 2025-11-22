"""
Video generation API endpoints
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import FileResponse
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from backend.application.services.contents import VideoService
from backend.infrastructure.llm.base.client import LLMClientBase

router = APIRouter()

# Get absolute path to project root chat/data directory
# Navigate from packages/backend/presentation/api/ to project root
# packages/backend/presentation/api/videos.py -> packages/backend/presentation/api -> packages/backend/presentation -> packages/backend -> packages -> project_root
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "chat" / "data"

class VideoGenerationRequest(BaseModel):
    session_id: str
    motion_style: Optional[str] = None

def get_video_service() -> VideoService:
    """
    Get Video service instance.

    Returns:
        VideoService: Service instance for video operations
    """
    return VideoService()

def get_llm_client(request: Request) -> LLMClientBase:
    """
    Get LLM client from app state.
    
    Args:
        request: FastAPI request instance containing app state
        
    Returns:
        LLMClientBase: LLM client instance
    """
    return request.app.state.llm_client

@router.get("/videos/{video_path:path}")
async def get_video(video_path: str):
    """
    API route for video file access.
    
    Args:
        video_path: Relative video path in format session_id/filename
        
    Returns:
        FileResponse: Video file response
    """
    try:
        # Construct full path using absolute path
        full_path = BASE_DIR / video_path
        # Security check: ensure path is within allowed directory
        if not str(full_path.resolve()).startswith(str(BASE_DIR.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")
        # Check if file exists
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Determine media type based on file extension
        suffix = full_path.suffix.lower()
        if suffix == '.mp4':
            media_type = "video/mp4"
        elif suffix == '.gif':
            media_type = "image/gif"
        elif suffix == '.webm':
            media_type = "video/webm"
        else:
            media_type = "application/octet-stream"
        
        # Return video file
        return FileResponse(
            full_path,
            media_type=media_type,
            headers={"Cache-Control": "public, max-age=31536000"}  # Cache for one year
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-video")
async def generate_video(
    request: VideoGenerationRequest,
    service: VideoService = Depends(get_video_service),
    llm_client: LLMClientBase = Depends(get_llm_client)
):
    """
    Generate video from the most recent image in conversation context.
    
    Args:
        request: Video generation request with session_id and motion_style
        
    Returns:
        dict: Generation result with success status and video data
    """
    try:
        result = await service.generate_video_for_session(
            session_id=request.session_id,
            motion_style=request.motion_style,
            llm_client=llm_client
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))