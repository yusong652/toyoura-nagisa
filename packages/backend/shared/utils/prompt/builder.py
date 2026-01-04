"""
Main prompt builder functions combining all components.
"""

import logging
import sys
import platform
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from .core import get_base_prompt, get_expression_prompt
from backend.infrastructure.mcp.utils.path_normalization import normalize_path_separators
from backend.infrastructure.skills import get_skills_loader

logger = logging.getLogger(__name__)

# Placeholder for skills injection
SKILLS_PLACEHOLDER = "{available_skills}"


async def _get_workspace_root(agent_profile: str, session_id: Optional[str] = None) -> str:
    """
    Determine workspace root based on agent profile and session context.

    DEPRECATED: This function now delegates to the unified workspace module.
    New code should use backend.shared.utils.workspace.get_workspace_for_profile directly.

    Args:
        agent_profile: Agent profile type ("pfc", "coding", "general", etc.)
        session_id: Optional session ID (reserved for future use)

    Returns:
        Absolute workspace root path as string
    """
    from backend.shared.utils.workspace import get_workspace_for_profile
    workspace_path = await get_workspace_for_profile(agent_profile, session_id)
    return str(workspace_path)


def _build_env_info(workspace_root: str, session_id: Optional[str] = None) -> str:
    """
    Build environment information string similar to Claude Code.

    Args:
        workspace_root: Workspace root path (already normalized)
        session_id: Optional session ID for task isolation context

    Returns:
        Formatted environment information block
    """
    # Use the provided workspace root (already normalized to forward slashes)
    working_dir = workspace_root

    # Check if directory is a git repository
    is_git_repo = (Path(working_dir) / ".git").exists()

    # Get platform and OS version
    platform_name = sys.platform  # 'win32', 'linux', 'darwin', etc.
    os_version = platform.version()

    # Get current date
    current_date = datetime.now().strftime("%Y-%m-%d")

    # Truncate session_id to 8 characters for readability (consistent with task_id format)
    session_id_display = session_id[:8] if session_id else 'unknown'

    # Format environment information (Claude Code style)
    env_info = f"""<env>
Working directory: {working_dir}
Is directory a git repo: {'Yes' if is_git_repo else 'No'}
Platform: {platform_name}
OS Version: {os_version}
Today's date: {current_date}
session_id: {session_id_display}
</env>"""

    return env_info


def _get_available_skills_xml(
    project_root: Optional[Path] = None,
    allowed_skills: Optional[List[str]] = None
) -> str:
    """
    Get available skills XML for system prompt injection.

    Args:
        project_root: Project root directory for skills discovery
        allowed_skills: Optional list of skill names to include. If None, include all.

    Returns:
        XML string with available skills, or empty string if no skills
    """
    try:
        loader = get_skills_loader(project_root)

        # If no allowed_skills filter, return all
        if allowed_skills is None:
            return loader.get_available_skills_xml()

        # Filter skills based on allowed list
        skills_xml = "<available_skills>\n"
        for skill_name in allowed_skills:
            skill = loader.get_skill(skill_name)
            if skill:
                skill_xml = skill.to_xml()
                indented = "\n".join(f"  {line}" for line in skill_xml.split("\n"))
                skills_xml += indented + "\n"
            else:
                logger.warning(f"Configured skill '{skill_name}' not found in .nagisa/skills/")
        skills_xml += "</available_skills>"

        return skills_xml
    except Exception as e:
        logger.warning(f"Failed to load skills: {e}")
        return "<!-- Skills loading failed -->"


async def build_system_prompt(
    agent_profile: str = "general",
    session_id: Optional[str] = None,
    include_expression: bool = True,
) -> str:
    """
    Build complete system prompt following modern LLM best practices.

    This is the main entry point for creating system prompts with support for:
    - Base identity and instructions (profile-specific)
    - Expression/Live2D instructions (MainAgent only)

    Note: Memory context is now injected into user messages via ReminderInjector,
    not in the system prompt. This follows modern LLM best practices where dynamic
    context should be closer to the user's query.

    Note: Tool schemas are handled by native LLM API (tools parameter), not embedded
    in the system prompt. This follows 2025 Anthropic best practices.

    Args:
        agent_profile: Agent profile type ("general", "pfc", "coding", "lifestyle", "disabled")
                      For SubAgents, use the SubAgent name (e.g., "pfc_explorer")
        session_id: Session ID for workspace resolution
        include_expression: Whether to include expression/Live2D instructions (default True).
                           Set to False for SubAgents.

    Returns:
        Complete system prompt string
    """
    components = []

    # 1. Get base prompt (contains {workspace_root} and {env} placeholders)
    base = get_base_prompt(profile=agent_profile)
    if not base:
        logger.warning(f"No base prompt found for profile: {agent_profile}")
        base = ""

    # 2. Get workspace root for path substitution (dynamic based on profile and session)
    workspace_root = await _get_workspace_root(agent_profile, session_id)

    # Normalize workspace_root to forward slashes for LLM consistency
    # This ensures LLM always sees paths in the same format (like Claude Code)
    workspace_root = normalize_path_separators(workspace_root, target_platform='linux')

    # 4. Build environment information with session context and dynamic workspace
    env_info = _build_env_info(workspace_root=workspace_root, session_id=session_id)

    # 5. Replace placeholders in base prompt
    # Note: {tool_schemas} placeholder removed from prompts - tools via native API
    base = base.replace("{workspace_root}", workspace_root)
    base = base.replace("{env}", env_info)

    # 6. Replace {available_skills} placeholder if present
    if SKILLS_PLACEHOLDER in base:
        # Get allowed skills for this profile
        from backend.domain.models.agent_profiles import get_skills_for_profile
        allowed_skills = get_skills_for_profile(agent_profile)

        # Use workspace root as project root for skills discovery
        project_root = Path(workspace_root)
        skills_xml = _get_available_skills_xml(project_root, allowed_skills if allowed_skills else None)
        base = base.replace(SKILLS_PLACEHOLDER, skills_xml)

    # Add base prompt as first component
    if base:
        components.append(base)

    # 5. Expression/Live2D instructions (MainAgent only)
    if include_expression:
        expression = get_expression_prompt()
        if expression:
            components.append(expression)

    # Join all components with separators
    return "\n\n---\n\n".join(filter(None, components))




