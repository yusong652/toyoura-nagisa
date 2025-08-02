"""Read single files with automatic encoding detection.

Supports:
- Text files: automatic encoding detection, line-based reading
- Binary files: images/docs/media returned as base64 for multimodal LLMs
- Security: path validation, size limits (50MB max)
- Reading modes: full, preview (100 lines), paginated
"""

import os
import time
import hashlib
import mimetypes
import base64
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
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
from .constants import (
    MAX_FILES_DEFAULT,
    TEXT_CHARSET_DEFAULT,
)

__all__ = ["read_file", "register_read_file_tool"]

# -----------------------------------------------------------------------------
# Constants and file limits
# -----------------------------------------------------------------------------

# File size limits
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB maximum file size
LARGE_FILE_THRESHOLD = 10 * 1024 * 1024  # 10MB considered large
INLINE_MAX_BYTES = 1024 * 1024  # 1MB maximum for inline binary data

# Text processing limits
DEFAULT_MAX_LINES = 5000  # Maximum lines to read by default
MAX_LINE_LENGTH = 5000   # Maximum line length before truncation
PREVIEW_LINES = 100      # Lines for preview mode
SAMPLE_SIZE_BINARY = 8192  # Bytes to sample for binary detection

# Content analysis limits
MAX_WORDS_COUNT = 100000  # Maximum words to count
MAX_ENCODING_ATTEMPTS = 5  # Maximum encoding attempts
HASH_CHUNK_SIZE = 8192   # Chunk size for file hashing

# Performance thresholds
PERFORMANCE_SLOW_THRESHOLD = 1.0  # seconds
PERFORMANCE_LARGE_THRESHOLD = 5.0  # seconds

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

BINARY_EXTENSIONS = {
    '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar',
    '.exe', '.dll', '.so', '.dylib', '.lib', '.a',
    '.class', '.jar', '.war', '.ear', '.apk', '.dex',
    '.o', '.obj', '.bin', '.dat', '.db', '.sqlite',
    '.pyc', '.pyo', '.wasm', '.node'
}

IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif',
    '.svg', '.webp', '.ico', '.psd', '.ai', '.eps'
}

DOCUMENT_EXTENSIONS = {
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.odt', '.ods', '.odp', '.rtf', '.pages', '.numbers', '.keynote'
}

AUDIO_EXTENSIONS = {
    '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a', '.opus'
}

VIDEO_EXTENSIONS = {
    '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'
}

ARCHIVE_EXTENSIONS = {
    '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar', '.dmg', '.iso'
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

class ReadMode(str, Enum):
    """Reading mode options."""
    FULL = "full"
    PREVIEW = "preview"
    PAGINATED = "paginated"
    METADATA_ONLY = "metadata_only"

class ContentFormat(str, Enum):
    """Content format options."""
    TEXT = "text"
    BASE64 = "base64"
    METADATA = "metadata"
    INLINE_DATA = "inline_data"

class SizeCategory(str, Enum):
    """File size categories."""
    TINY = "tiny"        # < 1KB
    SMALL = "small"      # 1KB - 100KB
    MEDIUM = "medium"    # 100KB - 1MB
    LARGE = "large"      # 1MB - 10MB
    HUGE = "huge"        # > 10MB

# -----------------------------------------------------------------------------
# Data structures for file analysis
# -----------------------------------------------------------------------------

@dataclass
class FileMetadata:
    """Comprehensive file metadata."""
    path: str
    size: int
    size_category: SizeCategory
    modified_time: datetime
    created_time: datetime
    permissions: str
    owner: str
    group: str
    is_symlink: bool
    is_executable: bool
    is_hidden: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "size": self.size,
            "size_category": self.size_category.value,
            "modified_time": self.modified_time.isoformat(),
            "created_time": self.created_time.isoformat(),
            "permissions": self.permissions,
            "owner": self.owner,
            "group": self.group,
            "is_symlink": self.is_symlink,
            "is_executable": self.is_executable,
            "is_hidden": self.is_hidden,
        }

