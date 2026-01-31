"""Service for managing session-specific skill tool registration.

This service handles re-registration of the trigger_skill tool when
session skills configuration changes (e.g., via /skills command).

Architecture:
- Called when skills are enabled/disabled for a session
- Creates a new ToolDefinition with session-specific skill Literal type
- Registers the tool as a session override in TOOL_REGISTRY
"""

from __future__ import annotations

import logging
from typing import List

from backend.application.tools.registry import TOOL_REGISTRY, build_tool_override
from backend.application.tools.schema_builder import build_input_schema, get_tool_description
from backend.application.tools.agent.trigger_skill import build_trigger_skill_handler

logger = logging.getLogger(__name__)


def register_session_trigger_skill(session_id: str, enabled_skills: List[str]) -> None:
    """Register a session-specific trigger_skill tool.
    
    Creates a new ToolDefinition with the session's enabled skills as
    the Literal type for the skill parameter, and registers it as a
    session override in TOOL_REGISTRY.
    
    Args:
        session_id: Session identifier
        enabled_skills: List of skill names enabled for this session
    """
    # Create handler with session-specific skill type
    handler = build_trigger_skill_handler(enabled_skills)
    
    base_tool = TOOL_REGISTRY.get("trigger_skill")
    if base_tool is None:
        logger.error("trigger_skill is not registered; cannot build session override")
        return

    tool_def = build_tool_override(
        base_tool,
        description=get_tool_description(handler),
        input_schema=build_input_schema(handler),
        handler=handler,
        metadata={
            "session_id": session_id,
            "enabled_skills": enabled_skills,
        },
    )
    
    # Register as session override
    TOOL_REGISTRY.register_for_session(session_id, tool_def)
    
    logger.info(
        f"Registered trigger_skill for session {session_id} with skills: {enabled_skills}"
    )


def clear_session_trigger_skill(session_id: str) -> None:
    """Clear session-specific trigger_skill registration.
    
    Called when a session is deleted or when resetting to global defaults.
    
    Args:
        session_id: Session identifier
    """
    TOOL_REGISTRY.clear_session(session_id)
    logger.info(f"Cleared session tool overrides for session {session_id}")
