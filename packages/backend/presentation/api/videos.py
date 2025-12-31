"""
Video File Serving API (2025 Standard).

Provides static file serving for generated videos stored in chat/data.

Routes:
    GET /videos/{video_path} - Serve video file

Note: This endpoint returns FileResponse (binary data), not ApiResponse.
Legacy /generate-video route is deprecated - use /content/video instead.
"""
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Request, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.presentation.models.api_models import ApiResponse
from backend.presentation.exceptions import (
    FileNotFoundError,
    AccessDeniedError,
    InternalServerError,
)
from backend.application.services.contents import VideoService
from backend.infrastructure.llm.base.client import LLMClientBase

router = APIRouter(tags=["media"])

# Get absolute path to project root chat/data directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "chat" / "data"


# =====================
# Response Data Models
# =====================
class VideoGenerateData(BaseModel):
    """Response data for video generation."""
    video_path: Optional[str] = Field(default=None, description="Path to generated video")


# =====================
# Request Models
# =====================
class VideoGenerationRequest(BaseModel):
    """Request body for video generation."""
    session_id: str = Field(..., description="Session ID")
    motion_style: Optional[str] = Field(
        default=None,
        description="Motion style description (e.g., 'cinematic camera movement')"
    )


# =====================
# Dependency Injection
# =====================
def get_video_service() -> VideoService:
    """Dependency injection for VideoService."""
    return VideoService()


def get_llm_client(request: Request) -> LLMClientBase:
    """Get LLM client from app state."""
    return request.app.state.llm_client


# =====================
# API Endpoints
# =====================
@router.get("/videos/{video_path:path}")
async def get_video(video_path: str) -> FileResponse:
    """Serve video file from chat/data storage.

    Args:
        video_path: Relative video path in format session_id/filename

    Returns:
        FileResponse with video data
    """
    full_path = BASE_DIR / video_path

    # Security check: ensure path is within allowed directory
    if not str(full_path.resolve()).startswith(str(BASE_DIR.resolve())):
        raise AccessDeniedError(
            resource=f"video:{video_path}",
            reason="Path traversal not allowed"
        )

    # Check if file exists
    if not full_path.exists():
        raise FileNotFoundError(file_path=video_path)

    # Determine media type based on file extension
    suffix = full_path.suffix.lower()
    media_type_map = {
        ".mp4": "video/mp4",
        ".gif": "image/gif",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
    }
    media_type = media_type_map.get(suffix, "application/octet-stream")

    return FileResponse(
        full_path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=31536000"}
    )


# =====================
# Legacy Routes (deprecated)
# =====================
@router.post("/generate-video", response_model=ApiResponse[VideoGenerateData], deprecated=True)
async def generate_video_legacy(
    request: VideoGenerationRequest,
    http_request: Request,
    service: VideoService = Depends(get_video_service),
    llm_client: LLMClientBase = Depends(get_llm_client)
) -> ApiResponse[VideoGenerateData]:
    """[DEPRECATED] Use POST /content/video instead.

    Generate video from the most recent image in conversation context.
    """
    try:
        result = await service.generate_video_for_session(
            session_id=request.session_id,
            motion_style=request.motion_style,
            llm_client=llm_client
        )

        if not result.get("success"):
            error_msg = result.get("error", "Video generation failed")
            raise InternalServerError(message=error_msg)

        return ApiResponse(
            success=True,
            message="Video generated successfully",
            data=VideoGenerateData(video_path=result.get("video_path"))
        )
    except InternalServerError:
        raise
    except Exception as e:
        raise InternalServerError(message=f"Failed to generate video: {str(e)}")
