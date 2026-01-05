"""
Shared file reading utilities for coding tools.

This module provides common file reading functionality used by:
- read.py: Interactive file reading tool
- file_mention_processor.py: File mention content injection

Supports:
- Text files: automatic encoding detection, line-based reading
- Binary files: images/docs/media returned as base64 for multimodal LLMs
- Security: path validation, size limits (50MB max)
- Reading modes: full, preview (100 lines), paginated
"""

import mimetypes
import base64
from pathlib import Path
from typing import Optional, Tuple, Union, Dict, Any
from dataclasses import dataclass
from enum import Enum


# -----------------------------------------------------------------------------
# Constants and file limits (matching read.py)
# -----------------------------------------------------------------------------

# File size limits
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB maximum file size
INLINE_MAX_BYTES = 1024 * 1024  # 1MB maximum for inline binary data

# Text processing limits
DEFAULT_MAX_LINES = 2000  # Maximum lines to read by default (matching Claude Code)
MAX_LINE_LENGTH = 2000   # Maximum line length before truncation (matching Claude Code)
SAMPLE_SIZE_BINARY = 8192  # Bytes to sample for binary detection

# -----------------------------------------------------------------------------
# Magic Bytes Signatures for Image Validation
# -----------------------------------------------------------------------------

# Magic bytes signatures for common image formats
# Reference: https://en.wikipedia.org/wiki/List_of_file_signatures
IMAGE_MAGIC_BYTES = {
    "png": b'\x89PNG\r\n\x1a\n',         # 8-byte PNG signature
    "jpeg": b'\xff\xd8\xff',              # 3-byte JPEG start
    "gif": b'GIF8',                       # GIF87a or GIF89a
    "webp": (b'RIFF', b'WEBP'),           # RIFF at 0, WEBP at offset 8
    "bmp": b'BM',                         # 2-byte BMP signature
    "tiff": (b'II\x2a\x00', b'MM\x00\x2a'),  # Little/Big-endian
    "ico": b'\x00\x00\x01\x00',           # Windows icon
    "psd": b'8BPS',                       # Photoshop PSD
}

# Extensions that map to magic byte checks
EXTENSION_TO_MAGIC = {
    '.png': 'png',
    '.jpg': 'jpeg',
    '.jpeg': 'jpeg',
    '.gif': 'gif',
    '.webp': 'webp',
    '.bmp': 'bmp',
    '.tiff': 'tiff',
    '.tif': 'tiff',
    '.ico': 'ico',
    '.psd': 'psd',
}

# Maximum bytes to read for magic validation
MAGIC_BYTES_READ_SIZE = 12  # WebP needs 12 bytes for full validation

# -----------------------------------------------------------------------------
# Known file extensions for quick categorization
# -----------------------------------------------------------------------------

TEXT_EXTENSIONS = {
    # Programming languages
    '.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.scss', '.sass',
    '.c', '.cpp', '.h', '.hpp', '.java', '.kt', '.swift', '.go', '.rs',
    '.php', '.rb', '.pl', '.r', '.m', '.scala', '.clj', '.hs', '.elm',
    # Data/config formats
    '.json', '.xml', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
    '.csv', '.tsv', '.sql', '.log', '.env', '.properties',
    # Documentation
    '.md', '.txt', '.rst',
    # Shell/build
    '.sh', '.bash', '.zsh', '.dockerfile', '.makefile', '.cmake',
    # Dotfiles
    '.gitignore', '.gitattributes', '.editorconfig',
    # Text-based image formats (XML/PostScript)
    '.svg', '.eps',
}

IMAGE_EXTENSIONS = {
    # Binary image formats (multimodal LLM compatible)
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif',
    '.webp', '.ico',
    # Proprietary formats (no magic bytes validation, best-effort)
    '.psd', '.ai',
}

