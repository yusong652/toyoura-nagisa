"""Workspace path utilities for filesystem tools.

This module resolves workspace roots and validates that filesystem operations
stay within the workspace boundary.
"""

from pathlib import Path
from typing import Union, Optional
from .config import get_tools_config

__all__ = [
    "WORKSPACE_ROOT",
    "get_workspace_root",
    "get_workspace_root_async",
    "validate_path_in_workspace",
]

# ---------------------------------------------------------------------------
# Workspace root (dynamic, context-aware)
# ---------------------------------------------------------------------------

async def get_workspace_root_async(context=None) -> Path:
    """
    Get workspace root directory dynamically (async version).

    Uses unified workspace resolution based on agent profile from context_manager.

    Args:
        context: Optional ToolContext object

    Returns:
        Path object for the workspace root directory
    """
    try:
        # Architecture guarantee: tool_manager.py always injects _meta.client_id
        session_id = context.session_id if context else None
        if session_id:
            from backend.shared.utils.workspace import resolve_workspace_root
            workspace_path = await resolve_workspace_root(session_id)
            return Path(workspace_path)

    except Exception as e:
        import logging
        logging.getLogger(__name__).debug(f"Failed to get dynamic workspace: {e}")

    # Fallback to static config
    workspace = get_tools_config().root_dir
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def get_workspace_root() -> Path:
    """
    Get workspace root directory (synchronous fallback).

    This is a synchronous fallback that returns the static workspace root.
    New code should use get_workspace_root_async() instead for dynamic behavior.

    Returns:
        Path object for the static workspace root directory
    """
    workspace = get_tools_config().root_dir
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


# For backward compatibility, export WORKSPACE_ROOT
# NOTE: This is a static value evaluated at import time
# Dynamic workspace resolution requires using get_workspace_root_async()
WORKSPACE_ROOT = get_tools_config().root_dir
WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Core path validation
# ---------------------------------------------------------------------------

def validate_path_in_workspace(path: Union[str, Path], workspace_root: Optional[Path] = None) -> str | None:
    """Return absolute path *str* if *path* is located inside workspace root.

    This is the primary security function that ensures all file operations
    stay within the designated workspace directory.

    Args:
        path: Path to validate (str or Path object)
        workspace_root: Optional workspace root to validate against.
                       If None, uses static workspace root from config.

    Returns:
        Absolute path as string if valid, None if outside workspace

    Security Rules:
        1. Relative paths are resolved **against** workspace root
        2. Absolute paths must point inside the workspace
        3. Returns *None* when the path escapes the workspace boundary

    Examples:
        >>> validate_path_in_workspace("file.txt")
        "/workspace/file.txt"

        >>> validate_path_in_workspace("/etc/passwd")
        None  # Outside workspace

        >>> validate_path_in_workspace("../../../etc/passwd")
        None  # Path traversal attempt blocked
    """
    # Use provided workspace root or fallback to static config
    if workspace_root is None:
        workspace_root = get_workspace_root()

    p = Path(str(path)).expanduser()

    if not p.is_absolute():
        # Relative paths are resolved against workspace root
        p = (workspace_root / p).resolve()
    else:
        # Absolute paths are used as-is (after resolving)
        p = p.resolve()

    try:
        # Check if the resolved path is within workspace
        p.relative_to(workspace_root.resolve())
    except ValueError:
        return None
    return str(p)