@dataclass
class ContentAnalysis:
    """Content analysis results."""
    file_type: FileType
    mime_type: str
    encoding: Optional[str]
    line_count: int
    word_count: int
    character_count: int
    binary_ratio: float
    hash_sha256: str
    has_bom: bool
    detected_language: Optional[str]
    complexity_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_type": self.file_type.value,
            "mime_type": self.mime_type,
            "encoding": self.encoding,
            "line_count": self.line_count,
            "word_count": self.word_count,
            "character_count": self.character_count,
            "binary_ratio": self.binary_ratio,
            "hash_sha256": self.hash_sha256,
            "has_bom": self.has_bom,
            "detected_language": self.detected_language,
            "complexity_score": self.complexity_score,
        }

@dataclass
class ReadPerformance:
    """Reading performance metrics."""
    read_time: float
    analysis_time: float
    total_time: float
    bytes_per_second: float
    lines_per_second: float
    is_slow: bool
    cache_hit: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "read_time": self.read_time,
            "analysis_time": self.analysis_time,
            "total_time": self.total_time,
            "bytes_per_second": self.bytes_per_second,
            "lines_per_second": self.lines_per_second,
            "is_slow": self.is_slow,
            "cache_hit": self.cache_hit,
        }

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

class ReadResult:
    """Comprehensive read result with rich metadata."""
    
    def __init__(
        self,
        file_metadata: FileMetadata,
        content_analysis: ContentAnalysis,
        processing_result: ProcessingResult,
        performance: ReadPerformance,
        read_mode: ReadMode,
        warnings: Optional[List[str]] = None,
        error_message: Optional[str] = None,
    ):
        self.file_metadata = file_metadata
        self.content_analysis = content_analysis
        self.processing_result = processing_result
        self.performance = performance
        self.read_mode = read_mode
        self.warnings = warnings or []
        self.error_message = error_message
        self.timestamp = datetime.now().isoformat()
    
    @property
    def success(self) -> bool:
        """Check if read was successful."""
        return self.error_message is None
    
    @property
    def complexity_category(self) -> str:
        """Get complexity category."""
        score = self.content_analysis.complexity_score
        if score < 0.2:
            return "simple"
        elif score < 0.6:
            return "moderate"
        elif score < 0.8:
            return "complex"
        else:
            return "very_complex"
    
    def get_summary(self) -> Dict[str, Any]:
        """Get read summary statistics."""
        return {
            "read_status": "success" if self.success else "failed",
            "file_type": self.content_analysis.file_type.value,
            "size_category": self.file_metadata.size_category.value,
            "complexity_category": self.complexity_category,
            "read_mode": self.read_mode.value,
            "content_format": self.processing_result.content_format.value,
            "truncated": self.processing_result.truncated,
            "performance_category": "slow" if self.performance.is_slow else "fast",
            "has_warnings": len(self.warnings) > 0,
            "line_count": self.content_analysis.line_count,
            "word_count": self.content_analysis.word_count,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "file_metadata": self.file_metadata.to_dict(),
            "content_analysis": self.content_analysis.to_dict(),
            "processing_result": self.processing_result.to_dict(),
            "performance": self.performance.to_dict(),
            "read_metadata": {
                "read_mode": self.read_mode.value,
                "timestamp": self.timestamp,
                "warnings": self.warnings,
                "error_message": self.error_message,
            },
            "summary": self.get_summary(),
        }

# -----------------------------------------------------------------------------
# Helper utilities
# -----------------------------------------------------------------------------

def _get_size_category(size: int) -> SizeCategory:
    """Determine size category."""
    if size < 1024:
        return SizeCategory.TINY
    elif size < 100 * 1024:
        return SizeCategory.SMALL
    elif size < 1024 * 1024:
        return SizeCategory.MEDIUM
    elif size < 10 * 1024 * 1024:
        return SizeCategory.LARGE
    else:
        return SizeCategory.HUGE

