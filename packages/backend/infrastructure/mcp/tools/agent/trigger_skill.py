"""trigger_skill tool - load skill instructions into conversation context.

This tool enables the agent to trigger a skill and receive its full instructions,
following the same pattern as Claude Code's Skill tool.

Design principles:
- Skills provide on-demand instructions/knowledge
- Full SKILL.md content is returned as tool_result
- Agent uses skill content to guide subsequent actions
"""

import logging
from typing import Any, Dict
from pydantic import Field
from fastmcp import FastMCP
from fastmcp.server.context import Context

from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.skills import get_skills_loader

logger = logging.getLogger(__name__)

__all__ = ["trigger_skill", "register_trigger_skill_tool"]


async def trigger_skill(
    context: Context,
    skill: str = Field(
        ...,
        description="The skill name to trigger (e.g., 'example', 'commit', 'test')"
    ),
    args: str = Field(
        default="",
        description="Optional arguments to pass to the skill"
    ),
) -> Dict[str, Any]:
    """Trigger and load a skill's full instructions into the conversation context.

    This tool loads the complete SKILL.md content for a registered skill,
    making its instructions available for the agent to follow.

    Skills are defined in .nagisa/skills/<skill-name>/SKILL.md and provide
    specialized workflows, best practices, or domain knowledge.

    Usage:
    - Use when you need specialized guidance for a task
    - The skill content will be returned and you should follow its instructions
    - Check available skills in your system prompt's <available_skills> section

    Example:
    - trigger_skill(skill="commit") - Load commit workflow instructions
    - trigger_skill(skill="test", args="UserService") - Load test instructions for UserService
    """
    try:
        loader = get_skills_loader()

        # Check if skill exists
        skill_metadata = loader.get_skill(skill)
        if not skill_metadata:
            available = loader.list_skills()
            return error_response(
                f"Skill '{skill}' not found. Available skills: {', '.join(available) if available else 'none'}",
                requested_skill=skill,
                available_skills=available
            )

        # Load full skill content
        content = loader.get_skill_content(skill)
        if not content:
            return error_response(
                f"Failed to load content for skill '{skill}'",
                requested_skill=skill
            )

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
            base_dir=str(skill_metadata.base_dir),
        )

    except Exception as e:
        logger.error(f"Failed to trigger skill '{skill}': {e}", exc_info=True)
        return error_response(
            f"Failed to trigger skill: {str(e)}",
            requested_skill=skill
        )


def register_trigger_skill_tool(mcp: FastMCP):
    """Register the trigger_skill tool with metadata."""
    mcp.tool(
        tags={"skill", "workflow", "instructions", "knowledge"},
        annotations={
            "category": "agent",
            "tags": ["skill", "workflow", "instructions", "knowledge"],
            "primary_use": "Load skill instructions for specialized workflows",
            "prompt_optimization": "Claude Code Skill tool compatible interface",
        }
    )(trigger_skill)
