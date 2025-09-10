"""
API request and response models

Defines data transfer objects (DTOs) for Web API, including request and response structures.
These models are specifically used for the HTTP API layer, separated from domain models.
"""

from pydantic import BaseModel, Field
from typing import Optional


# =====================
# Basic response models
# =====================
class ErrorResponse(BaseModel):
    """API error response model"""
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
# Feature toggle models
# =====================
class UpdateToolsEnabledRequest(BaseModel):
    """Request model for updating tools enabled status"""
    enabled: bool


class UpdateTTSEnabledRequest(BaseModel):
    """Request model for updating TTS enabled status"""
    enabled: bool


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