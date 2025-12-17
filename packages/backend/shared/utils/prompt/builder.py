"""
Main prompt builder functions combining all components.
"""

import json
import logging
import sys
import platform
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from .core import get_base_prompt, get_expression_prompt
from .memory import build_memory_section_from_session
from backend.infrastructure.mcp.utils.path_normalization import normalize_path_separators

logger = logging.getLogger(__name__)


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


async def build_system_prompt(
    agent_profile: str = "general",
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    enable_memory: bool = False,
    tool_schemas: Optional[List[Dict[str, Any]]] = None,
    include_expression: bool = True,
) -> str:
    """
    Build complete system prompt following modern LLM best practices.

    This is the main entry point for creating system prompts with support for:
    - Base identity and instructions (profile-specific)
    - Automatic memory context injection from conversation history
    - Expression/Live2D instructions (MainAgent only)

    Note: Tool schemas are NO LONGER embedded in the system prompt.
    Modern LLM APIs (Anthropic, Gemini, OpenAI) handle tool definitions natively
    via the `tools` API parameter. Embedding schemas in the prompt was a legacy
    practice that caused token waste and potential confusion from duplicate definitions.

    Args:
        agent_profile: Agent profile type ("general", "pfc", "coding", "lifestyle", "disabled")
                      For SubAgents, use the SubAgent name (e.g., "pfc_explorer")
        session_id: Session ID for memory retrieval
        user_id: User ID for memory operations
        enable_memory: Whether to enable memory injection (controlled by frontend)
        tool_schemas: DEPRECATED - kept for API compatibility but no longer used.
                     Tools are passed via native API parameter instead.
        include_expression: Whether to include expression/Live2D instructions (default True).
                           Set to False for SubAgents.

    Returns:
        Complete system prompt string with memory context
    """
    components = []

    # 1. Get base prompt (contains {workspace_root} and {env} placeholders)
    base = get_base_prompt(profile=agent_profile)
    if not base:
        logger.warning(f"No base prompt found for profile: {agent_profile}")
        base = ""

    # 2. Tool schemas are now handled by native LLM API (tools parameter)
    # No longer embedded in system prompt - this was legacy behavior that caused
    # duplicate definitions and wasted tokens. See 2025 Anthropic best practices.

    # 3. Get workspace root for path substitution (dynamic based on profile and session)
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

    # Add base prompt as first component
    if base:
        components.append(base)

    # 5. Memory context injection (if enabled)
    if enable_memory and session_id:
        memory_content = await build_memory_section_from_session(session_id, user_id)
        if memory_content:
            components.append(f"## Relevant Context from Memory\n\n{memory_content}")
        else:
            components.append("## Relevant Context from Memory\n\n(No relevant memories found for current query)")

    # 6. Expression/Live2D instructions (MainAgent only)
    if include_expression:
        expression = get_expression_prompt()
        if expression:
            components.append(expression)

    # Join all components with separators
    return "\n\n---\n\n".join(filter(None, components))




