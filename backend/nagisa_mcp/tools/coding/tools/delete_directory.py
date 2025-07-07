"""delete_directory tool - safe directory deletion with trash recovery."""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
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

__all__ = ["delete_directory", "register_delete_directory_tool"]

# Constants
TRASH_FOLDER_NAME = ".trash"


def _ensure_trash_folder() -> Path:
    """Ensure .trash folder exists in workspace root and return its path."""
    trash_path = WORKSPACE_ROOT / TRASH_FOLDER_NAME
    trash_path.mkdir(exist_ok=True)
    return trash_path


def _generate_trash_dirname(original_path: Path) -> str:
    """Generate a unique directory name for the trash folder."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # microseconds to milliseconds
    dir_name = original_path.name
    return f"{dir_name}_{timestamp}"


def _count_directory_contents(directory: Path, deep_count: bool = False) -> Dict[str, Any]:
    """Count files and subdirectories in a directory.
    
    Args:
        directory: Directory to analyze
        deep_count: If True, recursively count all items. If False, only count immediate children.
        
    Returns:
        Dictionary with count information and metadata
    """
    if deep_count:
        # Recursive counting (potentially slow for large directories)
        total_files = 0
        total_dirs = 0
        
        for item in directory.rglob("*"):
            try:
                if item.is_file():
                    total_files += 1
                elif item.is_dir():
                    total_dirs += 1
            except (OSError, PermissionError):
                # Skip items we can't access
                continue
        
        return {
            "files": total_files,
            "directories": total_dirs,
            "count_type": "recursive",
            "potentially_large": total_files > 1000 or total_dirs > 100
        }
    else:
        # Fast counting (only immediate children)
        immediate_files = 0
        immediate_dirs = 0
        
        try:
            for item in directory.iterdir():
                try:
                    if item.is_file():
                        immediate_files += 1
                    elif item.is_dir():
                        immediate_dirs += 1
                except (OSError, PermissionError):
                    # Skip items we can't access
                    continue
        except (OSError, PermissionError):
            # Can't read directory contents
            return {
                "files": 0,
                "directories": 0,
                "count_type": "immediate",
                "error": "Permission denied reading directory contents"
            }
        
        # Heuristic to detect potentially large directories
        potentially_large = immediate_files > 100 or immediate_dirs > 50
        
        result = {
            "files": immediate_files,
            "directories": immediate_dirs,
            "count_type": "immediate",
            "potentially_large": potentially_large
        }
        
        # Add hint for LLM if directory seems large
        if potentially_large:
            result["hint"] = "Directory has many immediate children - use deep_count=True for recursive statistics"
        
        return result


def delete_directory(
    path: str = Field(..., description="Directory path to delete (workspace-relative)"),
    recursive: bool = Field(False, description="If True, delete non-empty directories. If False (default), only delete empty directories."),
    permanent: bool = Field(False, description="If True, permanently delete directory. If False (default), move to .trash folder for recovery."),
    deep_count: bool = Field(False, description="If True, recursively count all files/directories. If False (default), only count immediate children for better performance.")
) -> Dict[str, Any]:
    """Safely deletes a directory, either by moving it to a .trash folder or permanently.

    ## Core Functionality
    - **Default Behavior (Safe):** By default, this tool only deletes **empty** directories.
    - **Recursive Deletion:** To delete a directory that is **not empty**, you MUST set `recursive=True`.
    - **Trash vs. Permanent:**
        - By default (`permanent=False`), the directory is moved to a `.trash` folder for recovery.
        - To **permanently delete** the directory and all its contents (irreversible), you MUST set `permanent=True`.

    ## Strategic Usage
    - This is a highly destructive operation, especially with `recursive=True`. Be absolutely certain before using it.
    - This tool is for **directories only**. To delete a single file, you must use the `delete_file` tool.
    - Before deleting a non-empty directory, consider using `list_directory` to understand its contents.

    ## Return Value (What you will receive)
    The output you get back from this tool will be one of the following two things:

    1.  **Success:** A single `string` confirming the deletion and summarizing its contents.
        - Example (to trash): `"Moved directory to trash: old_project/ → .trash/old_project_20250708_103000_123/ (files: 15, subdirs: 3)"`
        - Example (permanent): `"Permanently deleted directory: temp_files/ (files: 5, subdirs: 0)"`
    2.  **Error:** A single `string` starting with "Error:", explaining what went wrong.
        - Example: `"Error: Directory is not empty - use recursive=True to delete non-empty directories"`

    You MUST check the response to confirm success or handle the error.
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
    if isinstance(recursive, FieldInfo):
        recursive = False
    if isinstance(permanent, FieldInfo):
        permanent = False
    if isinstance(deep_count, FieldInfo):
        deep_count = False

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
        d = Path(abs_path)
        
        # Check if directory exists
        if not d.exists():
            return _error(f"Directory does not exist: {path}")
        
        # Enhanced file check with clear guidance
        if d.is_file():
            return _error("Path is a file - use delete_file tool instead")
        
        # Check if target is actually a directory
        if not d.is_dir():
            return _error(f"Path is not a directory: {path}")
        
        # Comprehensive symlink safety checks
        if d.is_symlink() and not is_safe_symlink(d):
            return _error("Cannot delete symlink pointing outside workspace")
        
        # Check parent directory safety
        if not check_parent_symlinks(d):
            return _error("Cannot delete directory with parent symlink pointing outside workspace")
        
        # Check if directory is empty (unless recursive is True)
        try:
            dir_contents = list(d.iterdir())
            is_empty = len(dir_contents) == 0
            
            if not is_empty and not recursive:
                return _error("Directory is not empty - use recursive=True to delete non-empty directories")
        except PermissionError:
            return _error("Permission denied when checking directory contents")
        
        # Record directory information before deletion
        was_symlink = d.is_symlink()
        contents_info = _count_directory_contents(d, deep_count) if not is_empty else {
            "files": 0, 
            "directories": 0, 
            "count_type": "immediate", 
            "potentially_large": False
        }
        
        # Prepare response data
        rel_display = d.relative_to(WORKSPACE_ROOT) if str(d).startswith(str(WORKSPACE_ROOT)) else Path(path)
        
        if permanent:
            # Permanent deletion
            if is_empty:
                d.rmdir()
            else:
                shutil.rmtree(str(d))
            
            # Build content info for LLM
            count_desc = f"files: {contents_info['files']}, subdirs: {contents_info['directories']} ({contents_info['count_type']} count)"
            hint_text = f" - {contents_info['hint']}" if contents_info.get('hint') else ""
            llm_content = f"Permanently deleted directory: {rel_display}/ ({count_desc}){hint_text}"
            
            return _success(
                "Directory permanently deleted",
                llm_content,
                original_path=str(d),
                relative_path=str(rel_display),
                was_symlink=was_symlink,
                permanent=True,
                recoverable=False,
                contents=contents_info,
            )
        else:
            # Move to trash (default behavior)
            trash_folder = _ensure_trash_folder()
            trash_dirname = _generate_trash_dirname(d)
            trash_path = trash_folder / trash_dirname
            
            # Move directory to trash
            shutil.move(str(d), str(trash_path))
            
            # Build content info for LLM
            count_desc = f"files: {contents_info['files']}, subdirs: {contents_info['directories']} ({contents_info['count_type']} count)"
            hint_text = f" - {contents_info['hint']}" if contents_info.get('hint') else ""
            llm_content = f"Moved directory to trash: {rel_display}/ → .trash/{trash_dirname}/ ({count_desc}){hint_text}"
            
            return _success(
                "Directory moved to trash successfully",
                llm_content,
                original_path=str(d),
                relative_path=str(rel_display),
                was_symlink=was_symlink,
                permanent=False,
                trash_path=str(trash_path),
                recoverable=True,
                contents=contents_info,
            )

    except PermissionError:
        return _error("Permission denied when deleting directory")
    except OSError as exc:
        # Handle specific errors
        if "Directory not empty" in str(exc):
            return _error("Directory is not empty - use recursive=True to delete non-empty directories")
        else:
            return _error(f"IO error: {exc}")
    except Exception as exc:  # pylint: disable=broad-except
        return _error(f"Unexpected error: {exc}")


# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_delete_directory_tool(mcp: FastMCP):
    common = dict(tags={"filesystem", "coding"}, annotations={"category": "coding"})
    mcp.tool(**common)(delete_directory) 