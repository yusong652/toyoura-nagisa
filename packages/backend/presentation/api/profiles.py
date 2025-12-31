"""
Agent Profiles API (2025 Standard).

Provides agent profile information for frontend UI.
This is a read-only API that returns available profiles and their metadata.

Routes:
    GET /api/profiles - List all available profiles
"""
from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.presentation.models.api_models import ApiResponse
from backend.presentation.exceptions import InternalServerError
from backend.domain.models.agent_profiles import AgentProfile, get_profile_config

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


# =====================
# Response Data Models
# =====================
class ProfileInfo(BaseModel):
    """Agent profile metadata for UI display."""
    profile_type: str = Field(..., description="Profile identifier")
    name: str = Field(..., description="Display name")
    description: str = Field(..., description="Profile description")
    tool_count: int = Field(..., description="Number of tools available")
    estimated_tokens: int = Field(..., description="Estimated token usage")
    color: str = Field(..., description="UI color theme (hex)")
    icon: str = Field(..., description="Display icon (emoji)")


class ProfileListData(BaseModel):
    """Response data for profile list."""
    profiles: List[ProfileInfo] = Field(..., description="Available profiles")


# =====================
# Helper Functions
# =====================
def _get_profile_info(profile: AgentProfile) -> ProfileInfo:
    """Get profile information from domain layer configuration."""
    try:
        config = get_profile_config(profile)
        return ProfileInfo(
            profile_type=profile.value,
            name=config.display_name,
            description=config.description,
            tool_count=config.tool_count,
            estimated_tokens=config.estimated_tokens,
            color=config.color,
            icon=config.icon
        )
    except Exception:
        # Fallback for any profile that might not be configured
        return ProfileInfo(
            profile_type=profile.value,
            name=profile.value.title(),
            description=f"{profile.value.title()} assistant mode",
            tool_count=0,
            estimated_tokens=0,
            color="#9E9E9E",
            icon="🤖"
        )


# =====================
# API Endpoints
# =====================
@router.get("/", response_model=ApiResponse[ProfileListData])
async def get_available_profiles() -> ApiResponse[ProfileListData]:
    """Get all available agent profiles with their metadata.

    This is a read-only endpoint that provides profile information for UI display.
    No state is managed on the backend - profiles are selected per-request.
    """
    try:
        profiles = [_get_profile_info(profile) for profile in AgentProfile]

        return ApiResponse(
            success=True,
            message=f"Retrieved {len(profiles)} profiles",
            data=ProfileListData(profiles=profiles)
        )
    except Exception as e:
        raise InternalServerError(
            message=f"Failed to get profiles: {str(e)}"
        )