def _analyze_file_metadata(file_path: Path) -> FileMetadata:
    """Analyze file metadata."""
    stat = file_path.stat()
    
    # Get file permissions
    permissions = oct(stat.st_mode)[-3:]
    
    # Get owner and group (with fallback)
    try:
        import pwd
        import grp
        owner = pwd.getpwuid(stat.st_uid).pw_name
        group = grp.getgrgid(stat.st_gid).gr_name
    except (ImportError, KeyError):
        owner = str(stat.st_uid)
        group = str(stat.st_gid)
    
    return FileMetadata(
        path=str(file_path),
        size=stat.st_size,
        size_category=_get_size_category(stat.st_size),
        modified_time=datetime.fromtimestamp(stat.st_mtime),
        created_time=datetime.fromtimestamp(stat.st_ctime),
        permissions=permissions,
        owner=owner,
        group=group,
        is_symlink=file_path.is_symlink(),
        is_executable=os.access(file_path, os.X_OK),
        is_hidden=file_path.name.startswith('.'),
    )

def _detect_file_type(file_path: Path) -> FileType:
    """Detect file type from extension and content."""
    ext = file_path.suffix.lower()
    
    if ext in TEXT_EXTENSIONS:
        return FileType.TEXT
    elif ext in IMAGE_EXTENSIONS:
        return FileType.IMAGE
    elif ext in DOCUMENT_EXTENSIONS:
        return FileType.DOCUMENT
    elif ext in AUDIO_EXTENSIONS:
        return FileType.AUDIO
    elif ext in VIDEO_EXTENSIONS:
        return FileType.VIDEO
    elif ext in ARCHIVE_EXTENSIONS:
        return FileType.ARCHIVE
    elif ext in BINARY_EXTENSIONS:
        return FileType.BINARY
    
    # Content-based detection
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

def _calculate_complexity_score(content: str) -> float:
    """Calculate content complexity score (0.0-1.0)."""
    if not content:
        return 0.0
    
    # Various complexity indicators
    lines = content.splitlines()
    line_count = len(lines)
    
    # Line length variance
    if line_count > 0:
        line_lengths = [len(line) for line in lines]
        avg_length = sum(line_lengths) / line_count
        variance = sum((length - avg_length) ** 2 for length in line_lengths) / line_count
        length_complexity = min(variance / 10000, 1.0)
    else:
        length_complexity = 0.0
    
    # Character diversity
    unique_chars = len(set(content))
    char_complexity = min(unique_chars / 256, 1.0)
    
    # Nested structure indicators
    nesting_chars = content.count('{') + content.count('[') + content.count('(')
    nesting_complexity = min(nesting_chars / max(len(content), 1) * 100, 1.0)
    
    # Combine scores
    return (length_complexity + char_complexity + nesting_complexity) / 3

def _detect_language(file_path: Path, content: str) -> Optional[str]:
    """Detect programming language from file extension and content."""
    ext = file_path.suffix.lower()
    
    # Extension-based detection
    lang_map = {
        '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
        '.java': 'java', '.c': 'c', '.cpp': 'c++', '.h': 'c',
        '.go': 'go', '.rs': 'rust', '.rb': 'ruby', '.php': 'php',
        '.swift': 'swift', '.kt': 'kotlin', '.scala': 'scala',
        '.html': 'html', '.css': 'css', '.scss': 'scss',
        '.json': 'json', '.xml': 'xml', '.yaml': 'yaml', '.yml': 'yaml',
        '.sql': 'sql', '.sh': 'bash', '.bash': 'bash',
        '.md': 'markdown', '.tex': 'latex', '.r': 'r',
    }
    
    if ext in lang_map:
        return lang_map[ext]
    
    # Content-based detection (simple heuristics)
    if content:
        content_lower = content.lower()[:1000]  # Sample first 1000 chars
        
        if 'def ' in content_lower or 'import ' in content_lower:
            return 'python'
        elif 'function' in content_lower or 'var ' in content_lower:
            return 'javascript'
        elif 'class ' in content_lower and 'public' in content_lower:
            return 'java'
        elif '#include' in content_lower:
            return 'c'
    
    return None

