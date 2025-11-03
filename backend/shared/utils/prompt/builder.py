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


def _get_workspace_root(agent_profile: str, session_id: Optional[str] = None) -> str:
    """
    Determine workspace root based on agent profile and session context.

    Workspace Strategy:
        - PFC profile with PFC server connected: Use PFC server's actual working directory
          → Ensures agent can access files saved by PFC (e.g., checkpoints, data)
        - PFC profile without PFC server: Fallback to local workspace
          → aiNagisa/pfc_workspace (standalone mode)
        - Other profiles (coding, general, lifestyle, etc.): Unified workspace
          → aiNagisa/workspace

    Args:
        agent_profile: Agent profile type ("pfc", "coding", "general", etc.)
        session_id: Optional session ID (reserved for future use, currently unused)

    Returns:
        Absolute workspace root path as string

    Note:
        For PFC profile, session_id is currently not used for workspace isolation
        because PFC server's working directory is determined by the PFC project itself.
    """
    # PFC-specific workspace logic
    if agent_profile == "pfc":
        # Try to get PFC server's actual working directory
        try:
            import asyncio
            from backend.infrastructure.pfc.websocket_client import get_client

            # Attempt to query PFC server's working directory
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # No event loop in current thread, create new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            try:
                client = loop.run_until_complete(get_client())
                pfc_working_dir = loop.run_until_complete(client.get_working_directory())

                if pfc_working_dir:
                    logger.info(f"✓ Using PFC server's working directory: {pfc_working_dir}")
                    return pfc_working_dir
                else:
                    logger.warning("PFC server returned no working directory, using fallback")
            except Exception as e:
                logger.warning(f"Failed to connect to PFC server for workspace sync: {e}")

        except Exception as e:
            logger.warning(f"Failed to query PFC working directory: {e}")

        # Fallback to local pfc_workspace
        try:
            from .config import BASE_DIR
            pfc_workspace = BASE_DIR.parent / "pfc_workspace"
            pfc_workspace.mkdir(parents=True, exist_ok=True)
            logger.info(f"✓ Using fallback PFC workspace: {pfc_workspace}")
            return str(pfc_workspace)
        except Exception as e:
            logger.warning(f"Failed to determine fallback PFC workspace: {e}")
            fallback = Path.cwd() / "pfc_workspace"
            fallback.mkdir(parents=True, exist_ok=True)
            return str(fallback)

    # Non-PFC profiles: use aiNagisa/workspace
    try:
        from .config import BASE_DIR
        workspace = BASE_DIR.parent / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        return str(workspace)
    except Exception as e:
        logger.warning(f"Failed to determine workspace, using fallback: {e}")
        # Fallback to project root workspace
        fallback = Path.cwd() / "workspace"
        fallback.mkdir(parents=True, exist_ok=True)
        return str(fallback)


def _build_env_info(session_id: Optional[str] = None) -> str:
    """
    Build environment information string similar to Claude Code.

    Args:
        session_id: Optional session ID for task isolation context

    Returns:
        Formatted environment information block
    """
    try:
        from backend.infrastructure.mcp.tools.coding.utils.path_security import WORKSPACE_ROOT
        working_dir = str(WORKSPACE_ROOT)
    except ImportError:
        working_dir = str(Path.cwd())

    # Normalize path to forward slashes for cross-platform consistency
    # This ensures LLM always sees paths in the same format regardless of OS
    working_dir = normalize_path_separators(working_dir, target_platform='linux')

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
    enable_memory: bool = True,
    tool_schemas: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Build complete system prompt following Anthropic best practices.

    This is the main entry point for creating system prompts with support for:
    - Base identity and instructions (profile-specific)
    - Tool schemas embedding (Anthropic function calling format)
    - Automatic memory context injection from conversation history
    - Expression/Live2D instructions

    Args:
        agent_profile: Agent profile type ("general", "pfc", "coding", "lifestyle", "disabled")
        session_id: Session ID for memory retrieval
        user_id: User ID for memory operations
        enable_memory: Whether to enable memory injection (controlled by frontend)
        tool_schemas: Pre-fetched tool schemas from LLM provider's tool manager

    Returns:
        Complete system prompt string following Anthropic format with memory context
    """
    components = []

    # 1. Get base prompt (contains {tool_schemas} and {workspace_root} placeholders)
    base = get_base_prompt(profile=agent_profile)
    if not base:
        logger.warning(f"No base prompt found for profile: {agent_profile}")
        base = ""

    # 2. Build tool schemas section (Anthropic function calling format)
    tool_schemas_section = ""
    if agent_profile != "disabled" and tool_schemas:
        sections = [
            "In this environment you have access to a set of tools you can use to answer the user's question.",
            "String and scalar parameters should be specified as is, while lists and objects should use JSON format.",
            "Here are the functions available in JSONSchema format:",
            "<functions>"
        ]

        for tool_schema in tool_schemas:
            tool_json = json.dumps(tool_schema, separators=(',', ':'))
            sections.append(f'<function>{tool_json}</function>')

        sections.append("</functions>")
        tool_schemas_section = "\n".join(sections)

    # 3. Get workspace root for path substitution (dynamic based on profile and session)
    workspace_root = _get_workspace_root(agent_profile, session_id)

    # Normalize workspace_root to forward slashes for LLM consistency
    # This ensures LLM always sees paths in the same format (like Claude Code)
    workspace_root = normalize_path_separators(workspace_root, target_platform='linux')

    # 4. Build environment information with session context
    env_info = _build_env_info(session_id=session_id)

    # 5. Replace placeholders in base prompt
    base = base.replace("{tool_schemas}", tool_schemas_section)
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

    # 6. Expression/Live2D instructions
    expression = get_expression_prompt()
    if expression:
        components.append(expression)

    # Join all components with separators
    return "\n\n---\n\n".join(filter(None, components))




