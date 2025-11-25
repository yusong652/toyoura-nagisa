"""
Unified workspace resolution for aiNagisa.

This module provides a single source of truth for determining workspace directories
based on agent profiles. Both system prompt construction and tool execution use
the same logic to ensure consistency.

Design principle: agent_profile is always passed explicitly as a parameter,
never retrieved implicitly from context_manager state.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


async def get_workspace_for_profile(agent_profile: str, session_id: Optional[str] = None) -> Path:
    """
    Determine workspace directory based on agent profile.

    This is the SINGLE SOURCE OF TRUTH for workspace resolution.
    All components (system prompts, coding tools, etc.) must use this function.

    Workspace Strategy:
        - PFC profile with PFC server connected: PFC server's actual working directory
          → Ensures agent can access files saved by PFC (e.g., checkpoints, data)
        - PFC profile without PFC server: Fallback to local pfc_workspace
          → aiNagisa/pfc_workspace (standalone mode)
        - Other profiles (coding, general, lifestyle, etc.): Unified workspace
          → aiNagisa/workspace

    Args:
        agent_profile: Agent profile type ("pfc", "coding", "general", etc.)
        session_id: Optional session ID (reserved for future use, currently unused)

    Returns:
        Path object for the workspace directory

    Note:
        For PFC profile, session_id is currently not used for workspace isolation
        because PFC server's working directory is determined by the PFC project itself.
    """
    # PFC-specific workspace logic
    if agent_profile == "pfc":
        # Try to get PFC server's actual working directory
        try:
            from backend.infrastructure.pfc.websocket_client import get_client

            try:
                # Query PFC server's working directory
                client = await get_client()
                pfc_working_dir = await client.get_working_directory()

                if pfc_working_dir:
                    workspace = Path(pfc_working_dir)
                    logger.info(f"✓ Using PFC server's working directory: {workspace}")
                    return workspace
                else:
                    logger.warning("PFC server returned no working directory, using fallback")
            except Exception as e:
                logger.warning(f"Failed to connect to PFC server for workspace sync: {e}")

        except Exception as e:
            logger.warning(f"Failed to query PFC working directory: {e}")

        # Fallback to local pfc_workspace
        try:
            from backend.shared.utils.prompt.config import BASE_DIR
            pfc_workspace = BASE_DIR / "pfc_workspace"
            pfc_workspace.mkdir(parents=True, exist_ok=True)
            logger.info(f"✓ Using fallback PFC workspace: {pfc_workspace}")
            return pfc_workspace
        except Exception as e:
            logger.warning(f"Failed to determine fallback PFC workspace: {e}")
            fallback = Path.cwd() / "pfc_workspace"
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback

    # Non-PFC profiles: use aiNagisa/workspace
    try:
        from backend.shared.utils.prompt.config import BASE_DIR
        workspace = BASE_DIR / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace
    except Exception as e:
        logger.warning(f"Failed to determine workspace, using fallback: {e}")
        # Fallback to project root workspace
        fallback = Path.cwd() / "workspace"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
