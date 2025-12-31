"""
API request and response models

Defines data transfer objects (DTOs) for Web API, including request and response structures.
These models are specifically used for the HTTP API layer, separated from domain models.

Response Format Standard (2025):
- All API endpoints return ApiResponse[T] for type-safe responses
- Error responses use StandardErrorResponse for consistent error handling
- HTTP status codes follow REST conventions (200, 201, 400, 404, 422, 500)
"""

from pydantic import BaseModel, Field
from typing import Optional, Generic, TypeVar, Any, Dict

T = TypeVar('T')


# =====================
# Unified Response Models (FastAPI 2025 Standard)
# =====================
class ApiResponse(BaseModel, Generic[T]):
    """Unified API response wrapper for all endpoints.

    Provides consistent response structure across all API endpoints,
    enabling type-safe client code and automatic OpenAPI documentation.

    Example:
        @router.get("/sessions/{id}", response_model=ApiResponse[SessionData])
        async def get_session(id: str) -> ApiResponse[SessionData]:
            return ApiResponse(
                success=True,
                message="Session retrieved",
                data=SessionData(...)
            )
    """
    success: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(..., description="Human-readable status message")
    data: Optional[T] = Field(default=None, description="Response payload (null on error)")
    error_code: Optional[str] = Field(default=None, description="Error code for client handling (null on success)")


class StandardErrorResponse(BaseModel):
    """Standardized error response for HTTPException detail.

    Used as the detail payload in HTTPException for consistent error handling.

    Example:
        raise HTTPException(
            status_code=404,
            detail=StandardErrorResponse(
                error_code="SESSION_NOT_FOUND",
                message="Session abc123 not found",
                details={"session_id": "abc123"}
            ).model_dump()
        )
    """
    error_code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error context")


# Legacy error response (deprecated, use StandardErrorResponse)
class ErrorResponse(BaseModel):
    """API error response model (deprecated: use StandardErrorResponse)"""
    detail: str = Field(..., description="Error message")


# =====================
# Session management models
# =====================
class NewHistoryRequest(BaseModel):
    """Request model for creating new history record"""
    name: Optional[str] = None


class HistorySessionResponse(BaseModel):
    """History session response model"""
    id: str
    name: str
    created_at: str
    updated_at: str


class SwitchSessionRequest(BaseModel):
    """Request model for switching session"""
    session_id: str


class DeleteSessionRequest(BaseModel):
    """Request model for deleting session"""
    session_id: str


# =====================
# Message management models
# =====================
class DeleteMessageRequest(BaseModel):
    """Request model for deleting message"""
    session_id: str
    message_id: str


# =====================
# Title generation models
# =====================
class GenerateTitleRequest(BaseModel):
    """Request model for generating title"""
    session_id: str


# =====================
# Image generation models
# =====================
class GenerateImageRequest(BaseModel):
    """Request model for one-click image generation"""
    session_id: str


# =====================
# Video generation models
# =====================
class GenerateVideoRequest(BaseModel):
    """Request model for video generation"""
    session_id: str
    motion_style: Optional[str] = Field(default=None, description="Motion style description (e.g., 'cinematic camera movement')")