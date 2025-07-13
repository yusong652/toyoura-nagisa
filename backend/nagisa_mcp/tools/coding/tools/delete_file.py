"""delete_file tool - safe file deletion with trash recovery.

This tool provides atomic file deletion functionality, focusing exclusively on 
removing files with comprehensive safety checks and recovery options. It supports
both permanent deletion and safe trash-based recovery.

Modeled after gemini-cli's file management tools for consistency and interoperability.
"""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import Field
from pydantic.fields import FieldInfo
from fastmcp import FastMCP  # type: ignore

from backend.nagisa_mcp.utils.tool_result import ToolResult
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
    """Safely deletes a file, either by moving it to a .trash folder or permanently.

    ## Core Functionality
    - **Default Behavior (Safe):** By default (`permanent=False`), this tool moves the specified file to a `.trash` directory within the workspace, allowing for recovery.
    - **Permanent Deletion:** To permanently delete the file (irreversible), you must explicitly set `permanent=True`.

    ## Strategic Usage
    - This is a destructive operation. Be certain you want to delete the file before using this tool.
    - This tool is for **files only**. To delete a directory, you must use the `delete_directory` tool.
    - For most cases, prefer the default behavior (moving to trash) as a safety measure.

    ## Return Value
    Returns a JSON object with the following structure:
    
    ```json
    {
      "operation": {
        "type": "delete_file",
        "path": "target_file.py",
        "permanent": false,
        "recoverable": true,
        "was_symlink": false
      },
      "file_info": {
        "size_bytes": 1024,
        "file_type": "text",
        "extension": ".py"
      },
      "trash_info": {
        "trash_path": ".trash/target_file_20250708_103000_123.py",
        "original_path": "target_file.py",
        "timestamp": "2025-07-08T10:30:00.123"
      },
      "summary": {
        "operation_type": "move_to_trash",
        "success": true
      }
    }
    ```

    The `operation` object contains details about the deletion operation.
    The `file_info` object provides information about the deleted file.
    The `trash_info` object is only present when `permanent=false`.
    The `summary` object provides a high-level overview of the operation.
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

    def _success(message: str, llm_content: Dict[str, Any], **data: Any) -> Dict[str, Any]:
        return ToolResult(
            status="success",
            message=message,
            llm_content=llm_content,
            data=data,
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
        file_extension = f.suffix.lower()
        
        # Determine file type for better categorization
        file_type = "binary"
        if file_extension in {'.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.md', '.txt', '.json', '.xml', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf', '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd'}:
            file_type = "text"
        elif file_extension in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.ico', '.tiff', '.tga'}:
            file_type = "image"
        elif file_extension in {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma'}:
            file_type = "audio"
        elif file_extension in {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv', '.m4v'}:
            file_type = "video"
        elif file_extension in {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'}:
            file_type = "document"
        elif file_extension in {'.zip', '.tar', '.gz', '.bz2', '.7z', '.rar'}:
            file_type = "archive"
        
        # Prepare response data
        rel_display = f.relative_to(WORKSPACE_ROOT) if str(f).startswith(str(WORKSPACE_ROOT)) else Path(path)
        
        if permanent:
            # Permanent deletion
            f.unlink()
            
            # Build structured LLM content
            llm_content = {
                "operation": {
                    "type": "delete_file",
                    "path": str(rel_display),
                    "permanent": True,
                    "recoverable": False,
                    "was_symlink": was_symlink
                },
                "file_info": {
                    "size_bytes": original_size,
                    "file_type": file_type,
                    "extension": file_extension
                },
                "summary": {
                    "operation_type": "permanent_deletion",
                    "success": True
                }
            }
            
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
            timestamp = datetime.now().isoformat()
            
            # Move file to trash
            shutil.move(str(f), str(trash_path))
            
            # Build structured LLM content
            llm_content = {
                "operation": {
                    "type": "delete_file",
                    "path": str(rel_display),
                    "permanent": False,
                    "recoverable": True,
                    "was_symlink": was_symlink
                },
                "file_info": {
                    "size_bytes": original_size,
                    "file_type": file_type,
                    "extension": file_extension
                },
                "trash_info": {
                    "trash_path": str(trash_path.relative_to(WORKSPACE_ROOT)),
                    "original_path": str(rel_display),
                    "timestamp": timestamp
                },
                "summary": {
                    "operation_type": "move_to_trash",
                    "success": True
                }
            }
            
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
    """Register the delete_file tool with proper tags synchronization."""
    common = dict(
        tags={"coding", "filesystem", "delete", "file"}, 
        annotations={"category": "coding", "tags": ["coding", "filesystem", "delete", "file"]}
    )
    mcp.tool(**common)(delete_file) 