# Encoding detection order
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
    content: Union[str, Dict[str, Any]]  # Text content or structured inline_data
    content_format: ContentFormat
    truncated: bool
    truncation_reason: Optional[str]
    original_size: int
    processed_size: int
    lines_shown: Tuple[int, int]
    file_type: FileType
    encoding: Optional[str]


# -----------------------------------------------------------------------------
# Helper utilities
# -----------------------------------------------------------------------------

def _detect_file_type(file_path: Path) -> FileType:
    """Detect file type from extension and content."""
    ext = file_path.suffix.lower()

    # Special handling for dotfiles (e.g., .gitignore, .env)
    if not ext and file_path.name.startswith('.'):
        full_name = file_path.name.lower()
        if full_name in TEXT_EXTENSIONS:
            return FileType.TEXT

    if ext in TEXT_EXTENSIONS:
        return FileType.TEXT
    elif ext in IMAGE_EXTENSIONS:
        return FileType.IMAGE
    else:
        # For all other files, treat as binary
        return FileType.BINARY


def detect_encoding(file_path: Path) -> Optional[str]:
    """
    Detect file encoding with BOM detection.

    Args:
        file_path: Path to file

    Returns:
        Detected encoding or None
    """
    try:
        with file_path.open('rb') as f:
            raw_data = f.read(min(SAMPLE_SIZE_BINARY, file_path.stat().st_size))

        # Check for BOM
        if raw_data.startswith(b'\xef\xbb\xbf'):
            return 'utf-8-sig'
        elif raw_data.startswith(b'\xff\xfe') or raw_data.startswith(b'\xfe\xff'):
            return 'utf-16'

        # Try encodings in order
        for encoding in ENCODING_CANDIDATES:
            try:
                raw_data.decode(encoding)
                return encoding
            except UnicodeDecodeError:
                continue

        return None

    except Exception:
        return None


# -----------------------------------------------------------------------------
# Validation utilities for robust file handling
# -----------------------------------------------------------------------------

def _check_empty_file(file_path: Path, file_size: int) -> Optional[ProcessingResult]:
    """
    Check if file is empty (0 bytes) and return appropriate result.

    Args:
        file_path: Path to the file
        file_size: File size in bytes (pre-computed to avoid double stat)

    Returns:
        ProcessingResult with METADATA format if empty, None otherwise
    """
    if file_size == 0:
        return ProcessingResult(
            content=f"File is empty (0 bytes): {file_path.name}",
            content_format=ContentFormat.METADATA,
            truncated=False,
            truncation_reason=None,
            original_size=0,
            processed_size=0,
            lines_shown=(0, 0),
            file_type=_detect_file_type(file_path),
            encoding=None
        )
    return None


def _validate_image_magic_bytes(file_path: Path, file_size: int) -> Tuple[bool, Optional[str]]:
    """
    Validate image file has correct magic bytes signature.

    This prevents LLM API errors when files have image extensions but
    non-image content (e.g., JSON saved as .png).

    Args:
        file_path: Path to the image file
        file_size: File size in bytes (reserved for future validation)

    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if valid image or no validation needed
        - (False, "reason") if invalid
    """
    _ = file_size  # Reserved for potential future size-based validation
    ext = file_path.suffix.lower()

    # Check if extension requires magic byte validation
    if ext not in EXTENSION_TO_MAGIC:
        # No magic validation for this extension (AI has complex/variable format)
        return True, None

    magic_type = EXTENSION_TO_MAGIC[ext]
    expected = IMAGE_MAGIC_BYTES.get(magic_type)

    if expected is None:
        return True, None

    # Note: Even for small files (< MAGIC_BYTES_READ_SIZE), we still attempt
    # validation with whatever bytes are available

    try:
        with file_path.open('rb') as f:
            header = f.read(MAGIC_BYTES_READ_SIZE)

        # Handle WebP special case (RIFF at start, WEBP at offset 8)
        if magic_type == 'webp':
            riff_sig, webp_sig = expected
            if not (header.startswith(riff_sig) and len(header) >= 12 and header[8:12] == webp_sig):
                return False, f"Invalid WebP: expected RIFF...WEBP signature"
            return True, None

        # Handle TIFF dual format (little-endian or big-endian)
        if magic_type == 'tiff':
            le_sig, be_sig = expected
            if not (header.startswith(le_sig) or header.startswith(be_sig)):
                return False, f"Invalid TIFF: expected II or MM signature"
            return True, None

        # Standard single-signature check
        if not header.startswith(expected):
            return False, f"Invalid {ext.upper()}: magic bytes mismatch (expected {expected[:4]!r}, got {header[:4]!r})"

        return True, None

    except Exception as e:
        return False, f"Failed to read file header: {e}"


