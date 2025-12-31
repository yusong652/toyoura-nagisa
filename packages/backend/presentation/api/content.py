"""
Content Generation API (2025 Standard).

Handles content generation endpoints including title, image, and video generation.

Routes:
    POST /content/title    - Generate session title
    POST /content/image    - Generate image from conversation
    POST /content/video    - Generate video from image
"""
from typing import Optional
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from backend.presentation.models.api_models import ApiResponse
from backend.presentation.exceptions import (
    BadRequestError,
    SessionNotFoundError,
    InternalServerError,
)
from backend.application.services.contents import TitleService, ImageService, VideoService
from backend.infrastructure.llm.base.client import LLMClientBase

router = APIRouter(tags=["content"])


# =====================
# Response Data Models
# =====================
class TitleGenerateData(BaseModel):
    """Response data for title generation."""
    session_id: str = Field(..., description="Session that received new title")
    title: str = Field(..., description="Generated title text")


class ImageGenerateData(BaseModel):
    """Response data for image generation."""
    image_path: Optional[str] = Field(default=None, description="Path to generated image")


class VideoGenerateData(BaseModel):
    """Response data for video generation."""
    video_path: Optional[str] = Field(default=None, description="Path to generated video")


# =====================
# Request Models
# =====================
class GenerateTitleRequest(BaseModel):
    """Request body for title generation."""
    session_id: str = Field(..., description="Session ID to generate title for")


class GenerateImageRequest(BaseModel):
    """Request body for image generation."""
    session_id: str = Field(..., description="Session ID")


class GenerateVideoRequest(BaseModel):
    """Request body for video generation."""
    session_id: str = Field(..., description="Session ID")
    motion_style: Optional[str] = Field(
        default=None,
        description="Motion style description (e.g., 'cinematic camera movement')"
    )


# =====================
# Dependency Injection
# =====================
def get_title_service() -> TitleService:
    """Dependency injection for TitleService."""
    return TitleService()


def get_image_service() -> ImageService:
    """Dependency injection for ImageService."""
    return ImageService()


def get_video_service() -> VideoService:
    """Dependency injection for VideoService."""
    return VideoService()


def get_llm_client(request: Request) -> LLMClientBase:
    """Get LLM client from app state."""
    return request.app.state.llm_client


# =====================
# API Endpoints
# =====================
@router.post("/content/title", response_model=ApiResponse[TitleGenerateData])
async def generate_title(
    request: GenerateTitleRequest,
    http_request: Request,
    service: TitleService = Depends(get_title_service),
    llm_client: LLMClientBase = Depends(get_llm_client)
) -> ApiResponse[TitleGenerateData]:
    """Generate a descriptive title for a chat session.

    Analyzes conversation history and uses LLM to generate a contextual title.
    """
    try:
        result = await service.generate_title_for_session(
            session_id=request.session_id,
            llm_client=llm_client
        )

        if not result:
            raise SessionNotFoundError(request.session_id)

        if result.get("error"):
            raise BadRequestError(message=result["error"])

        return ApiResponse(
            success=True,
            message="Title generated successfully",
            data=TitleGenerateData(
                session_id=request.session_id,
                title=result.get("title", "")
            )
        )
    except (SessionNotFoundError, BadRequestError):
        raise
    except Exception as e:
        raise InternalServerError(
            message=f"Failed to generate title: {str(e)}"
        )


@router.post("/content/image", response_model=ApiResponse[ImageGenerateData])
async def generate_image(
    request: GenerateImageRequest,
    http_request: Request,
    service: ImageService = Depends(get_image_service),
    llm_client: LLMClientBase = Depends(get_llm_client)
) -> ApiResponse[ImageGenerateData]:
    """Generate an image based on recent conversation context.

    Analyzes recent messages, generates prompts using LLM,
    and creates image using text-to-image service.
    """
    try:
        result = await service.generate_image_for_session(
            session_id=request.session_id,
            llm_client=llm_client
        )

        if not result.get("success"):
            error_msg = result.get("error", "Image generation failed")
            raise InternalServerError(message=error_msg)

        return ApiResponse(
            success=True,
            message="Image generated successfully",
            data=ImageGenerateData(image_path=result.get("image_path"))
        )
    except InternalServerError:
        raise
    except Exception as e:
        raise InternalServerError(
            message=f"Failed to generate image: {str(e)}"
        )


@router.post("/content/video", response_model=ApiResponse[VideoGenerateData])
async def generate_video(
    request: GenerateVideoRequest,
    http_request: Request,
    service: VideoService = Depends(get_video_service),
    llm_client: LLMClientBase = Depends(get_llm_client)
) -> ApiResponse[VideoGenerateData]:
    """Generate a video from the most recent image in conversation.

    Finds recent image, optimizes prompt for motion using LLM,
    and generates video using image-to-video service.
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
        raise InternalServerError(
            message=f"Failed to generate video: {str(e)}"
        )


# =====================
# Legacy Routes (deprecated)
# =====================
@router.post("/history/generate-title", response_model=ApiResponse[TitleGenerateData], deprecated=True)
async def generate_title_legacy(
    http_request: Request,
    service: TitleService = Depends(get_title_service),
    llm_client: LLMClientBase = Depends(get_llm_client)
) -> ApiResponse[TitleGenerateData]:
    """[DEPRECATED] Use POST /content/title instead."""
    data = await http_request.json()
    session_id = data.get('session_id')
    if not session_id:
        raise BadRequestError(message="session_id not provided in request")
    request = GenerateTitleRequest(session_id=session_id)
    return await generate_title(request, http_request, service, llm_client)


@router.post("/generate-image", response_model=ApiResponse[ImageGenerateData], deprecated=True)
async def generate_image_legacy(
    request: GenerateImageRequest,
    http_request: Request,
    service: ImageService = Depends(get_image_service),
    llm_client: LLMClientBase = Depends(get_llm_client)
) -> ApiResponse[ImageGenerateData]:
    """[DEPRECATED] Use POST /content/image instead."""
    return await generate_image(request, http_request, service, llm_client)


@router.post("/generate-video", response_model=ApiResponse[VideoGenerateData], deprecated=True)
async def generate_video_legacy(
    request: GenerateVideoRequest,
    http_request: Request,
    service: VideoService = Depends(get_video_service),
    llm_client: LLMClientBase = Depends(get_llm_client)
) -> ApiResponse[VideoGenerateData]:
    """[DEPRECATED] Use POST /content/video instead."""
    return await generate_video(request, http_request, service, llm_client)
