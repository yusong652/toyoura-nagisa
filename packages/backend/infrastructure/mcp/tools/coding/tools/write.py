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
from fastmcp.server.context import Context  # type: ignore

# from .config import get_tools_config  # Removed unused import
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.mcp.utils.path_normalization import normalize_path_separators, path_to_llm_format
from ..utils.path_security import (
    validate_path_in_workspace,
    get_workspace_root_async,
    is_safe_symlink,
    check_parent_symlinks
)

__all__ = ["write", "register_write_tool"]

# Constants for file size limits
MAX_CONTENT_SIZE_BYTES = 20 * 1024 * 1024  # 20 MiB (same as read_file limit)
MAX_CONTENT_SIZE_CHARS = MAX_CONTENT_SIZE_BYTES // 2  # Conservative estimate for UTF-8


async def write(
    context: Context,
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

    PFC Script Guidelines (when writing .py files for PFC simulations):
    - Add print() statements for progress monitoring (visible via pfc_check_task_status)
    - Use itasca.command("model save 'name'") for checkpoint persistence
    - Export data to CSV/JSON files for post-analysis (write analysis scripts to process, don't read CSV directly)
    """

    # ------------------------------------------------------------------
    # Parameter validation (manual to stay lightweight)
    # ------------------------------------------------------------------

    # Fixed encoding for simplicity
    encoding = "utf-8"

    # Normalize path separators for cross-platform compatibility
    # This handles cases where LLM generates mixed separators (e.g., C:\path/to/file)
    if not file_path or not file_path.strip():
        return error_response("file_path is required and cannot be empty")

    # Keep original path for LLM-friendly error messages (forward slashes)
    original_path_for_display = path_to_llm_format(file_path.strip())
    file_path = normalize_path_separators(file_path.strip())

    # Get workspace root dynamically based on current session
    workspace_root = await get_workspace_root_async(context)

    # Validate path security against dynamic workspace
    abs_path = validate_path_in_workspace(file_path, workspace_root)
    if abs_path is None:
        return error_response(f"Path is outside of workspace: {original_path_for_display}")

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

        # Check if file already exists and read original content for diff
        file_existed = abs_p.exists()
        original_content = ""
        if file_existed:
            try:
                with abs_p.open("r", encoding=encoding, errors='replace') as fh:
                    original_content = fh.read()
            except Exception:
                # If we can't read original, just use empty string
                original_content = ""

        # Symlink security checks (use dynamic workspace root for consistency)
        if file_existed:
            # Check if target file itself is an unsafe symlink
            if abs_p.is_symlink() and not is_safe_symlink(abs_p, workspace_root):
                return error_response("Cannot write to symlink pointing outside workspace")

        # Check if any parent directory is an unsafe symlink
        if not check_parent_symlinks(abs_p, workspace_root):
            return error_response("Cannot write to path with parent symlink pointing outside workspace")

        # Create parent directories if they don't exist
        abs_p.parent.mkdir(parents=True, exist_ok=True)

        # Additional check after mkdir - ensure created directories are safe
        if not check_parent_symlinks(abs_p, workspace_root):
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
        # Use absolute path with forward slashes for LLM consistency (matches Claude Code)
        abs_display = path_to_llm_format(abs_p)

        # Create simple Claude Code-style message
        if not file_existed:
            display_msg = f"File created successfully at: {abs_display}"
        else:
            display_msg = f"File updated successfully at: {abs_display}"

        # Generate unified diff for CLI display
        import difflib
        diff_lines = list(difflib.unified_diff(
            original_content.splitlines(),
            content.splitlines(),
            fromfile=abs_display,
            tofile=abs_display,
            lineterm=''
        ))
        diff_content = '\n'.join(diff_lines) if diff_lines else ''

        # Count additions and deletions
        additions = sum(1 for line in diff_lines if line.startswith('+') and not line.startswith('+++'))
        deletions = sum(1 for line in diff_lines if line.startswith('-') and not line.startswith('---'))

        return success_response(
            display_msg,
            llm_content={
                "parts": [
                    {"type": "text", "text": display_msg}
                ]
            },
            file_path=abs_display,
            size_bytes=size_bytes,
            lines_count=lines_count,
            file_created=not file_existed,
            # Include diff info in data for CLI display
            diff={
                "content": diff_content,
                "additions": additions,
                "deletions": deletions,
                "file_path": abs_display,
            }
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