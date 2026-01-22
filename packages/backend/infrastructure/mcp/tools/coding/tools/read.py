"""Read single files with automatic encoding detection.

Supports:
- Text files: automatic encoding detection, line-based reading
- Binary files: images/docs/media returned as base64 for multimodal LLMs
  (with graceful degradation for non-multimodal LLMs)
- Security: path validation, size limits (50MB max)
- Reading modes: full, preview (100 lines), paginated
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

from pydantic import Field
from fastmcp import FastMCP  # type: ignore
from fastmcp.server.context import Context  # type: ignore

logger = logging.getLogger(__name__)

from ..utils.path_security import (
    validate_path_in_workspace,
    get_workspace_root_async,
    is_safe_symlink,
    check_parent_symlinks
)
from ..utils.file_reader import (
    read_file_safely,
    MAX_FILE_SIZE_BYTES,
    ContentFormat,
    get_multimodal_support_for_session
)
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.mcp.utils.path_normalization import normalize_path_separators, path_to_llm_format

__all__ = ["read", "register_read_tool"]

# -----------------------------------------------------------------------------
# Main implementation
# -----------------------------------------------------------------------------

async def read(
    context: Context,
    path: str = Field(
        ...,
        min_length=1,
        description="The absolute path to the file to read",
    ),
    offset: Optional[int] = Field(
        None,
        description="The line number to start reading from. Only provide if the file is too large to read at once",
    ),
    limit: Optional[int] = Field(
        None,
        description="The number of lines to read. Only provide if the file is too large to read at once.",
    ),
) -> Dict[str, Any]:
    """Reads a file from the local filesystem. You can access any file directly by using this tool.
Assume this tool is able to read all files on the machine. If the User provides a path to a file assume that path is valid. It is okay to read a file that does not exist; an error will be returned.

