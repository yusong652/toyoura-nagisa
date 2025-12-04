"""
Agent Profiles Information API - Read-only profile information endpoint.

Provides agent profile information for frontend UI without managing state.
This is a query-only API that returns available profiles and their metadata.
"""

from fastapi import APIRouter
from typing import Dict, Any

from backend.domain.models.agent_profiles import AgentProfile, get_profile_config

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


def _get_profile_info(profile: AgentProfile) -> Dict[str, Any]:
    """Get profile information from domain layer configuration."""
    try:
        config = get_profile_config(profile)
        return {
            "profile_type": profile.value,
            "name": config.display_name,
            "description": config.description,
            "tool_count": config.tool_count,
            "estimated_tokens": config.estimated_tokens,
            "color": config.color,
            "icon": config.icon
        }
    except Exception as e:
        # Fallback for any profile that might not be configured
        return {
            "profile_type": profile.value,
            "name": profile.value.title(),
            "description": f"{profile.value.title()} assistant mode",
            "tool_count": 0,
            "estimated_tokens": 0,
            "color": "#9E9E9E",
            "icon": "🤖"
        }


@router.get("/")
async def get_available_profiles() -> Dict[str, Any]:
    """
    Get all available agent profiles with their metadata.
    
    This is a read-only endpoint that provides profile information for UI display.
    No state is managed on the backend - profiles are selected per-request.
    
    Returns:
        Dict with available profiles information including:
        - profile_type: Profile identifier
        - name: Display name
        - description: Profile description  
        - tool_count: Number of tools available
        - estimated_tokens: Estimated token usage
        - color: UI color theme
        - icon: Display icon
    """
    try:
        # Add all configured profiles (includes DISABLED)
        profiles = [_get_profile_info(profile) for profile in AgentProfile]

        return {
            "success": True,
            "profiles": profiles,
            "message": "Available agent profiles retrieved successfully"
        }
        
    except Exception as e:
        print(f"[ERROR] Get available profiles failed: {e}")
        return {
            "success": False,
            "profiles": [],
            "error": f"Failed to get profiles: {str(e)}"
        }