def _compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of file."""
    hash_sha256 = hashlib.sha256()
    
    try:
        with file_path.open('rb') as f:
            while chunk := f.read(HASH_CHUNK_SIZE):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception:
        return "unknown"

def _analyze_content(file_path: Path, content: str, encoding: Optional[str]) -> ContentAnalysis:
    """Analyze file content comprehensively."""
    file_type = _detect_file_type(file_path)
    mime_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    
    # Basic metrics
    line_count = len(content.splitlines()) if content else 0
    word_count = len(content.split()) if content else 0
    character_count = len(content)
    
    # Binary ratio (for text files)
    if content:
        binary_chars = sum(1 for c in content if ord(c) > 127 or c in '\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f')
        binary_ratio = binary_chars / len(content)
    else:
        binary_ratio = 0.0
    
    # File hash
    file_hash = _compute_file_hash(file_path)
    
    # BOM detection
    _, has_bom = _detect_encoding(file_path)
    
    # Language detection
    detected_language = _detect_language(file_path, content)
    
    # Complexity score
    complexity_score = _calculate_complexity_score(content)
    
    return ContentAnalysis(
        file_type=file_type,
        mime_type=mime_type,
        encoding=encoding,
        line_count=line_count,
        word_count=word_count,
        character_count=character_count,
        binary_ratio=binary_ratio,
        hash_sha256=file_hash,
        has_bom=has_bom,
        detected_language=detected_language,
        complexity_score=complexity_score,
    )

def _read_text_content(
    file_path: Path, 
    encoding: str, 
    offset: Optional[int] = None, 
    limit: Optional[int] = None,
    read_mode: ReadMode = ReadMode.FULL
) -> ProcessingResult:
    """Read and process text content with intelligent truncation."""
    start_time = time.time()
    
    try:
        with file_path.open('r', encoding=encoding, errors='replace') as f:
            content = f.read()
        
        original_size = len(content)
        lines = content.splitlines()
        total_lines = len(lines)
        
        # Determine effective reading parameters
        if read_mode == ReadMode.PREVIEW:
            effective_offset = 0
            effective_limit = PREVIEW_LINES
        elif read_mode == ReadMode.PAGINATED:
            effective_offset = offset or 0
            effective_limit = limit or DEFAULT_MAX_LINES
        else:  # FULL
            effective_offset = offset or 0
            effective_limit = limit or total_lines
        
        # Apply offset and limit
        start_line = max(0, min(effective_offset, total_lines))
        end_line = min(start_line + effective_limit, total_lines)
        
        selected_lines = lines[start_line:end_line]
        
        # Process lines with length limits
        processed_lines = []
        truncated_lines = 0
        
        for line in selected_lines:
            if len(line) > MAX_LINE_LENGTH:
                processed_lines.append(line[:MAX_LINE_LENGTH] + "... [line truncated]")
                truncated_lines += 1
            else:
                processed_lines.append(line)
        
        # Build final content
        result_content = '\n'.join(processed_lines)
        
        # Determine truncation status
        truncated = (end_line < total_lines) or (truncated_lines > 0)
        truncation_reason = None
        
        if end_line < total_lines and truncated_lines > 0:
            truncation_reason = "lines_and_content"
        elif end_line < total_lines:
            truncation_reason = "lines"
        elif truncated_lines > 0:
            truncation_reason = "content"
        
        # Add truncation header if needed
        if truncated:
            if read_mode == ReadMode.PREVIEW:
                header = f"[PREVIEW MODE: Showing first {len(selected_lines)} lines of {total_lines} total]\n"
            else:
                header = f"[TRUNCATED: Showing lines {start_line + 1}-{end_line} of {total_lines} total"
                if truncated_lines > 0:
                    header += f", {truncated_lines} lines had content truncated"
                header += "]\n"
            result_content = header + result_content
        
        return ProcessingResult(
            content=result_content,
            content_format=ContentFormat.TEXT,
            truncated=truncated,
            truncation_reason=truncation_reason,
            original_size=original_size,
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
    read_mode: ReadMode = ReadMode.FULL,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
) -> ReadResult:
    """Read file with comprehensive analysis and safety checks."""
    start_time = time.time()
    warnings = []
    
    # Analyze file metadata
    metadata_start = time.time()
    file_metadata = _analyze_file_metadata(file_path)
    metadata_time = time.time() - metadata_start
    
    # Detect encoding for text files
    encoding, has_bom = _detect_encoding(file_path)
    
    # Read content based on file type
    read_start = time.time()
    file_type = _detect_file_type(file_path)
    
    if file_type == FileType.TEXT and encoding:
        content = ""
        try:
            with file_path.open('r', encoding=encoding, errors='replace') as f:
                content = f.read()
        except Exception as e:
            warnings.append(f"Error reading text content: {e}")
        
        processing_result = _read_text_content(file_path, encoding, offset, limit, read_mode)
        
    elif file_type in [FileType.IMAGE, FileType.DOCUMENT, FileType.AUDIO, FileType.VIDEO]:
        content = ""
        processing_result = _read_binary_content(file_path)
        
    else:  # BINARY or UNKNOWN
        content = ""
        processing_result = _read_binary_content(file_path)
    
    read_time = time.time() - read_start
    
    # Content analysis
    analysis_start = time.time()
    content_analysis = _analyze_content(file_path, content, encoding)
    analysis_time = time.time() - analysis_start
    
    # Performance metrics
    total_time = time.time() - start_time
    file_size = file_metadata.size
    
    performance = ReadPerformance(
        read_time=read_time,
        analysis_time=analysis_time,
        total_time=total_time,
        bytes_per_second=file_size / max(read_time, 0.001),
        lines_per_second=content_analysis.line_count / max(read_time, 0.001),
        is_slow=total_time > PERFORMANCE_SLOW_THRESHOLD,
        cache_hit=False,  # No caching implemented yet
    )
    
    # Add performance warnings
    if performance.is_slow:
        warnings.append(f"File read took {total_time:.2f}s (considered slow)")
    
    if file_size > LARGE_FILE_THRESHOLD:
        warnings.append(f"Large file ({file_size // 1024 // 1024}MB) - consider using pagination")
    
    return ReadResult(
        file_metadata=file_metadata,
        content_analysis=content_analysis,
        processing_result=processing_result,
        performance=performance,
        read_mode=read_mode,
        warnings=warnings,
    )

# -----------------------------------------------------------------------------
# Main implementation
# -----------------------------------------------------------------------------

def read_file(
    path: str = Field(
        ...,
        description="File path to read.",
    ),
    read_mode: ReadMode = Field(
        ReadMode.FULL,
        description="Reading mode: 'full' (complete file), 'preview' (first 100 lines), 'paginated' (use offset/limit).",
    ),
    offset: Optional[int] = Field(
        None,
        description="Start line for paginated reading (0-based).",
    ),
    limit: Optional[int] = Field(
        None,
        description="Max lines to read.",
    ),
) -> Dict[str, Any]:
    """Read a single file.
    
    Supports text and binary files. Text files use automatic encoding detection.
    Binary files (images/docs) are returned as base64 for multimodal LLM processing.
    """

    # ------------------------------------------------------------------
    # Parameter validation and normalization
    # ------------------------------------------------------------------

    # Handle Pydantic FieldInfo objects when invoked programmatically
    if isinstance(read_mode, FieldInfo):
        read_mode = ReadMode.FULL
    if isinstance(offset, FieldInfo):
        offset = None
    if isinstance(limit, FieldInfo):
        limit = None
    
    # Set default values for removed parameters
    analyze_content = True
    include_metadata = True

    # Helper shortcuts for consistent results
    def _error(message: str, operation_type: str = "read_file", file_path: str = "") -> Dict[str, Any]:
        # Provide meaningful llm_content even for errors
        llm_content = {
            "operation": {
                "type": operation_type,
                "path": file_path,
                "success": False
            },
            "error_info": {
                "message": message,
                "operation_type": operation_type
            },
            "summary": {
                "operation_type": operation_type,
                "success": False
            }
        }
        return ToolResult(
            status="error", 
            message=message, 
            error=message,
            llm_content=llm_content
        ).model_dump()

    def _success(message: str, llm_content: Any, **data: Any) -> Dict[str, Any]:
        return ToolResult(
            status="success",
            message=message,
            llm_content=llm_content,
            data=data,
        ).model_dump()

    # Validate parameters
    if offset is not None and offset < 0:
        return _error("offset must be non-negative", file_path=path)
    
    if limit is not None and limit <= 0:
        return _error("limit must be positive", file_path=path)

    # Validate workspace access
    if not validate_path_in_workspace("."):
        return _error("Cannot access workspace directory", file_path=path)

    # ------------------------------------------------------------------
    # Path validation and security checks
    # ------------------------------------------------------------------

    # Validate file path
    abs_file_path = validate_path_in_workspace(path)
    if abs_file_path is None:
        return _error(f"File path is outside workspace: {path}", file_path=path)

    try:
        file_path = Path(abs_file_path)
        
        # Check file existence and type
        if not file_path.exists():
            return _error(f"File does not exist: {path}", file_path=path)
        
        if not file_path.is_file():
            return _error(f"Path is not a file: {path}", file_path=path)
        
        # Check file size
        file_size = file_path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            return _error(f"File too large: {file_size // 1024 // 1024}MB exceeds {MAX_FILE_SIZE_BYTES // 1024 // 1024}MB limit", file_path=path)
        
        # Security checks
        if file_path.is_symlink() and not is_safe_symlink(file_path):
            return _error("Cannot read unsafe symlink pointing outside workspace", file_path=path)
        
        if not check_parent_symlinks(file_path):
            return _error("Cannot read file with unsafe parent symlinks", file_path=path)

        # ------------------------------------------------------------------
        # File reading and analysis
        # ------------------------------------------------------------------

        # Read file with comprehensive analysis
        result = _read_file_safely(
            file_path=file_path,
            read_mode=read_mode,
            offset=offset,
            limit=limit,
        )

        # Build user-facing message
        if result.success:
            size_info = f"{result.file_metadata.size_category.value} {result.content_analysis.file_type.value}"
            if result.processing_result.truncated:
                message = f"Read {size_info} file: {path} (truncated, {result.processing_result.lines_shown[0]}-{result.processing_result.lines_shown[1]} lines)"
            else:
                message = f"Read {size_info} file: {path} ({result.content_analysis.line_count} lines)"
        else:
            message = f"Failed to read file: {path}"

        # Add performance and warnings info
        if result.performance.is_slow:
            message += f" - slow read ({result.performance.total_time:.2f}s)"
        
        if result.warnings:
            message += f" - {len(result.warnings)} warning(s)"

        # Build structured LLM content for consistency across tools
        rel_display = file_path.relative_to(WORKSPACE_ROOT) if str(file_path).startswith(str(WORKSPACE_ROOT)) else Path(path)
        
        # Handle content based on file type
        if result.processing_result.content_format == ContentFormat.INLINE_DATA:
            # For binary files, don't include base64 data in llm_content
            # The base64 data will be handled as separate multimodal Parts
            content_data = {
                "file_type": "binary",
                "mime_type": result.content_analysis.mime_type,
                "size_bytes": result.file_metadata.size,
                "multimodal_available": True
            }
        else:
            # For text files, include the actual content
            content_data = result.processing_result.content
        
        llm_content = {
            "operation": {
                "type": "read_file",
                "path": str(rel_display),
                "read_mode": result.read_mode.value,
                "truncated": result.processing_result.truncated,
                "content_format": result.processing_result.content_format.value
            },
            "file_info": {
                "size_bytes": result.file_metadata.size,
                "file_type": result.content_analysis.file_type.value,
                "extension": file_path.suffix.lower(),
                "line_count": result.content_analysis.line_count,
                "encoding": result.content_analysis.encoding
            },
            "content": {
                "data": content_data,
                "format": result.processing_result.content_format.value,
                "lines_shown": result.processing_result.lines_shown
            },
            "summary": {
                "operation_type": "read_file",
                "success": True
            }
        }

        return _success(
            message,
            llm_content,
            **result.to_dict(),
        )

    except Exception as exc:
        return _error(f"Unexpected error reading file: {exc}", file_path=path)

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