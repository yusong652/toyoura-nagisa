"""Path security utilities for filesystem tools.

This module provides comprehensive path security functions and workspace management
to ensure all filesystem operations stay within the workspace boundaries.
It includes workspace root configuration, path validation, and symlink safety checks.
"""

from pathlib import Path
from typing import Union
from .config import get_tools_config

__all__ = [
    "WORKSPACE_ROOT", 
    "validate_path_in_workspace", 
    "is_safe_symlink", 
    "check_parent_symlinks"
]

# ---------------------------------------------------------------------------
# Workspace root (static, no state)
# ---------------------------------------------------------------------------

# Workspace root from global config (created if missing)
WORKSPACE_ROOT = get_tools_config().root_dir
WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Core path validation
# ---------------------------------------------------------------------------

def validate_path_in_workspace(path: Union[str, Path]) -> str | None:
    """Return absolute path *str* if *path* is located inside ``WORKSPACE_ROOT``.

    This is the primary security function that ensures all file operations
    stay within the designated workspace directory.

    Args:
        path: Path to validate (str or Path object)
        
    Returns:
        Absolute path as string if valid, None if outside workspace
        
    Security Rules:
        1. Relative paths are resolved **against** ``WORKSPACE_ROOT``
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
    p = Path(str(path)).expanduser()

    if not p.is_absolute():
        # Relative paths are resolved against WORKSPACE_ROOT
        p = (WORKSPACE_ROOT / p).resolve()
    else:
        # Absolute paths are used as-is (after resolving)
        p = p.resolve()

    try:
        # Check if the resolved path is within workspace
        p.relative_to(WORKSPACE_ROOT.resolve())
    except ValueError:
        return None
    return str(p)


# ---------------------------------------------------------------------------
# Symlink security functions
# ---------------------------------------------------------------------------

def is_safe_symlink(path: Path) -> bool:
    """Check if a symlink is safe (points within workspace).
    
    Args:
        path: Path object to check
        
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
    
    try:
        # Resolve the symlink and check if it's within workspace
        real_path = path.resolve()
        workspace_real = WORKSPACE_ROOT.resolve()
        
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


def check_parent_symlinks(path: Path) -> bool:
    """Check if any parent directory is an unsafe symlink.
    
    This function walks up the directory tree from the given path to the
    workspace root, checking each parent directory to ensure none of them
    are symlinks pointing outside the workspace.
    
    Args:
        path: Path object to check
        
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
    current = path.parent
    workspace_real = WORKSPACE_ROOT.resolve()
    
    while current != workspace_real and current != current.parent:
        if current.is_symlink() and not is_safe_symlink(current):
            return False
        current = current.parent
    
    return True 