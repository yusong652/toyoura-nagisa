"""trigger_skill tool - load skill instructions into conversation context.

This tool enables the agent to trigger a skill and receive its full instructions,
following the same pattern as Claude Code's Skill tool.

Design principles:
- Skills provide on-demand instructions/knowledge
- Full SKILL.md content is returned as tool_result
- Agent uses skill content to guide subsequent actions
"""

import logging
from typing import Any, Dict, List, Optional

from pydantic import Field

from backend.application.tools.registrar import ToolRegistrar
from backend.application.tools.context import ToolContext
# from fastmcp.server.context import Context

from backend.shared.utils.tool_result import success_response, error_response
from backend.infrastructure.skills import get_skills_loader
from .utils import get_skill_literal_type, get_skill_description

logger = logging.getLogger(__name__)

__all__ = ["register_trigger_skill_tool", "build_trigger_skill_handler"]


async def _execute_trigger_skill(
    *,
    skill: str,
    args: str,
    enabled_skills: Optional[List[str]] = None,
) -> Dict[str, Any]:
    try:
        if enabled_skills is not None and not enabled_skills:
            return error_response(
                "No skills are enabled for this session. Use /skills command to enable skills.",
                requested_skill=skill,
            )

        loader = get_skills_loader()
        if not loader.list_skills():
            return error_response(
                "No skills are available. Add skills under .nagisa/skills to enable them.",
                requested_skill=skill,
            )

        content = loader.get_skill_content(skill)

        # Include args in response if provided
        if args:
            content = f"Arguments: {args}\n\n{content}"

        return success_response(
            message=f"Skill '{skill}' loaded successfully",
            llm_content={
                "parts": [{
                    "type": "text",
                    "text": content
                }]
            },
            skill_name=skill,
        )

    except Exception as e:
        logger.error(f"Failed to trigger skill '{skill}': {e}", exc_info=True)
        return error_response(
            f"Failed to trigger skill: {str(e)}",
            requested_skill=skill,
        )


def build_trigger_skill_handler(enabled_skills: Optional[List[str]] = None):
    """Build trigger_skill handler with optional session-specific skill constraints."""
    if enabled_skills is None:
        SkillType = get_skill_literal_type()
        skill_description = get_skill_description()
    elif enabled_skills:
        from typing import Literal

        SkillType = Literal[tuple(enabled_skills)]  # type: ignore
        examples = ", ".join(f'"{s}"' for s in enabled_skills[:3])
        skill_description = f"The skill name. Available: {examples}"
    else:
        SkillType = str
        skill_description = "No skills enabled for this session"

    async def trigger_skill(
        context: ToolContext,
        skill: SkillType = Field(..., description=skill_description),  # type: ignore
        args: str = Field(default="", description="Optional arguments for the skill"),
    ) -> Dict[str, Any]:
        """Execute a skill to load specialized workflow instructions.

        When a skill is relevant to the task, invoke this tool IMMEDIATELY.
        The skill's full instructions will be returned for you to follow.

        Skills provide domain-specific knowledge and step-by-step guidance.
        Check <available_skills> in your system prompt for available skills.
        """
        return await _execute_trigger_skill(
            skill=skill,
            args=args,
            enabled_skills=enabled_skills,
        )

    return trigger_skill


def register_trigger_skill_tool(registrar: ToolRegistrar):
    """
    Register the trigger_skill tool with dynamic Literal type validation.

    The skill parameter uses a Literal type containing all available skill names,
    providing semantic clarity for LLM and runtime validation.
    """
    # Get dynamic type and description at registration time
    # TODO: Currently, the Literal type includes ALL skills from .nagisa/skills/, 
    # not filtered by agent profile. The system prompt's {available_skills} section
    # IS profile-filtered, so LLM guidance works correctly. However, if we need
    # different agents to have different skill schemas (e.g., SubAgents with skills),
    # we'll need to research FastMCP's dynamic tool registration mechanism or
    # consider per-profile MCP server instances.
    handler = build_trigger_skill_handler()
    registrar.tool(
        tags={"skill", "workflow", "instructions", "knowledge"},
        annotations={
            "category": "agent",
            "tags": ["skill", "workflow", "instructions", "knowledge"],
            "primary_use": "Load skill instructions for specialized workflows",
        },
    )(handler)

    logger.info("Registered trigger_skill tool with dynamic skill type")
