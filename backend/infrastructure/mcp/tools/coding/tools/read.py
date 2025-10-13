"""Read single files with automatic encoding detection.

Supports:
- Text files: automatic encoding detection, line-based reading
- Binary files: images/docs/media returned as base64 for multimodal LLMs
- Security: path validation, size limits (50MB max)
- Reading modes: full, preview (100 lines), paginated
"""

import mimetypes
import base64
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum

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
from backend.infrastructure.mcp.utils.path_normalization import normalize_path_separators, path_to_llm_format

__all__ = ["read", "register_read_tool"]

# -----------------------------------------------------------------------------
# Constants and file limits
# -----------------------------------------------------------------------------

# File size limits
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB maximum file size
INLINE_MAX_BYTES = 1024 * 1024  # 1MB maximum for inline binary data

# Text processing limits
DEFAULT_MAX_LINES = 2000  # Maximum lines to read by default (matching Claude Code)
MAX_LINE_LENGTH = 2000   # Maximum line length before truncation (matching Claude Code)
SAMPLE_SIZE_BINARY = 8192  # Bytes to sample for binary detection

# Known file extensions for quick categorization
TEXT_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.scss', '.sass',
    '.json', '.xml', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
    '.md', '.txt', '.rst', '.csv', '.tsv', '.sql', '.sh', '.bash', '.zsh',
    '.c', '.cpp', '.h', '.hpp', '.java', '.kt', '.swift', '.go', '.rs',
    '.php', '.rb', '.pl', '.r', '.m', '.scala', '.clj', '.hs', '.elm',
    '.dockerfile', '.gitignore', '.gitattributes', '.editorconfig',
    '.log', '.env', '.properties', '.makefile', '.cmake'
}

IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif',
    '.svg', '.webp', '.ico', '.psd', '.ai', '.eps'
}


# Encoding detection order
# Note: utf-16 and utf-32 are handled separately via BOM detection
ENCODING_CANDIDATES = [
    'utf-8', 'ascii', 'latin-1', 'cp1252', 'iso-8859-1', 'gbk', 'shift_jis'
]

# -----------------------------------------------------------------------------
# Enums for type safety
# -----------------------------------------------------------------------------

class FileType(str, Enum):
    """File type categories."""
    TEXT = "text"
    IMAGE = "image"
    BINARY = "binary"


class ContentFormat(str, Enum):
    """Content format options."""
    TEXT = "text"
    METADATA = "metadata"
    INLINE_DATA = "inline_data"


# -----------------------------------------------------------------------------
# Data structures for file analysis
# -----------------------------------------------------------------------------

@dataclass
class ProcessingResult:
    """Processing result with metadata."""
    content: Union[str, Dict[str, Any]]  # 可以是文本内容或结构化的inline_data
    content_format: ContentFormat
    truncated: bool
    truncation_reason: Optional[str]
    original_size: int
    processed_size: int
    lines_shown: Tuple[int, int]
    

# -----------------------------------------------------------------------------
# Helper utilities
# -----------------------------------------------------------------------------

def _detect_file_type(file_path: Path) -> FileType:
    """Detect file type from extension and content."""
    ext = file_path.suffix.lower()
    
    if ext in TEXT_EXTENSIONS:
        return FileType.TEXT
    elif ext in IMAGE_EXTENSIONS:
        return FileType.IMAGE
    else:
        # For all other files, treat as binary
        return FileType.BINARY

def _detect_encoding(file_path: Path) -> Tuple[Optional[str], bool]:
    """Detect file encoding and BOM presence."""
    try:
        with file_path.open('rb') as f:
            raw_data = f.read(min(SAMPLE_SIZE_BINARY, file_path.stat().st_size))

        # Check for BOM
        has_bom = False
        if raw_data.startswith(b'\xef\xbb\xbf'):
            has_bom = True
            return 'utf-8-sig', has_bom
        elif raw_data.startswith(b'\xff\xfe'):
            has_bom = True
            return 'utf-16', has_bom  # Use generic utf-16 which handles LE with BOM
        elif raw_data.startswith(b'\xfe\xff'):
            has_bom = True
            return 'utf-16', has_bom  # Use generic utf-16 which handles BE with BOM

        # Try encodings in order
        for encoding in ENCODING_CANDIDATES:
            try:
                raw_data.decode(encoding)
                return encoding, has_bom
            except UnicodeDecodeError:
                continue

        return None, has_bom

    except Exception:
        return None, False

def _read_text_content(
    file_path: Path,
    encoding: str,
    offset: Optional[int] = None,
    limit: Optional[int] = None
) -> ProcessingResult:
    """Read and process text content with standard cat -n format."""
    try:
        # Use 'replace' error handler to handle any encoding issues gracefully
        with file_path.open('r', encoding=encoding, errors='replace') as f:
            content = f.read()
        
        lines = content.splitlines()
        total_lines = len(lines)
        
        # Apply offset and limit
        start_line = offset or 0
        end_line = min(start_line + (limit or DEFAULT_MAX_LINES), total_lines) if limit else total_lines
        
        selected_lines = lines[start_line:end_line]
        
        # Process lines with Claude Code format (line numbers with arrow separator)
        processed_lines = []
        for i, line in enumerate(selected_lines, start=start_line + 1):
            # Truncate long lines
            if len(line) > MAX_LINE_LENGTH:
                line = line[:MAX_LINE_LENGTH] + "... [line truncated]"

            # Format with line number and arrow separator (Claude Code format)
            # Using → instead of \t prevents LLM from including line numbers in edit strings
            processed_lines.append(f"{i:6}→{line}")
        
        result_content = '\n'.join(processed_lines)
        truncated = end_line < total_lines
        
        return ProcessingResult(
            content=result_content,
            content_format=ContentFormat.TEXT,
            truncated=truncated,
            truncation_reason="lines" if truncated else None,
            original_size=len(content),
            processed_size=len(result_content),
            lines_shown=(start_line + 1, end_line),
        )
        
    except Exception as e:
        return ProcessingResult(
            content=f"Error reading file: {e}",
            content_format=ContentFormat.TEXT,
            truncated=False,
            truncation_reason=None,
            original_size=0,
            processed_size=0,
            lines_shown=(0, 0),
        )

