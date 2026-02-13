"""
Unified workspace resolution for toyoura-nagisa.

This module provides a single source of truth for determining workspace directories.
Both system prompt construction and tool execution use the same logic to ensure
consistency.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _resolve_workspace_from_session(session_id: str) -> Optional[Path]:
    """Resolve workspace root from session metadata."""
    try:
        from backend.infrastructure.storage.session_manager import get_session_metadata

        metadata = get_session_metadata(session_id)
        if not metadata:
            return None

        workspace_root = metadata.get("workspace_root")
        if not isinstance(workspace_root, str) or not workspace_root.strip():
            return None

        candidate = Path(workspace_root).expanduser().resolve()
        if candidate.exists() and candidate.is_dir():
            return candidate

        logger.warning(
            f"Session workspace_root is invalid for session {session_id}: {workspace_root}"
        )
        return None
    except Exception as e:
        logger.debug(f"Failed to resolve workspace from session metadata: {e}")
        return None


async def resolve_workspace_root(session_id: Optional[str] = None) -> Path:
    """
    Determine workspace directory.

    This is the SINGLE SOURCE OF TRUTH for workspace resolution.
    All components (system prompts, coding tools, etc.) must use this function.

    Workspace Strategy:
        - Session metadata workspace_root (create-session time)
        - Configured PFC workspace (PFC_WORKSPACE in config/pfc.py)
        - Local pfc_workspace fallback (toyoura-nagisa/pfc_workspace)

    Args:
        session_id: Optional session ID (reserved for future use).

    Returns:
        Path object for the workspace directory

    Note:
        Workspace resolution no longer caches by agent profile.
    """
    if session_id:
        session_workspace = _resolve_workspace_from_session(session_id)
        if session_workspace:
            return session_workspace

    # Primary: Use configured PFC workspace if available
    try:
        from backend.config.pfc import get_pfc_workspace

        configured_workspace = get_pfc_workspace()
        if configured_workspace:
            logger.debug(f"Using configured PFC workspace: {configured_workspace}")
            return configured_workspace
    except ImportError:
        logger.debug("PFC config not available, skipping configured workspace check")
    except Exception as e:
        logger.warning(f"Failed to get configured PFC workspace: {e}")

    # Fallback: Local pfc_workspace (development/testing)
    try:
        from backend.shared.utils.prompt.config import BASE_DIR

        pfc_workspace = BASE_DIR / "pfc_workspace"
        pfc_workspace.mkdir(parents=True, exist_ok=True)
        return pfc_workspace
    except Exception as e:
        logger.warning(f"Failed to determine fallback PFC workspace: {e}")
        fallback = Path.cwd() / "pfc_workspace"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
