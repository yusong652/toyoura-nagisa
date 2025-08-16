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
from backend.infrastructure.mcp.utils.tool_result import ToolResult

__all__ = ["read_file", "register_read_file_tool"]

# -----------------------------------------------------------------------------
# Constants and file limits
# -----------------------------------------------------------------------------

# File size limits
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB maximum file size
LARGE_FILE_THRESHOLD = 10 * 1024 * 1024  # 10MB considered large
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

DOCUMENT_EXTENSIONS = {
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.odt', '.ods', '.odp', '.rtf', '.pages', '.numbers', '.keynote'
}

BINARY_EXTENSIONS = {
    '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar',
    '.exe', '.dll', '.so', '.dylib', '.lib', '.a',
    '.class', '.jar', '.war', '.ear', '.apk', '.dex',
    '.o', '.obj', '.bin', '.dat', '.db', '.sqlite',
    '.pyc', '.pyo', '.wasm', '.node', '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a', '.opus',
    '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.dmg', '.iso'
}

# Encoding detection order
ENCODING_CANDIDATES = [
    'utf-8', 'utf-16', 'utf-32', 'ascii', 'latin-1', 'cp1252', 'iso-8859-1'
]

# -----------------------------------------------------------------------------
# Enums for type safety
# -----------------------------------------------------------------------------

class FileType(str, Enum):
    """File type categories."""
    TEXT = "text"
    BINARY = "binary"
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"
    ARCHIVE = "archive"
    UNKNOWN = "unknown"


class ContentFormat(str, Enum):
    """Content format options."""
    TEXT = "text"
    BASE64 = "base64"
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
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "content_format": self.content_format.value,
            "truncated": self.truncated,
            "truncation_reason": self.truncation_reason,
            "original_size": self.original_size,
            "processed_size": self.processed_size,
            "lines_shown": list(self.lines_shown),
        }

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
    elif ext in DOCUMENT_EXTENSIONS:
        return FileType.DOCUMENT
    elif ext in BINARY_EXTENSIONS:
        return FileType.BINARY
    
    # Content-based detection for unknown extensions
    try:
        with file_path.open('rb') as f:
            sample = f.read(SAMPLE_SIZE_BINARY)
        
        # Check for null bytes (binary indicator)
        if b'\x00' in sample:
            return FileType.BINARY
        
        # Try to decode as text
        try:
            sample.decode('utf-8')
            return FileType.TEXT
        except UnicodeDecodeError:
            return FileType.BINARY
            
    except Exception:
        return FileType.UNKNOWN

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
            return 'utf-16-le', has_bom
        elif raw_data.startswith(b'\xfe\xff'):
            has_bom = True
            return 'utf-16-be', has_bom
        
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
    """Read and process text content with simple truncation."""
    try:
        with file_path.open('r', encoding=encoding, errors='replace') as f:
            content = f.read()
        
        lines = content.splitlines()
        total_lines = len(lines)
        
        # Apply offset and limit
        start_line = offset or 0
        end_line = min(start_line + (limit or DEFAULT_MAX_LINES), total_lines) if limit else total_lines
        
        selected_lines = lines[start_line:end_line]
        
        # Process lines with length limits
        processed_lines = []
        for line in selected_lines:
            if len(line) > MAX_LINE_LENGTH:
                processed_lines.append(line[:MAX_LINE_LENGTH] + "... [line truncated]")
            else:
                processed_lines.append(line)
        
        result_content = '\n'.join(processed_lines)
        truncated = end_line < total_lines
        
        if truncated:
            result_content = f"[Showing lines {start_line + 1}-{end_line} of {total_lines} total]\n" + result_content
        
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

def read_file(
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
- Results are returned using cat -n format, with line numbers starting at 1
- This tool allows you to read images (eg PNG, JPG, etc). When reading an image file the contents are presented visually as you are a multimodal LLM.
- This tool can read PDF files (.pdf). PDFs are processed page by page, extracting both text and visual content for analysis.
- This tool can read Jupyter notebooks (.ipynb files) and returns all cells with their outputs, combining code, text, and visualizations.
- You have the capability to call multiple tools in a single response. It is always better to speculatively read multiple files as a batch that are potentially useful.
- You will regularly be asked to read screenshots. If the user provides a path to a screenshot ALWAYS use this tool to view the file at the path. This tool will work with all temporary file paths like /var/folders/123/abc/T/TemporaryItems/NSIRD_screencaptureui_ZfB1tD/Screenshot.png
- If you read a file that exists but has empty contents you will receive a system reminder warning in place of file contents."""

    # ------------------------------------------------------------------
    # Parameter validation and normalization
    # ------------------------------------------------------------------

    # Handle Pydantic FieldInfo objects when invoked programmatically
    if isinstance(offset, FieldInfo):
        offset = None
    if isinstance(limit, FieldInfo):
        limit = None

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

    # Validate parameters
    if offset is not None and offset < 0:
        return _error("offset must be non-negative")
    
    if limit is not None and limit <= 0:
        return _error("limit must be positive")

    # Validate workspace access
    if not validate_path_in_workspace("."):
        return _error("Cannot access workspace directory")

    # ------------------------------------------------------------------
    # Path validation and security checks
    # ------------------------------------------------------------------

    # Validate file path
    abs_file_path = validate_path_in_workspace(path)
    if abs_file_path is None:
        return _error(f"File path is outside workspace: {path}")

    try:
        file_path = Path(abs_file_path)
        
        # Check file existence and type
        if not file_path.exists():
            return _error(f"File does not exist: {path}")
        
        if not file_path.is_file():
            return _error(f"Path is not a file: {path}")
        
        # Check file size
        file_size = file_path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            return _error(f"File too large: {file_size // 1024 // 1024}MB exceeds {MAX_FILE_SIZE_BYTES // 1024 // 1024}MB limit")
        
        # Security checks
        if file_path.is_symlink() and not is_safe_symlink(file_path):
            return _error("Cannot read unsafe symlink pointing outside workspace")
        
        if not check_parent_symlinks(file_path):
            return _error("Cannot read file with unsafe parent symlinks")

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
            lines = len(processing_result.content.splitlines()) if isinstance(processing_result.content, str) else 0
            message = f"Read {file_type.value} file: {file_path.name} ({lines} lines)"

        # Build structured LLM content
        rel_display = file_path.relative_to(WORKSPACE_ROOT) if str(file_path).startswith(str(WORKSPACE_ROOT)) else Path(path)
        
        # Handle content based on file type and ensure llm_content is always a dict
        if processing_result.content_format == ContentFormat.INLINE_DATA:
            # For binary files, return the inline_data structure directly for multimodal LLM
            if isinstance(processing_result.content, dict):
                llm_content = processing_result.content
            else:
                llm_content = {"content": processing_result.content}
        else:
            # For text files, wrap content in a dictionary structure
            llm_content = {"content": processing_result.content}

        return _success(
            message,
            llm_content,
            file_path=str(rel_display),
            file_type=file_type.value,
            encoding=encoding,
            truncated=processing_result.truncated,
            lines_shown=processing_result.lines_shown,
        )

    except Exception as exc:
        return _error(f"Unexpected error reading file: {exc}")

# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_read_file_tool(mcp: FastMCP):
    """Register the read_file tool with proper tags synchronization."""
    common = dict(
        tags={"coding", "filesystem", "read", "file", "content", "analysis", "metadata"}, 
        annotations={"category": "coding", "tags": ["coding", "filesystem", "read", "file", "content", "analysis", "metadata"]}
    )
    mcp.tool(**common)(read_file) 