def _try_text_fallback(file_path: Path, original_error: str) -> Optional[ProcessingResult]:
    """
    Attempt to read a failed binary file as text.

    This provides graceful degradation for files with image extensions
    but text content (e.g., JSON saved as .png).

    Args:
        file_path: Path to the file
        original_error: Original error message to include in result

    Returns:
        ProcessingResult if text reading succeeded, None if it failed
    """
    try:
        encoding = detect_encoding(file_path)
        if encoding:
            result = _read_text_content(file_path, encoding)
            # Add note about fallback only if we got valid text content
            if isinstance(result.content, str) and result.content_format == ContentFormat.TEXT:
                fallback_note = f"[Note: {original_error}. Reading as text instead.]\n\n"
                return ProcessingResult(
                    content=fallback_note + result.content,
                    content_format=result.content_format,
                    truncated=result.truncated,
                    truncation_reason=result.truncation_reason,
                    original_size=result.original_size,
                    processed_size=result.processed_size + len(fallback_note),
                    lines_shown=result.lines_shown,
                    file_type=FileType.TEXT,  # Override to TEXT since we're reading as text
                    encoding=result.encoding
                )
    except Exception:
        pass
    return None


# -----------------------------------------------------------------------------
# Content reading functions
# -----------------------------------------------------------------------------

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

        # Apply offset and limit (always cap at DEFAULT_MAX_LINES if limit not specified)
        start_line = offset or 0
        max_lines = limit if limit is not None else DEFAULT_MAX_LINES
        end_line = min(start_line + max_lines, total_lines)

        selected_lines = lines[start_line:end_line]

        # Process lines with Claude Code format (line numbers with arrow separator)
        processed_lines = []
        for i, line in enumerate(selected_lines, start=start_line + 1):
            # Truncate long lines
            if len(line) > MAX_LINE_LENGTH:
                line = line[:MAX_LINE_LENGTH] + "... [line truncated]"

            # Format with line number and arrow separator (Claude Code format)
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
            file_type=FileType.TEXT,
            encoding=encoding
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
            file_type=FileType.TEXT,
            encoding=encoding
        )


