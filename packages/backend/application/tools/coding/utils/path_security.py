"""Workspace path utilities for filesystem tools.

This module resolves the current workspace root and converts tool paths into
absolute filesystem paths. Relative paths are anchored to the workspace root;
absolute paths are used as-is.
"""

from pathlib import Path
from typing import Union, Optional
from .config import get_tools_config

__all__ = [
    "WORKSPACE_ROOT",
    "get_workspace_root",
    "get_workspace_root_async",
    "resolve_tool_path",
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
# Core path resolution
# ---------------------------------------------------------------------------

def resolve_tool_path(path: Union[str, Path], workspace_root: Optional[Path] = None) -> Path:
    """Resolve a tool path to an absolute filesystem path.

    Args:
        path: Path to resolve (str or Path object)
        workspace_root: Optional workspace root used for relative paths.
            If None, uses the static workspace root from config.

    Returns:
        Resolved absolute ``Path``.

    Examples:
        >>> resolve_tool_path("file.txt")
        PosixPath('/workspace/file.txt')

        >>> resolve_tool_path("/etc/passwd")
        PosixPath('/etc/passwd')

        >>> resolve_tool_path("../../../etc/passwd")
        PosixPath('/etc/passwd')
    """
    if workspace_root is None:
        workspace_root = get_workspace_root()

    p = Path(str(path)).expanduser()

    if not p.is_absolute():
        p = (workspace_root / p).resolve()
    else:
        p = p.resolve()

    return p