Usage:
- The file_path parameter must be an absolute path, not a relative path
- By default, it reads up to 2000 lines starting from the beginning of the file
- You can optionally specify a line offset and limit (especially handy for long files), but it's recommended to read the whole file by not providing these parameters
- Any lines longer than 2000 characters will be truncated
- Results are returned with line numbers starting at 1 (format: "     1→<content>")
- The line numbers and arrow (→) are for positioning reference - they are NOT part of the actual file content
- This tool allows reading images (PNG, JPG, etc). When reading an image file the contents are presented as base64 data for multimodal LLM consumption
- This tool can read PDF files (.pdf). PDFs are processed page by page, extracting both text and visual content for analysis
- This tool can read Jupyter notebooks (.ipynb files) and returns all cells with their outputs, combining code, text, and visualizations
- You can call multiple tools in a single response. It is better to speculatively read multiple files as a batch that are potentially useful
- You may be asked to read screenshots. If provided a screenshot path, use this tool to view the file. This tool works with all temporary file paths
- If you read a file that exists but has empty contents you will receive a system reminder warning in place of file contents"""

    # ------------------------------------------------------------------
    # Parameter validation and normalization
    # ------------------------------------------------------------------

    # Validate parameters
    if offset is not None and offset < 0:
        return error_response("offset must be non-negative")

    if limit is not None and limit <= 0:
        return error_response("limit must be positive")

    # ------------------------------------------------------------------
    # Path validation and security checks
    # ------------------------------------------------------------------

    # path is pre-validated by Pydantic (min_length=1)
    # Normalize path separators for cross-platform compatibility
    # This handles cases where LLM generates mixed separators (e.g., C:\path/to/file)

    # Keep original path for LLM-friendly error messages (forward slashes)
    original_path_for_display = path_to_llm_format(path.strip())
    path = normalize_path_separators(path.strip())

    # Get workspace root dynamically based on current session
    workspace_root = await get_workspace_root_async(context)

    # Validate file path against dynamic workspace
    abs_file_path = validate_path_in_workspace(path, workspace_root)
    if abs_file_path is None:
        return error_response(f"File path is outside workspace: {original_path_for_display}")

    try:
        file_path = Path(abs_file_path)

        # Check file existence and type
        if not file_path.exists():
            return error_response(f"File does not exist: {original_path_for_display}")

        if not file_path.is_file():
            # Provide more helpful error message for directories
            if file_path.is_dir():
                return error_response(f"Cannot read directory (use glob tool to list files): {original_path_for_display}")
            else:
                return error_response(f"Path is not a regular file: {original_path_for_display}")
        
        # Check file size
        file_size = file_path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            return error_response(f"File too large: {file_size // 1024 // 1024}MB exceeds {MAX_FILE_SIZE_BYTES // 1024 // 1024}MB limit")
        
        # Security checks (use dynamic workspace root for consistency)
        if file_path.is_symlink() and not is_safe_symlink(file_path, workspace_root):
            return error_response("Cannot read unsafe symlink pointing outside workspace")

        if not check_parent_symlinks(file_path, workspace_root):
            return error_response("Cannot read file with unsafe parent symlinks")

        # ------------------------------------------------------------------
        # File reading and analysis
        # ------------------------------------------------------------------

        # Read file with automatic type detection (using shared utility)
        processing_result = read_file_safely(
            file_path=file_path,
            offset=offset,
            limit=limit,
        )

        # Extract file type and encoding from processing result
        file_type = processing_result.file_type
        encoding = processing_result.encoding

        # Build user-facing message
        if processing_result.truncated:
            message = f"Read {file_type.value} file: {file_path.name} (lines {processing_result.lines_shown[0]}-{processing_result.lines_shown[1]})"
        else:
            # For text files, calculate lines from the range shown
            if processing_result.content_format == ContentFormat.TEXT:
                lines = processing_result.lines_shown[1] - processing_result.lines_shown[0] + 1
                message = f"Read {file_type.value} file: {file_path.name} ({lines} lines)"
            else:
                message = f"Read {file_type.value} file: {file_path.name} (0 lines)"

        # Build structured LLM content with unified parts format
        # Use absolute path with forward slashes for LLM consistency (matches Claude Code)
        abs_display = path_to_llm_format(file_path)

        # Handle METADATA format (validation errors: empty file, invalid image, etc.)
        if processing_result.content_format == ContentFormat.METADATA:
            error_msg = processing_result.content if isinstance(processing_result.content, str) else str(processing_result.content)
            return error_response(
                error_msg,
                file_path=abs_display,
                file_type=file_type.value,
                validation_error=True
            )

        # Build parts array for unified content structure
        parts = []

        if processing_result.content_format == ContentFormat.INLINE_DATA:
            # For binary/multimodal files (images, etc.)
            if isinstance(processing_result.content, dict) and "inline_data" in processing_result.content:
                inline_data = processing_result.content["inline_data"]

                # Check if current LLM provider supports multimodal
                supports_multimodal = get_multimodal_support_for_session(context.client_id or "")

                if not supports_multimodal:
                    # Graceful degradation: return simple error for LLM
                    file_size_kb = processing_result.original_size / 1024

                    # Simple error message for LLM (no backend implementation details)
                    error_message = (
                        f"Cannot read {file_type.value} file: {file_path.name}\n"
                        f"File type: {inline_data.get('mime_type', 'unknown')}\n"
                        f"File size: {file_size_kb:.2f} KB\n\n"
                        f"This file type requires multimodal support, which is not currently available.\n"
                        f"Only text files can be read."
                    )

                    logger.info(f"Multimodal not supported - returning error for {abs_display}")

                    return error_response(
                        error_message,
                        file_path=abs_display,
                        file_type=file_type.value,
                        multimodal_required=True
                    )

                # Multimodal supported: add inline_data part
                parts.append({
                    "type": "inline_data",
                    "mime_type": inline_data["mime_type"],
                    "data": inline_data["data"]
                })
        else:
            # For text files, add content as text part
            parts.append({
                "type": "text",
                "text": processing_result.content
            })

        return success_response(
            message,
            llm_content={"parts": parts},
            file_path=abs_display,
            file_type=file_type.value,
            encoding=encoding,
            truncated=processing_result.truncated,
            lines_shown=processing_result.lines_shown,
        )

    except Exception as exc:
        return error_response(f"Unexpected error reading file: {exc}")

# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_read_tool(mcp: FastMCP):
    """Register the read tool with proper tags synchronization."""
    mcp.tool(
        tags={"coding", "filesystem", "read", "file", "content", "analysis", "metadata"}, 
        annotations={"category": "coding", "tags": ["coding", "filesystem", "read", "file", "content", "analysis", "metadata"]}
    )(read) 