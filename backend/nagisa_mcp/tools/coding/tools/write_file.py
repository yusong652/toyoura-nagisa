"""Filesystem helper tools — *write_file* implementation.

This module exposes a single FastMCP-compatible tool that writes UTF-8 text
files inside the workspace directory. The only public symbol meant to be
registered is :pyfunc:`write_file`.
"""

import errno
from pathlib import Path
from typing import Dict, Any, Optional

from pydantic import Field
from pydantic.fields import FieldInfo
from fastmcp import FastMCP  # type: ignore

from .config import get_tools_config
from ..utils.tool_result import ToolResult
from ..utils.path_security import (
    WORKSPACE_ROOT, 
    validate_path_in_workspace, 
    is_safe_symlink, 
    check_parent_symlinks
)

__all__ = ["write_file", "register_write_file_tool"]

# Constants for file size limits
MAX_CONTENT_SIZE_BYTES = 20 * 1024 * 1024  # 20 MiB (same as read_file limit)
MAX_CONTENT_SIZE_CHARS = MAX_CONTENT_SIZE_BYTES // 2  # Conservative estimate for UTF-8


def write_file(
    path: str = Field(..., description="Path (relative to workspace) to write to."),
    content: str = Field(..., description="Text content to write"),
    encoding: str = Field("utf-8", description="File encoding"),
    append: bool = Field(False, description="Append instead of overwrite"),
) -> Dict[str, Any]:
    """Creates, overwrites, or appends to a text file in the workspace.

    ## Core Functionality
    - **Path:** Specify the file's location with `path`. If the file doesn't exist, it will be created. Parent directories are also created automatically if they don't exist.
    - **Content:** Provide the text content to be written in the `content` parameter.
    - **Mode:**
        - By default, this tool **overwrites** the entire file.
        - To **append** content to the end of an existing file, set `append=True`.

    ## Strategic Usage
    - This is your primary tool for saving new code, documents, or modifying existing ones.
    - **To modify a file:** You must first use `read_file` to get its current content, modify that content in your context, and then use this `write_file` tool to save the complete, updated content back to the file.
    - This tool is for **text content only**. Do not attempt to write binary data.

    ## Return Value (What you will receive)
    The output you get back from this tool will be one of the following two things:

    1.  **Success:** A single `string` confirming the successful write operation.
        - Example: `"Successfully wrote 512 bytes to src/app.js"`
    2.  **Error:** A single `string` starting with "Error:", explaining what went wrong.
        - Example: `"Error: Permission denied when writing file"`

    You MUST check the response to confirm success or handle the error.
    """

    # ------------------------------------------------------------------
    # Parameter validation (manual to stay lightweight)
    # ------------------------------------------------------------------
    
    # Handle Pydantic FieldInfo objects when invoked programmatically
    if isinstance(encoding, FieldInfo):
        encoding = "utf-8"
    if isinstance(append, FieldInfo):
        append = False

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

    # Validate encoding parameter
    if not isinstance(encoding, str) or not encoding.strip():
        return _error("Encoding must be a non-empty string")

    # Validate content size to prevent disk exhaustion
    content_size_chars = len(content)
    if content_size_chars > MAX_CONTENT_SIZE_CHARS:
        size_mb = content_size_chars / (1024 * 1024)
        return _error(f"Content exceeds maximum size limit (20 MB): {size_mb:.2f} MB")

    # Estimate byte size for UTF-8 content (conservative)
    estimated_bytes = len(content.encode(encoding))
    if estimated_bytes > MAX_CONTENT_SIZE_BYTES:
        size_mb = estimated_bytes / (1024 * 1024)
        return _error(f"Content exceeds maximum size limit (20 MB): {size_mb:.2f} MB")

    try:
        abs_p = Path(abs_path)
        
        # Symlink security checks
        if abs_p.exists():
            # Check if target file itself is an unsafe symlink
            if abs_p.is_symlink() and not is_safe_symlink(abs_p):
                return _error("Cannot write to symlink pointing outside workspace")
        
        # Check if any parent directory is an unsafe symlink
        if not check_parent_symlinks(abs_p):
            return _error("Cannot write to path with parent symlink pointing outside workspace")
        
        # Create parent directories if they don't exist
        abs_p.parent.mkdir(parents=True, exist_ok=True)
        
        # Additional check after mkdir - ensure created directories are safe
        if not check_parent_symlinks(abs_p):
            return _error("Parent directory creation resulted in unsafe symlink structure")
        
        # Determine write mode
        mode = "a" if append else "w"
        
        # Write the content
        with abs_p.open(mode, encoding=encoding) as fh:
            fh.write(content)

        # Get file statistics
        size = abs_p.stat().st_size
        rel_display = abs_p.relative_to(WORKSPACE_ROOT)
        
        # Prepare response content
        operation_mode = "appended to" if append else "wrote to"
        llm_content = f"Successfully {operation_mode} {rel_display} ({estimated_bytes} bytes written)."
        
        # Use debug mode setting from config
        display_msg = llm_content if get_tools_config().debug_mode else "File written successfully"

        return _success(
            display_msg,
            llm_content,
            path=str(abs_p),
            size=size,
            mode=operation_mode,
            encoding=encoding,
            content_size=estimated_bytes,
        )

    except PermissionError:
        return _error("Permission denied when writing file")
    except IsADirectoryError:
        return _error("Specified path is a directory, not a file")
    except UnicodeEncodeError as exc:
        return _error(f"Encoding error: {exc}")
    except OSError as exc:
        # Handle specific disk space errors
        if exc.errno == errno.ENOSPC:
            return _error("Insufficient disk space (ENOSPC) - cannot write file")
        elif exc.errno == errno.EDQUOT:
            return _error("Disk quota exceeded (EDQUOT) - cannot write file")
        elif exc.errno == errno.EFBIG:
            return _error("File too large (EFBIG) - exceeds filesystem limits")
        else:
            return _error(f"IO error: {exc}")
    except Exception as exc:  # pylint: disable=broad-except
        return _error(f"Unexpected error: {exc}")


# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_write_file_tool(mcp: FastMCP):
    """Register the write_file tool with proper tags synchronization."""
    common = dict(
        tags={"coding", "filesystem", "write", "file", "create"}, 
        annotations={"category": "coding", "tags": ["coding", "filesystem", "write", "file", "create"]}
    )
    mcp.tool(**common)(write_file) 