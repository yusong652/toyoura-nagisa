"""ls tool – minimal directory listing following Unix philosophy.

This tool provides simple directory listing functionality with minimal parameters,
focusing on doing one thing well: listing directory contents.

Modeled after Claude Code's LS tool for simplicity and clarity.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import fnmatch
from datetime import datetime

from pydantic import Field
from pydantic.fields import FieldInfo
from fastmcp import FastMCP  # type: ignore

from ..utils.path_security import (
    validate_path_in_workspace, 
    WORKSPACE_ROOT, 
    is_safe_symlink,
    check_parent_symlinks
)
from backend.infrastructure.mcp.utils.tool_result import ToolResult

__all__ = ["ls", "register_ls_tool"]

# -----------------------------------------------------------------------------
# Main implementation
# -----------------------------------------------------------------------------

def ls(
    path: str = Field(
        ...,
        description="The absolute path to the directory to list (must be absolute, not relative)",
    ),
    ignore: Optional[List[str]] = Field(
        None,
        description="List of glob patterns to ignore",
    ),
) -> Dict[str, Any]:
    """List files and directories in a given path.
    
    Simple, Unix-like directory listing with optional ignore patterns.
    The path parameter must be an absolute path, not a relative path.
    
    Args:
        path: The absolute path to the directory to list
        ignore: Optional list of glob patterns to ignore
    
    Returns:
        Dict[str, Any]: ToolResult with directory contents:
            - status: "success" or "error"
            - message: User-facing summary
            - llm_content: Structured data for LLM
            - data: Raw directory listing data
    
    Example:
        # List current directory
        ls("/Users/username/project")
        
        # List with ignore patterns
        ls("/Users/username/project", ignore=["*.pyc", "__pycache__", ".git"])
    """

    # Handle Pydantic FieldInfo objects when invoked programmatically
    if isinstance(ignore, FieldInfo):
        ignore = None

    # Helper shortcuts for consistent results
    def _error(message: str) -> Dict[str, Any]:
        return ToolResult(status="error", message=message, error=message).model_dump()

    def _success(message: str, llm_content: Any, **data: Any) -> Dict[str, Any]:
        return ToolResult(
            status="success",
            message=message,
            llm_content=llm_content,
            data=data,
        ).model_dump()

    # Validate path is provided
    if not path or not path.strip():
        return _error("Path is required and cannot be empty")

    # For workspace-relative paths, convert to absolute
    if not path.startswith('/'):
        # Convert relative path to absolute using workspace root
        abs_path = validate_path_in_workspace(path)
        if abs_path is None:
            return _error(f"Path is outside workspace: {path}")
    else:
        # Validate absolute path is within workspace
        abs_path = validate_path_in_workspace(path)
        if abs_path is None:
            return _error(f"Path is outside workspace: {path}")

    try:
        target_dir = Path(abs_path)
        
        # Check path existence and type
        if not target_dir.exists():
            return _error(f"Directory does not exist: {path}")
        if not target_dir.is_dir():
            return _error(f"Path is not a directory: {path}")

        # Additional symlink safety check
        if target_dir.is_symlink() and not is_safe_symlink(target_dir):
            return _error("Target directory is an unsafe symlink pointing outside workspace")

        # List directory contents
        items = []
        files_count = 0
        dirs_count = 0
        skipped_count = 0
        
        for item_path in sorted(target_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            try:
                # Security checks for symlinks
                if item_path.is_symlink() and not is_safe_symlink(item_path):
                    skipped_count += 1
                    continue
                
                if not check_parent_symlinks(item_path):
                    skipped_count += 1
                    continue
                
                # Apply ignore patterns if provided
                if ignore:
                    item_name = item_path.name
                    should_ignore = False
                    for pattern in ignore:
                        if fnmatch.fnmatch(item_name, pattern):
                            should_ignore = True
                            break
                    if should_ignore:
                        skipped_count += 1
                        continue
                
                # Get basic item info
                try:
                    stat_info = item_path.stat()
                    size = stat_info.st_size if item_path.is_file() else None
                    modified = datetime.fromtimestamp(stat_info.st_mtime).isoformat()
                except Exception:
                    size = None
                    modified = None
                
                # Determine item type
                if item_path.is_dir():
                    item_type = "directory"
                    dirs_count += 1
                elif item_path.is_file():
                    item_type = "file"
                    files_count += 1
                elif item_path.is_symlink():
                    item_type = "symlink"
                else:
                    item_type = "other"
                
                # Build item info
                item_info = {
                    "name": item_path.name,
                    "type": item_type,
                }
                
                # Add optional metadata
                if size is not None:
                    item_info["size"] = size
                if modified is not None:
                    item_info["modified"] = modified
                
                items.append(item_info)
                
            except PermissionError:
                skipped_count += 1
                continue
            except Exception:
                skipped_count += 1
                continue
        
        # Build summary
        total_items = len(items)
        
        # Create user-facing message
        message_parts = []
        if files_count > 0:
            message_parts.append(f"{files_count} file{'s' if files_count != 1 else ''}")
        if dirs_count > 0:
            message_parts.append(f"{dirs_count} director{'ies' if dirs_count != 1 else 'y'}")
        
        if message_parts:
            message = f"Found {' and '.join(message_parts)}"
        else:
            message = "No items found"
        
        if skipped_count > 0:
            message += f" ({skipped_count} items skipped)"
        
        # Build structured LLM content
        llm_content = {
            "operation": {
                "type": "ls",
                "path": str(target_dir.relative_to(WORKSPACE_ROOT)) if target_dir != WORKSPACE_ROOT else ".",
            },
            "result": {
                "items": items,
                "total": total_items,
                "files": files_count,
                "directories": dirs_count,
            }
        }
        
        if skipped_count > 0:
            llm_content["skipped"] = skipped_count
        
        if ignore:
            llm_content["ignore_patterns"] = ignore
        
        return _success(
            message,
            llm_content,
            items=items,
            summary={
                "total": total_items,
                "files": files_count,
                "directories": dirs_count,
                "skipped": skipped_count,
            },
            path=str(target_dir.relative_to(WORKSPACE_ROOT)) if target_dir != WORKSPACE_ROOT else ".",
        )

    except PermissionError:
        return _error(f"Permission denied when accessing directory: {path}")
    except OSError as exc:
        return _error(f"IO error: {exc}")
    except Exception as exc:
        return _error(f"Unexpected error during directory listing: {exc}")

# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_ls_tool(mcp: FastMCP):
    """Register the ls tool with proper tags synchronization."""
    common = dict(
        tags={"coding", "filesystem", "directory", "listing"}, 
        annotations={"category": "coding", "tags": ["coding", "filesystem", "directory", "listing"]}
    )
    mcp.tool(**common)(ls)