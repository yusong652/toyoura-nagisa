"""delete_file tool (split from coding.fs_tools)."""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from pydantic import Field
from pydantic.fields import FieldInfo
from fastmcp import FastMCP  # type: ignore

from ..utils.tool_result import ToolResult
from ..utils.path_security import (
    WORKSPACE_ROOT, 
    validate_path_in_workspace, 
    is_safe_symlink, 
    check_parent_symlinks
)

__all__ = ["delete_file", "register_delete_file_tool"]

# Constants
TRASH_FOLDER_NAME = ".trash"


def _ensure_trash_folder() -> Path:
    """Ensure .trash folder exists in workspace root and return its path."""
    trash_path = WORKSPACE_ROOT / TRASH_FOLDER_NAME
    trash_path.mkdir(exist_ok=True)
    return trash_path


def _generate_trash_filename(original_path: Path) -> str:
    """Generate a unique filename for the trash folder."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # microseconds to milliseconds
    stem = original_path.stem
    suffix = original_path.suffix
    return f"{stem}_{timestamp}{suffix}"


def delete_file(
    path: str = Field(..., description="File path to delete (workspace-relative)"),
    permanent: bool = Field(False, description="If True, permanently delete file. If False (default), move to .trash folder for recovery.")
) -> Dict[str, Any]:
    """delete_file – Safely delete a file within the workspace (REVERSIBLE by default).

    This tool safely removes files from the workspace directory with comprehensive
    security checks, including symlink safety validation. The default behavior moves 
    files to a .trash folder for recovery, making all deletions reversible unless 
    explicitly requested otherwise. All operations are restricted to the workspace 
    directory with multi-layer protection against malicious symlinks.

    Successful response (``ToolResult.model_dump()``) – **keys of interest**::

        {
        "status": "success",
        "message": "File moved to trash successfully",       # short summary
        "llm_content": "Moved file to trash: foo/bar.py",   # detailed summary for LLM
        "data": {
            "original_path": "/abs/workspace/foo/bar.py",    # original absolute path
            "relative_path": "foo/bar.py",                   # workspace-relative path
            "was_symlink": false,                            # whether deleted item was a symlink
            "permanent": false,                              # whether permanently deleted
            "trash_path": "/abs/workspace/.trash/bar_20231201_143022_123.py",  # trash location (if not permanent)
            "recoverable": true                              # whether file can be recovered
        }
        }

    Error response::

        {
        "status": "error",
        "message": "Path is a directory - use delete_directory tool instead",
        "error": "Path is a directory - use delete_directory tool instead"
        }

    Security Features:
    - Symlink safety: Prevents deleting symlinks pointing outside workspace
    - Parent directory safety: Checks all parent directories for unsafe symlinks
    - Path validation: Ensures all operations stay within workspace boundaries
    - Type checking: Verifies target is actually a file (not directory)
    - Safe resolution: Handles broken symlinks and permission issues gracefully

    Reliability Features:
    - Recoverable deletion: Files moved to .trash folder by default
    - Permanent deletion option: Available when explicitly requested
    - Clear guidance: Directs LLM to appropriate tools for different file types

    The **``llm_content``** field provides detailed information for the assistant's
    conversation history, while **``message``** is a concise user-facing summary.
    """

    # ------------------------------------------------------------------
    # Parameter validation (manual to stay lightweight)
    # ------------------------------------------------------------------
    
    # Handle Pydantic FieldInfo objects when invoked programmatically
    if isinstance(path, FieldInfo):
        return ToolResult(
            status="error", 
            message="Invalid path parameter", 
            error="Invalid path parameter"
        ).model_dump()
    if isinstance(permanent, FieldInfo):
        permanent = False

    # Helper shortcuts for consistent results
    def _error(message: str) -> Dict[str, Any]:
        return ToolResult(status="error", message=message, error=message).model_dump()

    def _success(message: str, llm_content: str, **data: Any) -> Dict[str, Any]:
        payload = data or None
        return ToolResult(
            status="success",
            message=message,
            llm_content=llm_content,
            data=payload,
        ).model_dump()

    # Validate path security
    abs_path = validate_path_in_workspace(path)
    if abs_path is None:
        return _error(f"Path is outside of workspace: {path}")

    try:
        f = Path(abs_path)
        
        # Check if file exists
        if not f.exists():
            return _error(f"File does not exist: {path}")
        
        # Enhanced directory check with clear guidance
        if f.is_dir():
            return _error("Path is a directory - use delete_directory tool instead")
        
        # Check if target is actually a file
        if not f.is_file():
            return _error(f"Path is not a regular file: {path}")
        
        # Comprehensive symlink safety checks
        if f.is_symlink() and not is_safe_symlink(f):
            return _error("Cannot delete symlink pointing outside workspace")
        
        # Check parent directory safety (NEW - addresses security concern)
        if not check_parent_symlinks(f):
            return _error("Cannot delete file with parent symlink pointing outside workspace")
        
        # Record file information before deletion
        was_symlink = f.is_symlink()
        original_size = f.stat().st_size
        
        # Prepare response data
        rel_display = f.relative_to(WORKSPACE_ROOT) if str(f).startswith(str(WORKSPACE_ROOT)) else Path(path)
        
        if permanent:
            # Permanent deletion
            f.unlink()
            
            llm_content = f"Permanently deleted file: {rel_display} ({original_size} bytes)"
            
            return _success(
                "File permanently deleted",
                llm_content,
                original_path=str(f),
                relative_path=str(rel_display),
                was_symlink=was_symlink,
                permanent=True,
                recoverable=False,
            )
        else:
            # Move to trash (default behavior)
            trash_folder = _ensure_trash_folder()
            trash_filename = _generate_trash_filename(f)
            trash_path = trash_folder / trash_filename
            
            # Move file to trash
            shutil.move(str(f), str(trash_path))
            
            llm_content = f"Moved file to trash: {rel_display} → .trash/{trash_filename} ({original_size} bytes)"
            
            return _success(
                "File moved to trash successfully",
                llm_content,
                original_path=str(f),
                relative_path=str(rel_display),
                was_symlink=was_symlink,
                permanent=False,
                trash_path=str(trash_path),
                recoverable=True,
            )

    except PermissionError:
        return _error("Permission denied when deleting file")
    except IsADirectoryError:
        # Additional safety check
        return _error("Path is a directory - use delete_directory tool instead")
    except FileNotFoundError:
        # Handle race condition where file was deleted between checks
        return _error(f"File no longer exists: {path}")
    except OSError as exc:
        return _error(f"IO error: {exc}")
    except Exception as exc:  # pylint: disable=broad-except
        return _error(f"Unexpected error: {exc}")


# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_delete_file_tool(mcp: FastMCP):
    common = dict(tags={"filesystem", "coding"}, annotations={"category": "coding"})
    mcp.tool(**common)(delete_file) 