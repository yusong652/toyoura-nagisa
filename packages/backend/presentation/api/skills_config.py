"""
Skills Configuration API.

Provides endpoints for managing skill configuration per session.
Global defaults are defined in config/agents.yaml.
Session overrides are stored in session metadata.

Routes:
    GET /api/skills-config - Get skills configuration for a session
    POST /api/skills-config - Update skill enabled state for a session
    GET /api/skills-config/available - Get all available skills (global view)
"""

from typing import List, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.presentation.models.api_models import ApiResponse
from backend.presentation.exceptions import BadRequestError, InternalServerError
from backend.infrastructure.storage.session_manager import (
    get_session_skills_config,
    update_session_skill,
    get_session_metadata,
    is_skill_enabled_for_session,
)
from backend.domain.models.agent_profiles import get_skill_configs_for_agent, MAIN_AGENT_CONFIG
from backend.infrastructure.skills import get_skills_loader

router = APIRouter(prefix="/api/skills-config", tags=["skills-config"])


# =====================
# Request/Response Models
# =====================
class SkillStatus(BaseModel):
    """Status of a skill for a session."""

    name: str = Field(..., description="Skill identifier")
    description: str = Field(..., description="Skill description")
    enabled: bool = Field(..., description="Whether enabled for this session")
    available: bool = Field(..., description="Whether skill file exists and is valid")


class SkillsConfigData(BaseModel):
    """Skills configuration data for a session."""

    skills: List[SkillStatus] = Field(..., description="List of skills with their status")


class SkillUpdateRequest(BaseModel):
    """Request to update a skill's enabled state."""

    skill_name: str = Field(..., description="Skill identifier to update")
    enabled: bool = Field(..., description="Whether to enable this skill for the session")


# =====================
# API Endpoints
# =====================
@router.get("/", response_model=ApiResponse[SkillsConfigData])
async def get_skills_config(
    session_id: str = Query(..., description="Session ID to get configuration for"),
) -> ApiResponse[SkillsConfigData]:
    """
    Get skills configuration for a session.

    Returns the list of available skills with their:
    - enabled state (session-specific, falls back to global default)
    - availability status (whether skill file exists)
    - description
    """
    try:
        # Verify session exists
        if not get_session_metadata(session_id):
            raise BadRequestError(message=f"Session not found: {session_id}")

        # Get agent's skill configs (global defaults)
        agent_name = MAIN_AGENT_CONFIG.name
        agent_skills = get_skill_configs_for_agent(agent_name)

        # Get skills loader for metadata
        loader = get_skills_loader()

        # Build response
        skills = []
        for skill_config in agent_skills:
            # Get enabled state (session override > global default)
            enabled = is_skill_enabled_for_session(session_id, skill_config.name, agent_name)

            # Check if skill file exists and get description
            skill_metadata = loader.get_skill(skill_config.name)
            available = skill_metadata is not None
            description = skill_metadata.description if skill_metadata else f"Skill '{skill_config.name}' not found"

            skills.append(
                SkillStatus(
                    name=skill_config.name,
                    description=description,
                    enabled=enabled,
                    available=available,
                )
            )

        return ApiResponse(
            success=True,
            message="Retrieved skills configuration for session",
            data=SkillsConfigData(skills=skills),
        )

    except BadRequestError:
        raise
    except Exception as e:
        raise InternalServerError(message=f"Failed to get skills configuration: {str(e)}")


@router.post("/", response_model=ApiResponse[SkillStatus])
async def update_skill(
    request: SkillUpdateRequest,
    session_id: str = Query(..., description="Session ID to update"),
) -> ApiResponse[SkillStatus]:
    """
    Update a skill's enabled state for a session.

    This controls whether the skill is available in system prompt and can be triggered
    for this session.
    """
    try:
        # Verify session exists
        if not get_session_metadata(session_id):
            raise BadRequestError(message=f"Session not found: {session_id}")

        # Verify skill exists in agent config
        agent_name = MAIN_AGENT_CONFIG.name
        agent_skills = get_skill_configs_for_agent(agent_name)
        skill_names = [s.name for s in agent_skills]

        if request.skill_name not in skill_names:
            raise BadRequestError(message=f"Skill not found in agent config: {request.skill_name}")

        # Update session config
        success = update_session_skill(session_id, request.skill_name, request.enabled)
        if not success:
            raise InternalServerError(message="Failed to update skills configuration")

        # Get skill metadata for response
        loader = get_skills_loader()
        skill_metadata = loader.get_skill(request.skill_name)
        available = skill_metadata is not None
        description = skill_metadata.description if skill_metadata else f"Skill '{request.skill_name}' not found"

        return ApiResponse(
            success=True,
            message=f"Skill '{request.skill_name}' {'enabled' if request.enabled else 'disabled'} for session",
            data=SkillStatus(
                name=request.skill_name,
                description=description,
                enabled=request.enabled,
                available=available,
            ),
        )

    except BadRequestError:
        raise
    except Exception as e:
        raise InternalServerError(message=f"Failed to update skills configuration: {str(e)}")


@router.get("/available", response_model=ApiResponse[SkillsConfigData])
async def get_available_skills() -> ApiResponse[SkillsConfigData]:
    """
    Get list of all available skills (global view).

    Returns all configured skills from agent config regardless of session.
    Useful for admin views or when no session context is available.
    """
    try:
        agent_name = MAIN_AGENT_CONFIG.name
        agent_skills = get_skill_configs_for_agent(agent_name)
        loader = get_skills_loader()

        skills = []
        for skill_config in agent_skills:
            skill_metadata = loader.get_skill(skill_config.name)
            available = skill_metadata is not None
            description = skill_metadata.description if skill_metadata else f"Skill '{skill_config.name}' not found"

            skills.append(
                SkillStatus(
                    name=skill_config.name,
                    description=description,
                    enabled=skill_config.enabled,  # Global default
                    available=available,
                )
            )

        return ApiResponse(
            success=True,
            message=f"Retrieved {len(skills)} skills",
            data=SkillsConfigData(skills=skills),
        )

    except Exception as e:
        raise InternalServerError(message=f"Failed to get available skills: {str(e)}")
