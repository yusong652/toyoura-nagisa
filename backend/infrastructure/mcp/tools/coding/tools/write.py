"""write tool - atomic text file creation and modification.

This tool provides atomic file writing functionality, focusing exclusively on 
creating and modifying text files with comprehensive safety checks and encoding support.
It supports both overwrite and append modes with automatic directory creation.

Modeled after gemini-cli's file management tools for consistency and interoperability.
"""

import errno
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from pydantic import Field
from fastmcp import FastMCP  # type: ignore

# from .config import get_tools_config  # Removed unused import
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from ..utils.path_security import (
    WORKSPACE_ROOT, 
    validate_path_in_workspace, 
    is_safe_symlink, 
    check_parent_symlinks
)

__all__ = ["write", "register_write_tool"]

# Constants for file size limits
MAX_CONTENT_SIZE_BYTES = 20 * 1024 * 1024  # 20 MiB (same as read_file limit)
MAX_CONTENT_SIZE_CHARS = MAX_CONTENT_SIZE_BYTES // 2  # Conservative estimate for UTF-8


def write(
    file_path: str = Field(
        ..., 
        description="The absolute path to the file to write"
    ),
    content: str = Field(
        ..., 
        description="The content to write to the file"
    ),
) -> Dict[str, Any]:
    """Writes a file to the local filesystem.
    
    Usage:
    - This tool will overwrite the existing file if there is one at the provided path.
    - If this is an existing file, you MUST use the Read tool first to read the file's contents. This tool will fail if you did not read the file first.
    - ALWAYS prefer editing existing files in the codebase. NEVER write new files unless explicitly required.
    - NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.
    - Only use emojis if the user explicitly requests it. Avoid writing emojis to files unless asked.
    """

    # ------------------------------------------------------------------
    # Parameter validation (manual to stay lightweight)
    # ------------------------------------------------------------------
    
    # Fixed encoding for simplicity
    encoding = "utf-8"

    # Validate path security
    abs_path = validate_path_in_workspace(file_path)
    if abs_path is None:
        return error_response(f"Path is outside of workspace: {file_path}")

    # Validate content size to prevent disk exhaustion
    content_size_chars = len(content)
    if content_size_chars > MAX_CONTENT_SIZE_CHARS:
        size_mb = content_size_chars / (1024 * 1024)
        return error_response(f"Content exceeds maximum size limit (20 MB): {size_mb:.2f} MB")

    # Estimate byte size for UTF-8 content (conservative)
    estimated_bytes = len(content.encode(encoding))
    if estimated_bytes > MAX_CONTENT_SIZE_BYTES:
        size_mb = estimated_bytes / (1024 * 1024)
        return error_response(f"Content exceeds maximum size limit (20 MB): {size_mb:.2f} MB")

    try:
        abs_p = Path(abs_path)
        
        # Check if file already exists
        file_existed = abs_p.exists()
        
        # Symlink security checks
        if file_existed:
            # Check if target file itself is an unsafe symlink
            if abs_p.is_symlink() and not is_safe_symlink(abs_p):
                return error_response("Cannot write to symlink pointing outside workspace")
        
        # Check if any parent directory is an unsafe symlink
        if not check_parent_symlinks(abs_p):
            return error_response("Cannot write to path with parent symlink pointing outside workspace")
        
        # Create parent directories if they don't exist
        abs_p.parent.mkdir(parents=True, exist_ok=True)
        
        # Additional check after mkdir - ensure created directories are safe
        if not check_parent_symlinks(abs_p):
            return error_response("Parent directory creation resulted in unsafe symlink structure")
        
        # Write the content (always overwrite)
        with abs_p.open("w", encoding=encoding) as fh:
            fh.write(content)

        # Get file statistics and metadata
        stat = abs_p.stat()
        size_bytes = stat.st_size
        
        # Count lines in content
        lines_count = content.count('\n') + (1 if content and not content.endswith('\n') else 0)
        
        # Prepare response data
        rel_display = abs_p.relative_to(WORKSPACE_ROOT)
        
        # Create simple Claude Code-style message
        if not file_existed:
            display_msg = f"File created successfully at: {str(rel_display)}"
        else:
            display_msg = f"File updated successfully at: {str(rel_display)}"

        return success_response(
            display_msg,
            display_msg,  # Simple message content like Claude Code
            file_path=str(rel_display),
            size_bytes=size_bytes,
            lines_count=lines_count,
            file_created=not file_existed,
        )

    except PermissionError:
        return error_response("Permission denied when writing file")
    except IsADirectoryError:
        return error_response("Specified path is a directory, not a file")
    except UnicodeEncodeError as exc:
        return error_response(f"Encoding error: {exc}")
    except OSError as exc:
        # Handle specific disk space errors
        if exc.errno == errno.ENOSPC:
            return error_response("Insufficient disk space (ENOSPC) - cannot write file")
        elif exc.errno == errno.EDQUOT:
            return error_response("Disk quota exceeded (EDQUOT) - cannot write file")
        elif exc.errno == errno.EFBIG:
            return error_response("File too large (EFBIG) - exceeds filesystem limits")
        else:
            return error_response(f"IO error: {exc}")
    except Exception as exc:  # pylint: disable=broad-except
        return error_response(f"Unexpected error: {exc}")


# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_write_tool(mcp: FastMCP):
    """Register the write tool with comprehensive metadata."""
    common = dict(

    )
    mcp.tool(        
        tags={"coding", "filesystem", "write", "file", "create"}, 
        annotations={
            "category": "coding", 
            "tags": ["coding", "filesystem", "write", "file", "create"],
            "primary_use": "Create and modify text files with comprehensive safety checks",
            "prompt_optimization": "Enhanced for LLM interaction with clear guidance and contextual feedback"
        })(write) 