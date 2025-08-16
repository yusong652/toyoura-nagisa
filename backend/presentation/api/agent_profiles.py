"""
Agent Profile API Endpoints - Agent profile management and switching functionality.

Provides agent profile management features including switching profiles,
getting available profiles list, and profile status information.
"""

from fastapi import APIRouter, HTTPException, Request

from backend.presentation.models.agent_profile_models import (
    UpdateAgentProfileRequest,
    AgentProfileResponse, 
    GetAgentProfilesResponse,
    AgentProfileInfo,
    AgentProfileType
)
from backend.infrastructure.mcp.tool_profile_manager import ToolProfileManager, AgentProfile
from backend.infrastructure.llm import LLMClientBase


router = APIRouter(prefix="/api/agent", tags=["agent-profiles"])

# Global state: current agent profile
_current_agent_profile: AgentProfileType = AgentProfileType.GENERAL



def _convert_profile_type_to_enum(profile_type: AgentProfileType) -> AgentProfile:
    """Convert API enum to internal enum."""
    if profile_type == AgentProfileType.DISABLED:
        # DISABLED profile should be handled separately in business logic
        raise ValueError("DISABLED profile should be handled separately")
    
    mapping = {
        AgentProfileType.CODING: AgentProfile.CODING,
        AgentProfileType.LIFESTYLE: AgentProfile.LIFESTYLE,
        AgentProfileType.GENERAL: AgentProfile.GENERAL
    }
    return mapping[profile_type]


def _create_profile_info(profile_type: AgentProfileType) -> AgentProfileInfo:
    """Create agent profile information."""
    if profile_type == AgentProfileType.DISABLED:
        return AgentProfileInfo(
            profile_type=profile_type,
            name="Disabled",
            description="All tools disabled, pure text conversation mode",
            tool_count=0,
            estimated_tokens=0,
            color="#9E9E9E",  # Gray color
            icon="🚫"
        )
    
    try:
        profile_enum = _convert_profile_type_to_enum(profile_type)
        profile_config = ToolProfileManager.get_profile(profile_enum)
        
        return AgentProfileInfo(
            profile_type=profile_type,
            name=profile_config.name,
            description=profile_config.description,
            tool_count=len(profile_config.tools) if profile_config.tools else 30,
            estimated_tokens=profile_config.estimated_tokens,
            color=profile_config.color,
            icon=profile_config.icon
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid profile type: {profile_type}")


@router.post("/profile", response_model=AgentProfileResponse)
async def update_agent_profile(request: UpdateAgentProfileRequest, api_request: Request):
    """
    Switch agent profile.
    
    Supported profile types:
    - coding: Coding assistant (focused development tools)
    - lifestyle: Lifestyle assistant (daily life tools)  
    - general: General assistant (all available tools)
    - disabled: Tools disabled (pure text conversation mode)
    """
    global _current_agent_profile
    
    try:
        print(f"[DEBUG] Agent profile switch request: {request.profile}")
        
        # Get LLM client
        llm_client: LLMClientBase = api_request.app.state.llm_client
        
        # Handle tools disabled case
        if request.profile == AgentProfileType.DISABLED:
            llm_client.update_config(tools_enabled=False)
            _current_agent_profile = AgentProfileType.DISABLED
            
            # Clear tool cache
            if request.session_id and hasattr(llm_client, '_clear_session_tool_cache'):
                await llm_client._clear_session_tool_cache(request.session_id)
            
            profile_info = _create_profile_info(AgentProfileType.DISABLED)
            
            return AgentProfileResponse(
                success=True,
                current_profile=AgentProfileType.DISABLED,
                profile_info=profile_info,
                tools_enabled=False,
                message="Switched to pure text conversation mode, all tools disabled"
            )
        
        # Enable tools and set profile
        llm_client.update_config(tools_enabled=True)
        
        # Update LLM client agent_profile (requires LLM client support)
        if hasattr(llm_client, 'update_agent_profile'):
            llm_client.update_agent_profile(request.profile.value)
        
        # Clear tool cache to apply new profile settings
        if request.session_id and hasattr(llm_client, '_clear_session_tool_cache'):
            await llm_client._clear_session_tool_cache(request.session_id)
            print(f"[DEBUG] Cleared tool cache for session: {request.session_id}")
        
        # Update global state
        _current_agent_profile = request.profile
        
        # Create response information
        profile_info = _create_profile_info(request.profile)
        
        print(f"[DEBUG] Agent profile switched to: {request.profile} ({profile_info.tool_count} tools)")
        
        return AgentProfileResponse(
            success=True,
            current_profile=request.profile,
            profile_info=profile_info,
            tools_enabled=True,
            message=f"Switched to {profile_info.name} mode, loaded {profile_info.tool_count} tools"
        )
        
    except Exception as e:
        import traceback
        print(f"[ERROR] Agent profile switch failed: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to switch agent profile: {str(e)}")


@router.get("/profiles", response_model=GetAgentProfilesResponse)
async def get_available_profiles():
    """Get all available agent profiles list."""
    global _current_agent_profile
    
    try:
        available_profiles = []
        
        # Add all supported profile types
        for profile_type in AgentProfileType:
            profile_info = _create_profile_info(profile_type)
            available_profiles.append(profile_info)
        
        return GetAgentProfilesResponse(
            success=True,
            current_profile=_current_agent_profile,
            available_profiles=available_profiles,
            message=f"Current agent profile: {_current_agent_profile.value}"
        )
        
    except Exception as e:
        print(f"[ERROR] Get available profiles failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get agent profiles list: {str(e)}")



@router.get("/status", response_model=dict)
async def get_agent_status(api_request: Request):
    """Get current agent status information."""
    global _current_agent_profile
    
    try:
        llm_client: LLMClientBase = api_request.app.state.llm_client
        tools_enabled = getattr(llm_client, 'tools_enabled', True)
        
        current_profile_info = _create_profile_info(_current_agent_profile)
        
        return {
            "success": True,
            "current_profile": _current_agent_profile,
            "profile_info": current_profile_info.model_dump(),
            "tools_enabled": tools_enabled,
            "message": f"Current mode: {current_profile_info.name}"
        }
        
    except Exception as e:
        print(f"[ERROR] Get agent status failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")