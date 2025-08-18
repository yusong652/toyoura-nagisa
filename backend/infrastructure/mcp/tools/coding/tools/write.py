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
from backend.infrastructure.mcp.utils.tool_result import ToolResult
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

    # Helper shortcuts for consistent results
    def _error(message: str, suggestion: str = None) -> Dict[str, Any]:
        error_msg = message
        if suggestion:
            error_msg += f" Suggestion: {suggestion}"
        return ToolResult(status="error", message=error_msg, error=message).model_dump()

    def _success(message: str, llm_content: Dict[str, Any], **data: Any) -> Dict[str, Any]:
        return ToolResult(
            status="success",
            message=message,
            llm_content=llm_content,
            data=data,
        ).model_dump()

    # Validate path security
    abs_path = validate_path_in_workspace(file_path)
    if abs_path is None:
        return _error(
            f"Path is outside of workspace: {file_path}",
            "Use paths relative to workspace root, e.g., 'src/app.py', 'config/settings.json', or 'docs/README.md'"
        )

    # Validate content size to prevent disk exhaustion
    content_size_chars = len(content)
    if content_size_chars > MAX_CONTENT_SIZE_CHARS:
        size_mb = content_size_chars / (1024 * 1024)
        return _error(
            f"Content exceeds maximum size limit (20 MB): {size_mb:.2f} MB",
            "Split large files into smaller chunks or use streaming for large data files"
        )

    # Estimate byte size for UTF-8 content (conservative)
    estimated_bytes = len(content.encode(encoding))
    if estimated_bytes > MAX_CONTENT_SIZE_BYTES:
        size_mb = estimated_bytes / (1024 * 1024)
        return _error(
            f"Content exceeds maximum size limit (20 MB): {size_mb:.2f} MB",
            "Content is too large after encoding. Consider breaking into smaller files or using compression"
        )

    try:
        abs_p = Path(abs_path)
        
        # Check if file already exists
        file_existed = abs_p.exists()
        
        # Symlink security checks
        if file_existed:
            # Check if target file itself is an unsafe symlink
            if abs_p.is_symlink() and not is_safe_symlink(abs_p):
                return _error(
                    "Cannot write to symlink pointing outside workspace",
                    "Use a regular file path instead of a symlink, or ensure the symlink points within the workspace"
                )
        
        # Check if any parent directory is an unsafe symlink
        if not check_parent_symlinks(abs_p):
            return _error(
                "Cannot write to path with parent symlink pointing outside workspace",
                "Use a directory path without symlinks, or ensure all parent symlinks point within the workspace"
            )
        
        # Count parent directories that need to be created
        parent_dirs_created = 0
        if not abs_p.parent.exists():
            # Count how many parent directories will be created
            current = abs_p.parent
            while not current.exists():
                parent_dirs_created += 1
                current = current.parent
                if current == WORKSPACE_ROOT:
                    break
        
        # Create parent directories if they don't exist
        abs_p.parent.mkdir(parents=True, exist_ok=True)
        
        # Additional check after mkdir - ensure created directories are safe
        if not check_parent_symlinks(abs_p):
            return _error(
                "Parent directory creation resulted in unsafe symlink structure",
                "Choose a different path that doesn't involve symlinks pointing outside the workspace"
            )
        
        # Write the content (always overwrite)
        with abs_p.open("w", encoding=encoding) as fh:
            fh.write(content)

        # Get file statistics and metadata
        stat = abs_p.stat()
        size_bytes = stat.st_size
        # Note: modification time available if needed for future enhancements
        # _modified_time = datetime.fromtimestamp(stat.st_mtime).isoformat()
        
        # Determine file type based on extension
        file_extension = abs_p.suffix.lower()
        file_type = "text"
        if file_extension in {'.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.md', '.txt', '.json', '.xml', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf', '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd'}:
            file_type = "text"
        elif file_extension in {'.log', '.out', '.err'}:
            file_type = "log"
        elif file_extension in {'.md', '.rst', '.txt'}:
            file_type = "documentation"
        else:
            file_type = "text"
        
        # Count lines in content
        lines_count = content.count('\n') + (1 if content and not content.endswith('\n') else 0)
        
        # Prepare response data
        rel_display = abs_p.relative_to(WORKSPACE_ROOT)
        
        # Build structured LLM content following unified standard
        # Focus on information most relevant for LLM decision-making
        llm_content = {
            "operation": {
                "type": "write_file",
                "path": str(rel_display),
                "mode": "overwrite"
            },
            "result": {
                "file_created": not file_existed,
                "bytes_written": size_bytes,
                "lines_written": lines_count,
                "success": True
            },
            "file_info": {
                "file_type": file_type,
                "extension": file_extension,
                "encoding": encoding
            },
            "summary": {
                "operation_type": "write_file",
                "success": True,
                "file_status": "created" if not file_existed else "modified",
                "content_size": "large" if size_bytes > 10000 else "small"
            }
        }
        
        # Add context hints for LLM understanding
        if not file_existed:
            llm_content["context"] = {
                "action": "created_new_file",
                "note": "File was created successfully with the provided content"
            }
        else:
            llm_content["context"] = {
                "action": "overwrote_file",
                "note": "Existing file was completely replaced with new content",
                "alternative": "For precise edits, consider using the replace tool instead"
            }
        
        # Add simple guidance for common file types
        if file_extension in {'.py', '.js', '.ts', '.jsx', '.tsx'}:
            llm_content["next_steps"] = "Consider running tests or linting"
        elif file_extension in {'.json', '.yaml', '.yml', '.toml'}:
            llm_content["next_steps"] = "Validate configuration format"
        elif file_extension in {'.md', '.txt', '.rst'}:
            llm_content["next_steps"] = "Review documentation content"
        
        # Add tool selection guidance
        if not file_existed:
            llm_content["tool_usage"] = "Perfect for creating new files"
        else:
            llm_content["tool_usage"] = "Used for complete file replacement. For precise edits, consider the replace tool."
        
        # Create informative display message for LLM
        if not file_existed:
            display_msg = f"Created new file '{rel_display}' ({size_bytes} bytes, {lines_count} lines)"
        else:
            display_msg = f"Completely rewrote '{rel_display}' ({size_bytes} bytes, {lines_count} lines). For precise edits, consider using replace tool."

        return _success(
            display_msg,
            llm_content,
            path=str(abs_p),
            size=size_bytes,
            mode="overwrite",
            encoding=encoding,
            content_size=estimated_bytes,
            file_created=not file_existed,
            parent_dirs_created=parent_dirs_created,
        )

    except PermissionError:
        return _error(
            "Permission denied when writing file",
            "Check file permissions or try writing to a different location. File may be read-only or in use"
        )
    except IsADirectoryError:
        return _error(
            "Specified path is a directory, not a file",
            "Add a filename to the path, e.g., change 'src/' to 'src/app.py'"
        )
    except UnicodeEncodeError as exc:
        return _error(
            f"Encoding error: {exc}",
            "Try using 'utf-8' encoding or remove non-ASCII characters from the content"
        )
    except OSError as exc:
        # Handle specific disk space errors
        if exc.errno == errno.ENOSPC:
            return _error(
                "Insufficient disk space (ENOSPC) - cannot write file",
                "Free up disk space by removing unnecessary files or choose a different location"
            )
        elif exc.errno == errno.EDQUOT:
            return _error(
                "Disk quota exceeded (EDQUOT) - cannot write file",
                "You have exceeded your disk quota. Clean up files or request more storage space"
            )
        elif exc.errno == errno.EFBIG:
            return _error(
                "File too large (EFBIG) - exceeds filesystem limits",
                "Split the content into smaller files or use a different filesystem that supports larger files"
            )
        else:
            return _error(
                f"IO error: {exc}",
                "Check file system permissions and disk space, or try writing to a different location"
            )
    except Exception as exc:  # pylint: disable=broad-except
        return _error(
            f"Unexpected error: {exc}",
            "Verify the file path is correct and the content is valid text"
        )


# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_write_tool(mcp: FastMCP):
    """Register the write tool with comprehensive metadata."""
    common = dict(
        tags={"coding", "filesystem", "write", "file", "create"}, 
        annotations={
            "category": "coding", 
            "tags": ["coding", "filesystem", "write", "file", "create"],
            "primary_use": "Create and modify text files with comprehensive safety checks",
            "prompt_optimization": "Enhanced for LLM interaction with clear guidance and contextual feedback"
        }
    )
    mcp.tool(**common)(write) 