"""
Agent Profiles Information API - Read-only profile information endpoint.

Provides agent profile information for frontend UI without managing state.
This is a query-only API that returns available profiles and their metadata.
"""

from fastapi import APIRouter
from typing import List, Dict, Any
from backend.infrastructure.mcp.tool_profile_manager import ToolProfileManager, AgentProfile

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


def _get_profile_info(profile: AgentProfile) -> Dict[str, Any]:
    """Get profile information from ToolProfileManager."""
    try:
        config = ToolProfileManager.get_profile(profile)
        return {
            "profile_type": profile.value,
            "name": config.name,
            "description": config.description,
            "tool_count": len(config.tools) if config.tools else 0,
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
        profiles = []
        
        # Add all configured profiles
        for profile in AgentProfile:
            profile_info = _get_profile_info(profile)
            profiles.append(profile_info)
        
        # Add special "disabled" profile
        profiles.append({
            "profile_type": "disabled",
            "name": "Disabled",
            "description": "Pure text conversation mode with all tools disabled",
            "tool_count": 0,
            "estimated_tokens": 0,
            "color": "#9E9E9E",
            "icon": "🚫"
        })
        
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