def _read_binary_content(file_path: Path) -> ProcessingResult:
    """
    Read and process binary content for multimodal LLM consumption.

    For binary files (images, documents, audio, video), this function:
    1. Validates the file (empty check, magic bytes for images)
    2. Reads the raw binary data
    3. Encodes it as base64
    4. Returns structured inline_data format compatible with LLM multimodal APIs

    For invalid image files (wrong content type), attempts graceful fallback
    to text reading.

    Args:
        file_path: Path to the binary file to read

    Returns:
        ProcessingResult with:
        - content: Dict with inline_data structure
        - content_format: ContentFormat.INLINE_DATA
        - Other metadata about the processing
    """
    file_size = file_path.stat().st_size

    # Check for empty file first
    empty_result = _check_empty_file(file_path, file_size)
    if empty_result:
        return empty_result

    if file_size > INLINE_MAX_BYTES:
        return ProcessingResult(
            content=f"Binary file too large for inline: {file_path.name} ({file_size} bytes)",
            content_format=ContentFormat.METADATA,
            truncated=True,
            truncation_reason="size_limit",
            original_size=file_size,
            processed_size=0,
            lines_shown=(0, 0),
            file_type=_detect_file_type(file_path),
            encoding=None
        )

    # Validate magic bytes for image files to prevent LLM API errors
    file_type = _detect_file_type(file_path)
    if file_type == FileType.IMAGE:
        is_valid, error_msg = _validate_image_magic_bytes(file_path, file_size)
        if not is_valid:
            # Try text fallback for files with image extension but text content
            fallback_result = _try_text_fallback(file_path, error_msg or "Invalid image")
            if fallback_result:
                return fallback_result
            # If text fallback fails, return metadata error
            return ProcessingResult(
                content=f"Invalid image file: {error_msg}. Cannot read as text either.",
                content_format=ContentFormat.METADATA,
                truncated=False,
                truncation_reason=None,
                original_size=file_size,
                processed_size=0,
                lines_shown=(0, 0),
                file_type=file_type,
                encoding=None
            )

    try:
        with file_path.open('rb') as f:
            binary_data = f.read()

        mime_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        base64_data = base64.b64encode(binary_data).decode('ascii')

        # Return structured inline_data (not stringified)
        inline_data = {
            "inline_data": {
                "mime_type": mime_type,
                "data": base64_data
            }
        }

        return ProcessingResult(
            content=inline_data,
            content_format=ContentFormat.INLINE_DATA,
            truncated=False,
            truncation_reason=None,
            original_size=file_size,
            processed_size=len(base64_data),
            lines_shown=(0, 0),
            file_type=_detect_file_type(file_path),
            encoding=None
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
            file_type=_detect_file_type(file_path),
            encoding=None
        )


def read_file_safely(
    file_path: Path,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
) -> ProcessingResult:
    """
    Read file with automatic type detection and appropriate processing.

    This is the main entry point for file reading, used by both the read tool
    and file mention processor.

    Includes validation for:
    - Empty files (0 bytes)
    - Invalid image files (magic bytes mismatch)

    Args:
        file_path: Path to the file to read
        offset: Starting line number for text files (0-indexed)
        limit: Maximum number of lines to read for text files

    Returns:
        ProcessingResult with content and metadata
    """
    # Get file size early for validation
    try:
        file_size = file_path.stat().st_size
    except OSError as e:
        return ProcessingResult(
            content=f"Cannot access file: {e}",
            content_format=ContentFormat.METADATA,
            truncated=False,
            truncation_reason=None,
            original_size=0,
            processed_size=0,
            lines_shown=(0, 0),
            file_type=FileType.BINARY,
            encoding=None
        )

    # Check for empty file at entry point (handles all file types)
    empty_result = _check_empty_file(file_path, file_size)
    if empty_result:
        return empty_result

    # Detect file type
    file_type = _detect_file_type(file_path)

    if file_type == FileType.TEXT:
        # For TEXT files, detect encoding or fallback to UTF-8
        encoding = detect_encoding(file_path) or 'utf-8'
        return _read_text_content(file_path, encoding, offset, limit)
    else:
        # For IMAGE and BINARY files, read as binary with base64 encoding
        return _read_binary_content(file_path)


def read_text_file_with_line_numbers(
    file_path: Path,
    encoding: str,
    offset: Optional[int] = None,
    limit: Optional[int] = None
) -> str:
    """
    Read text file with Claude Code style line numbering.

    DEPRECATED: Use read_file_safely() instead for better type detection.
    Kept for backward compatibility.

    Format: "     1→content" (6-space padding + arrow separator)

    Args:
        file_path: Path to file
        encoding: Text encoding
        offset: Line number to start from (0-indexed)
        limit: Maximum number of lines to read

    Returns:
        Formatted content with line numbers
    """
    result = _read_text_content(file_path, encoding, offset, limit)
    return result.content if isinstance(result.content, str) else str(result.content)