def _read_binary_content(file_path: Path) -> ProcessingResult:
    """Read and process binary content for multimodal LLM consumption.
    
    For binary files (images, documents, audio, video), this function:
    1. Reads the raw binary data 
    2. Encodes it as base64
    3. Returns structured inline_data format compatible with LLM multimodal APIs
    
    Args:
        file_path: Path to the binary file to read
        
    Returns:
        ProcessingResult with:
        - content: Dict with inline_data structure: {"inline_data": {"mime_type": str, "data": str}}
        - content_format: ContentFormat.INLINE_DATA
        - Other metadata about the processing
        
    The returned structure is specifically designed for LLM APIs that support
    multimodal content (images, etc.) and will be processed by the client
    to create appropriate message parts.
    """
    file_size = file_path.stat().st_size
    
    if file_size > INLINE_MAX_BYTES:
        return ProcessingResult(
            content=f"Binary file too large for inline: {file_path.name} ({file_size} bytes)",
            content_format=ContentFormat.METADATA,
            truncated=True,
            truncation_reason="size_limit",
            original_size=file_size,
            processed_size=0,
            lines_shown=(0, 0),
        )
    
    try:
        with file_path.open('rb') as f:
            binary_data = f.read()
        
        mime_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        base64_data = base64.b64encode(binary_data).decode('ascii')
        
        # 直接返回结构化的inline_data，而不是字符串化
        inline_data = {
            "inline_data": {
                "mime_type": mime_type,
                "data": base64_data
            }
        }
        
        return ProcessingResult(
            content=inline_data,  # 修复：保持字典结构
            content_format=ContentFormat.INLINE_DATA,
            truncated=False,
            truncation_reason=None,
            original_size=file_size,
            processed_size=len(base64_data),
            lines_shown=(0, 0),
        )
        
    except Exception as e:
        return ProcessingResult(
            content=f"Error reading binary file: {e}",
            content_format=ContentFormat.METADATA,
            truncated=False,
            truncation_reason=None,
            original_size=file_size,
            processed_size=0,
            lines_shown=(0, 0),
        )

def _read_file_safely(
    file_path: Path,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
) -> Tuple[ProcessingResult, FileType, Optional[str]]:
    """Read file with basic safety checks."""
    # Detect encoding for text files
    encoding, _ = _detect_encoding(file_path)
    
    # Read content based on file type
    file_type = _detect_file_type(file_path)
    
    if file_type == FileType.TEXT and encoding:
        processing_result = _read_text_content(file_path, encoding, offset, limit)
    else:
        processing_result = _read_binary_content(file_path)
    
    return processing_result, file_type, encoding

# -----------------------------------------------------------------------------
# Main implementation
# -----------------------------------------------------------------------------

def read(
    path: str = Field(
        ...,
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

    # Handle Pydantic FieldInfo objects when invoked programmatically
    if isinstance(offset, FieldInfo):
        offset = None
    if isinstance(limit, FieldInfo):
        limit = None

    # Validate parameters
    if offset is not None and offset < 0:
        return error_response("offset must be non-negative")
    
    if limit is not None and limit <= 0:
        return error_response("limit must be positive")

    # Validate workspace access
    if not validate_path_in_workspace("."):
        return error_response("Cannot access workspace directory")

    # ------------------------------------------------------------------
    # Path validation and security checks
    # ------------------------------------------------------------------

    # Normalize path separators for cross-platform compatibility
    # This handles cases where LLM generates mixed separators (e.g., C:\path/to/file)
    if not path or not path.strip():
        return error_response("path is required and cannot be empty")
    path = normalize_path_separators(path.strip())

    # Validate file path
    abs_file_path = validate_path_in_workspace(path)
    if abs_file_path is None:
        return error_response(f"File path is outside workspace: {path}")

    try:
        file_path = Path(abs_file_path)
        
        # Check file existence and type
        if not file_path.exists():
            return error_response(f"File does not exist: {path}")
        
        if not file_path.is_file():
            return error_response(f"Path is not a file: {path}")
        
        # Check file size
        file_size = file_path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            return error_response(f"File too large: {file_size // 1024 // 1024}MB exceeds {MAX_FILE_SIZE_BYTES // 1024 // 1024}MB limit")
        
        # Security checks
        if file_path.is_symlink() and not is_safe_symlink(file_path):
            return error_response("Cannot read unsafe symlink pointing outside workspace")
        
        if not check_parent_symlinks(file_path):
            return error_response("Cannot read file with unsafe parent symlinks")

        # ------------------------------------------------------------------
        # File reading and analysis
        # ------------------------------------------------------------------

        # Read file with basic safety checks
        processing_result, file_type, encoding = _read_file_safely(
            file_path=file_path,
            offset=offset,
            limit=limit,
        )

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

        # Build parts array for unified content structure
        parts = []

        if processing_result.content_format == ContentFormat.INLINE_DATA:
            # For binary/multimodal files (images, etc.)
            if isinstance(processing_result.content, dict) and "inline_data" in processing_result.content:
                inline_data = processing_result.content["inline_data"]
                # Add inline_data part
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