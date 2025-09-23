"""ls tool – minimal directory listing following Unix philosophy.

This tool provides simple directory listing functionality with minimal parameters,
focusing on doing one thing well: listing directory contents.

Modeled after Claude Code's LS tool for simplicity and clarity.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import fnmatch

from pydantic import Field
from pydantic.fields import FieldInfo
from fastmcp import FastMCP  # type: ignore

from ..utils.path_security import (
    validate_path_in_workspace, 
    WORKSPACE_ROOT, 
    is_safe_symlink,
    check_parent_symlinks
)
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response

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
    """Lists files and directories in a given path. The path parameter must be an absolute path, not a relative path. You can optionally provide an array of glob patterns to ignore with the ignore parameter. You should generally prefer the Glob and Grep tools, if you know which directories to search."""

    # Handle Pydantic FieldInfo objects when invoked programmatically
    if isinstance(ignore, FieldInfo):
        ignore = None

    # Validate path is provided
    if not path or not path.strip():
        return error_response("Path is required and cannot be empty")

    # Validate path is within workspace
    abs_path = validate_path_in_workspace(path)
    if abs_path is None:
        return error_response(f"Path is outside workspace: {path}")

    try:
        target_dir = Path(abs_path)
        
        # Check path existence and type
        if not target_dir.exists():
            return error_response(f"Directory does not exist: {path}")
        if not target_dir.is_dir():
            return error_response(f"Path is not a directory: {path}")

        # Additional symlink safety check
        if target_dir.is_symlink() and not is_safe_symlink(target_dir):
            return error_response("Target directory is an unsafe symlink pointing outside workspace")

        # List directory contents and build Claude Code style tree structure
        tree_lines = []
        files_count = 0
        dirs_count = 0
        skipped_count = 0
        
        # Build tree structure similar to Claude Code
        # Start with the target directory path
        workspace_relative = target_dir.relative_to(WORKSPACE_ROOT) if target_dir != WORKSPACE_ROOT else Path(".")
        tree_lines.append(f"- {WORKSPACE_ROOT}/")
        
        # Add intermediate directories if needed
        if workspace_relative != Path("."):
            parts = workspace_relative.parts
            current_indent = "  "
            for part in parts:
                tree_lines.append(f"{current_indent}- {part}/")
                current_indent += "  "
        
        # List items in the directory  
        item_indent = "  " + "  " * len(workspace_relative.parts) if workspace_relative != Path(".") else "  "
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
                
                # Build tree line for this item
                if item_path.is_dir():
                    tree_lines.append(f"{item_indent}- {item_path.name}/")
                    dirs_count += 1
                else:
                    tree_lines.append(f"{item_indent}- {item_path.name}")
                    files_count += 1
                    
            except PermissionError:
                skipped_count += 1
                continue
            except Exception:
                skipped_count += 1
                continue
        
        # Build summary
        
        # Create user-facing message
        message_parts = []
        if files_count > 0:
            message_parts.append(f"{files_count} file{'s' if files_count != 1 else ''}")
        if dirs_count > 0:
            message_parts.append(f"{dirs_count} director{'ies' if dirs_count != 1 else 'y'}")
        
        if message_parts:
            message = f"Found {' and '.join(message_parts)}"
        else:
            message = "Directory is empty"
        
        if skipped_count > 0:
            message += f" ({skipped_count} items skipped)"
        
        # Build Claude Code style LLM content - tree structure
        llm_content = "\n".join(tree_lines)
        
        return success_response(
            message,
            llm_content,
            files=files_count,
            directories=dirs_count,
            skipped=skipped_count,
        )

    except PermissionError:
        return error_response(f"Permission denied when accessing directory: {path}")
    except OSError as exc:
        return error_response(f"IO error: {exc}")
    except Exception as exc:
        return error_response(f"Unexpected error during directory listing: {exc}")

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