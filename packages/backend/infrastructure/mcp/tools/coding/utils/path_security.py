"""Path security utilities for filesystem tools.

This module provides comprehensive path security functions and workspace management
to ensure all filesystem operations stay within the workspace boundaries.
It includes workspace root configuration, path validation, and symlink safety checks.
"""

from pathlib import Path
from typing import Union, Optional
from .config import get_tools_config

__all__ = [
    "WORKSPACE_ROOT",
    "get_workspace_root",
    "get_workspace_root_async",
    "validate_path_in_workspace",
    "is_safe_symlink",
    "check_parent_symlinks"
]

# ---------------------------------------------------------------------------
# Workspace root (dynamic, context-aware)
# ---------------------------------------------------------------------------

async def get_workspace_root_async(context=None) -> Path:
    """
    Get workspace root directory dynamically (async version).

    Uses unified workspace resolution based on agent profile from context_manager.

    Args:
        context: Optional FastMCP Context object

    Returns:
        Path object for the workspace root directory
    """
    try:
        # Architecture guarantee: tool_manager.py always injects _meta.client_id
        session_id = context.client_id if context else None
        if session_id:
            # Get agent profile from session's context manager
            # (set by chat_service before tool execution)
            from backend.shared.utils.app_context import get_llm_client
            from backend.shared.utils.workspace import get_workspace_for_profile

            llm_client = get_llm_client()
            context_manager = llm_client.get_or_create_context_manager(session_id)
            agent_profile = getattr(context_manager, 'agent_profile', 'general')

            # Use unified workspace resolution for all profiles
            workspace_path = await get_workspace_for_profile(agent_profile, session_id)
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


# ---------------------------------------------------------------------------
# Symlink security functions
# ---------------------------------------------------------------------------

def is_safe_symlink(path: Path, workspace_root: Optional[Path] = None) -> bool:
    """Check if a symlink is safe (points within workspace).

    Args:
        path: Path object to check
        workspace_root: Optional workspace root to validate against.
                       If None, uses static workspace root from config.

    Returns:
        True if the path is not a symlink or if it's a safe symlink.
        False if it's a symlink pointing outside workspace.

    Examples:
        >>> from pathlib import Path
        >>> safe_link = Path("workspace/safe_link.txt")  # points to workspace/file.txt
        >>> is_safe_symlink(safe_link)
        True

        >>> unsafe_link = Path("workspace/unsafe_link.txt")  # points to /etc/passwd
        >>> is_safe_symlink(unsafe_link)
        False
    """
    if not path.is_symlink():
        return True

    # Use provided workspace root or fallback to static config
    if workspace_root is None:
        workspace_root = get_workspace_root()

    try:
        # Resolve the symlink and check if it's within workspace
        real_path = path.resolve()
        workspace_real = workspace_root.resolve()

        # Check if the resolved path is within workspace
        try:
            real_path.relative_to(workspace_real)
            return True
        except ValueError:
            # Path is outside workspace
            return False
    except (OSError, RuntimeError):
        # Failed to resolve - consider unsafe
        return False


def check_parent_symlinks(path: Path, workspace_root: Optional[Path] = None) -> bool:
    """Check if any parent directory is an unsafe symlink.

    This function walks up the directory tree from the given path to the
    workspace root, checking each parent directory to ensure none of them
    are symlinks pointing outside the workspace.

    Args:
        path: Path object to check
        workspace_root: Optional workspace root to validate against.
                       If None, uses static workspace root from config.

    Returns:
        True if all parent directories are safe (not symlinks or safe symlinks).
        False if any parent directory is an unsafe symlink.

    Examples:
        >>> from pathlib import Path
        >>> safe_path = Path("workspace/safe_dir/file.txt")
        >>> check_parent_symlinks(safe_path)
        True

        >>> unsafe_path = Path("workspace/unsafe_dir/file.txt")  # unsafe_dir -> /etc
        >>> check_parent_symlinks(unsafe_path)
        False
    """
    # Use provided workspace root or fallback to static config
    if workspace_root is None:
        workspace_root = get_workspace_root()

    current = path.parent
    workspace_real = workspace_root.resolve()

    while current != workspace_real and current != current.parent:
        if current.is_symlink() and not is_safe_symlink(current, workspace_root):
            return False
        current = current.parent

    return True 