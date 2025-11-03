"""
Unified workspace resolution for aiNagisa.

This module provides a single source of truth for determining workspace directories
based on agent profiles. Both system prompt construction and tool execution use
the same logic to ensure consistency.
"""

import asyncio
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
            pfc_workspace = BASE_DIR.parent / "pfc_workspace"
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
        workspace = BASE_DIR.parent / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace
    except Exception as e:
        logger.warning(f"Failed to determine workspace, using fallback: {e}")
        # Fallback to project root workspace
        fallback = Path.cwd() / "workspace"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


async def get_workspace_for_session(session_id: str) -> Path:
    """
    Get workspace directory for a specific session.

    Retrieves the agent profile from the session's context manager,
    then returns the appropriate workspace directory.

    Args:
        session_id: Session identifier

    Returns:
        Path object for the workspace directory
    """
    try:
        # Get agent profile from session's context manager
        from backend.shared.utils.app_context import get_llm_client
        llm_client = get_llm_client()
        context_manager = llm_client.get_or_create_context_manager(session_id)
        agent_profile = getattr(context_manager, 'agent_profile', 'general')

        return await get_workspace_for_profile(agent_profile, session_id)

    except Exception as e:
        logger.warning(f"Failed to get workspace for session {session_id}: {e}")
        # Fallback to general workspace
        return await get_workspace_for_profile('general', session_id)


def get_workspace_for_session_sync(session_id: str) -> Path:
    """
    Get workspace directory for a specific session (synchronous version).

    This is a synchronous wrapper for tools that cannot use async/await.
    It runs the async function in the current event loop or creates a new one.

    Args:
        session_id: Session identifier

    Returns:
        Path object for the workspace directory
    """
    try:
        # Try to get the current running event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're already in an async context - use asyncio.create_task approach
            # Create a new event loop in a thread-safe way
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, get_workspace_for_session(session_id))
                return future.result(timeout=10)
        else:
            # Safe to run coroutine
            return loop.run_until_complete(get_workspace_for_session(session_id))
    except RuntimeError:
        # No event loop in current thread, create a new one
        return asyncio.run(get_workspace_for_session(session_id))
    except Exception as e:
        logger.error(f"Failed to get workspace for session {session_id}: {e}")
        # Fallback to general workspace
        from backend.shared.utils.prompt.config import BASE_DIR
        workspace = BASE_DIR.parent / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace
