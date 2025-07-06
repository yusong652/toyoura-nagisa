"""read_many_files tool – bulk reader for multiple workspace files with SOTA security and performance."""

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import base64
import mimetypes
import os

from pydantic import Field
from pydantic.fields import FieldInfo
from fastmcp import FastMCP  # type: ignore

from ..utils.path_security import (
    validate_path_in_workspace, 
    WORKSPACE_ROOT, 
    is_safe_symlink, 
    check_parent_symlinks
)
from ..utils.tool_result import ToolResult
from .config import get_tools_config

__all__ = ["read_many_files", "register_read_many_files_tool"]

# -----------------------------------------------------------------------------
# Constants and limits (mirroring read_file.py for consistency)
# -----------------------------------------------------------------------------

_TEXT_CHARSET_DEFAULT = "utf-8"

# File size limits
_MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MiB per file
_INLINE_MAX_BYTES = 512 * 1024  # 512 KiB for inline binary data

# Performance protection limits
_MAX_FILES_DEFAULT = 100  # Maximum files to read in one operation
_MAX_TOTAL_SIZE_DEFAULT = 50 * 1024 * 1024  # 50 MiB total data limit

# Default exclusions for common large/irrelevant directories
DEFAULT_EXCLUDES = {
    "node_modules",
    ".git",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "coverage",
    "__pycache__",
    ".next",
    ".nuxt",
    "target",
    "venv",
    ".env",
    ".cache",
}

# -----------------------------------------------------------------------------
# Helper utilities (consistent with read_file.py)
# -----------------------------------------------------------------------------

def _is_binary_file(path: Path, sample_size: int = 1024) -> bool:
    """Heuristic binary detector – looks for NUL bytes in the first *sample_size* bytes."""
    try:
        with path.open("rb") as fh:
            chunk = fh.read(sample_size)
        return b"\x00" in chunk
    except Exception:
        return True

def _detect_file_type(path: Path) -> str:
    """Return 'text' | 'image' | 'pdf' | 'audio' | 'video' | 'binary'."""
    mime, _ = mimetypes.guess_type(str(path))
    ext = path.suffix.lower()

    # Specific quick wins – images / pdf
    if mime and mime.startswith("image/"):
        return "image"
    if mime == "application/pdf" or ext == ".pdf":
        return "pdf"
    if mime and mime.startswith("audio/"):
        return "audio"
    if mime and mime.startswith("video/"):
        return "video"

    # Known binary extensions list (consistent with read_file.py)
    _binary_exts = {
        ".zip", ".tar", ".gz", ".exe", ".dll", ".so", ".class", ".jar", ".war",
        ".7z", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt",
        ".ods", ".odp", ".bin", ".dat", ".obj", ".o", ".a", ".lib", ".wasm",
        ".pyc", ".pyo",
    }
    if ext in _binary_exts:
        return "binary"

    # Fallback – treat as binary if heuristic detects non-text
    if _is_binary_file(path):
        return "binary"

    return "text"

def _safe_read_text(path: Path, max_bytes: int) -> str:
    """Read up to *max_bytes* from *path* and return decoded text (replace errors)."""
    chunk = path.read_bytes()[:max_bytes]
    return chunk.decode(_TEXT_CHARSET_DEFAULT, errors="replace")

def _inline_data(path: Path, mime_type: str) -> Dict[str, Any]:
    """Return inline_data payload with base64 encoded content."""
    data_b64 = base64.b64encode(path.read_bytes()).decode()
    return {
        "inline_data": {"mime_type": mime_type, "data": data_b64},
    }

def _expand_globs_streaming(base: Path, patterns: List[str], max_files: int = 1000):
    """Generator that yields unique Paths matching glob patterns with early termination."""
    seen_files: set[Path] = set()
    files_yielded = 0
    
    for pat in patterns:
        try:
            for file_path in base.glob(pat):
                # Early termination check
                if files_yielded >= max_files:
                    return
                
                # Deduplicate files
                if file_path in seen_files:
                    continue
                
                # Only yield actual files
                if file_path.is_file():
                    seen_files.add(file_path)
                    yield file_path
                    files_yielded += 1
                    
        except Exception:
            # Skip invalid glob patterns
            continue

def _file_size_ok(path: Path) -> bool:
    """Check if file size is within limits."""
    try:
        return path.stat().st_size <= _MAX_FILE_SIZE_BYTES
    except Exception:
        return False

# -----------------------------------------------------------------------------
# Main implementation
# -----------------------------------------------------------------------------

def read_many_files(
    paths: List[str] = Field(
        ...,
        description="Glob patterns or relative file paths to read – e.g. `src/**/*.py` or `README.md`.",
    ),
    include: Optional[List[str]] = Field(
        None,
        description=(
            "Additional file patterns to merge with `paths`. List image/PDF names here "
            "(e.g. `'diagram.png'`, `'manual.pdf'`) to explicitly request those assets."
        ),
    ),
    exclude: Optional[List[str]] = Field(
        None,
        description="Glob patterns to exclude from the final result – evaluated after the include list.",
    ),
    max_bytes_per_file: int = Field(
        131_072,  # 128 KiB default
        ge=1,
        le=_MAX_FILE_SIZE_BYTES,
        description="Maximum bytes to read per file (protects against large files).",
    ),
    max_files: int = Field(
        _MAX_FILES_DEFAULT,
        ge=1,
        le=500,
        description="Maximum number of files to read in one operation (performance protection).",
    ),
    max_total_size: int = Field(
        _MAX_TOTAL_SIZE_DEFAULT,
        ge=1024,
        description="Maximum total size of all file content combined (memory protection).",
    ),
    use_default_excludes: bool = Field(
        True,
        description="Enable the built-in ignore list (`node_modules`, `.git`, `dist`, etc.).",
    ),
    force_inline_assets: bool = Field(
        False,
        description="Force inline embedding of small image/pdf/audio/video files as base64.",
    ),
) -> Dict[str, Any]:
    """read_many_files – Bulk read multiple text files with enterprise-grade security and performance.

    This tool efficiently reads multiple files matching glob patterns or specific paths,
    with comprehensive security checks, performance limits, and intelligent handling of
    different file types. All operations are restricted to the workspace directory with
    multi-layer protection against malicious paths and resource exhaustion.

    Successful response (``ToolResult.model_dump()``) – **keys of interest**::

        {
        "status": "success",
        "message": "Read 15 files successfully (2 skipped)",  # short summary
        "llm_content": "Read 15 files: src/main.py, src/utils.py...",  # detailed content for LLM
        "data": {
            "files": {                                        # file path → content mapping
                "src/main.py": "#!/usr/bin/env python...",    # text file content
                "docs/logo.png": {                            # binary file inline data
                    "inline_data": {"mime_type": "image/png", "data": "iVBORw0KGgo..."}
                }
            },
                         "statistics": {                                   # read operation stats
                 "files_read": 15,                             # successfully read files
                 "files_skipped": 2,                           # skipped files
                 "files_processed": 20,                        # total files examined
                 "total_bytes": 45231,                         # total content size
                 "largest_file": "src/main.py (15.2 KB)"      # largest file info
             },
            "skipped": {                                      # skipped files with reasons
                "node_modules/package.json": "excluded_directory",
                "image.jpg": "asset_not_explicit"
            },
            "limits_applied": {                               # performance limits info
                "max_files": 100,
                "max_total_size": 52428800,
                "stopped_early": false
            }
        }
        }

    Error response::

        {
        "status": "error",
        "message": "No files matched the given patterns",
        "error": "No files matched the given patterns"
        }

    Security Features:
    - Path validation: All paths validated against workspace boundaries
    - Symlink safety: Prevents reading symlinks pointing outside workspace
    - Parent directory safety: Checks all parent directories for unsafe symlinks
    - File size limits: Individual file size protection (default 20MB max)
    - Resource limits: Total memory and file count protection

    Performance Features:
    - Smart exclusions: Automatically excludes common large directories
    - Batch limits: Configurable maximum files per operation
    - Memory protection: Total size limits prevent memory exhaustion
    - Early termination: Stops reading when limits are reached
    - Progress tracking: Detailed statistics for monitoring

    Reliability Features:
    - Graceful degradation: Continues processing even if some files fail
    - Detailed error reporting: Per-file error tracking with specific reasons
    - Content type detection: Intelligent handling of text vs binary files
    - Encoding safety: Robust text decoding with error replacement

    The **``llm_content``** field provides structured information optimized for
    the assistant's context, while **``message``** is a concise user summary.
    """

    # ------------------------------------------------------------------
    # Parameter validation (manual to stay lightweight)
    # ------------------------------------------------------------------

    # Handle Pydantic FieldInfo objects when invoked programmatically
    if isinstance(include, FieldInfo):
        include = None
    if isinstance(exclude, FieldInfo):
        exclude = None
    if isinstance(max_bytes_per_file, FieldInfo):
        max_bytes_per_file = 131_072
    if isinstance(max_files, FieldInfo):
        max_files = _MAX_FILES_DEFAULT
    if isinstance(max_total_size, FieldInfo):
        max_total_size = _MAX_TOTAL_SIZE_DEFAULT
    if isinstance(use_default_excludes, FieldInfo):
        use_default_excludes = True
    if isinstance(force_inline_assets, FieldInfo):
        force_inline_assets = False

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

    # Validate workspace access
    if not validate_path_in_workspace("."):
        return _error("Cannot access workspace directory")

    # ------------------------------------------------------------------
    # Build file list from patterns
    # ------------------------------------------------------------------

    try:
        # Combine all patterns
        all_patterns = list(paths)
        if include:
            all_patterns.extend(include)

        if not all_patterns:
            return _error("No file patterns provided")

        # ------------------------------------------------------------------
        # Streaming file collection with integrated filtering
        # ------------------------------------------------------------------

        # Build exclusion rules upfront
        default_excl_dirs = set(DEFAULT_EXCLUDES) if use_default_excludes else set()
        pattern_excludes = set(exclude or [])

        def _should_exclude(file_path: Path) -> Tuple[bool, str]:
            """Return (should_exclude, reason)."""
            try:
                rel_path = file_path.relative_to(WORKSPACE_ROOT)
                
                # Check default exclusions
                if any(part in default_excl_dirs for part in rel_path.parts):
                    return True, "excluded_directory"
                
                # Check pattern exclusions
                if any(rel_path.match(pattern) for pattern in pattern_excludes):
                    return True, "excluded_pattern"
                
                return False, ""
            except Exception:
                return True, "path_error"

        # Cache explicit patterns for asset detection
        explicit_patterns_lc = [p.lower() for p in all_patterns]

        # ------------------------------------------------------------------
        # Streaming processing with early termination
        # ------------------------------------------------------------------

        files = {}
        skipped = {}
        total_bytes = 0
        largest_file = ""
        largest_size = 0
        files_processed = 0
        stopped_early = False

        # Stream files and process them immediately
        for file_path in _expand_globs_streaming(WORKSPACE_ROOT, all_patterns, max_files * 2):  # 2x buffer for filtering
            # Early termination if we've reached our file limit
            if len(files) >= max_files:
                stopped_early = True
                break
            
            rel_path = str(file_path.relative_to(WORKSPACE_ROOT))
            files_processed += 1

            try:
                # Apply exclusion filters
                should_exclude, exclude_reason = _should_exclude(file_path)
                if should_exclude:
                    skipped[rel_path] = exclude_reason
                    continue

                # Security checks
                abs_path_str = validate_path_in_workspace(rel_path)
                if abs_path_str is None:
                    skipped[rel_path] = "outside_workspace"
                    continue

                # Check if file is a symlink and validate safety
                if file_path.is_symlink() and not is_safe_symlink(file_path):
                    skipped[rel_path] = "unsafe_symlink"
                    continue

                # Check parent directory safety
                if not check_parent_symlinks(file_path):
                    skipped[rel_path] = "unsafe_parent_symlink"
                    continue

                # Check file size
                if not _file_size_ok(file_path):
                    file_size_mb = file_path.stat().st_size / (1024 * 1024)
                    skipped[rel_path] = f"too_large_{file_size_mb:.1f}MB"
                    continue

                # Detect file type
                file_type = _detect_file_type(file_path)
                file_size = file_path.stat().st_size

                # Track largest file
                if file_size > largest_size:
                    largest_size = file_size
                    largest_file = f"{rel_path} ({file_size / 1024:.1f} KB)"

                # Handle different file types with total size checking
                if file_type == "text":
                    # Check total size limit before reading
                    estimated_read_size = min(file_size, max_bytes_per_file)
                    if total_bytes + estimated_read_size > max_total_size:
                        skipped[rel_path] = "total_size_limit"
                        stopped_early = True
                        break

                    content = _safe_read_text(file_path, max_bytes_per_file)
                    files[rel_path] = content
                    total_bytes += len(content.encode(_TEXT_CHARSET_DEFAULT))

                elif file_type in {"image", "pdf", "audio", "video"}:
                    # Check if asset is explicitly requested or forced
                    ext_lc = file_path.suffix.lower()
                    name_lc = file_path.name.lower()
                    explicitly_requested = any(
                        ext_lc in pat or name_lc in pat 
                        for pat in explicit_patterns_lc
                    )

                    if not explicitly_requested and not force_inline_assets:
                        skipped[rel_path] = "asset_not_explicit"
                        continue

                    # Check size limits for inline data
                    if file_size > _INLINE_MAX_BYTES:
                        skipped[rel_path] = f"asset_too_large_{file_size / 1024:.1f}KB"
                        continue

                    # Check total size limit
                    if total_bytes + file_size > max_total_size:
                        skipped[rel_path] = "total_size_limit"
                        stopped_early = True
                        break

                    mime_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
                    inline_data = _inline_data(file_path, mime_type)
                    files[rel_path] = inline_data
                    total_bytes += file_size

                else:
                    # Binary file
                    skipped[rel_path] = "binary"

            except PermissionError:
                skipped[rel_path] = "permission_denied"
            except Exception as exc:
                skipped[rel_path] = f"error_{str(exc)[:50]}"

        # Check if we found any matching files at all
        if len(files) == 0 and len(skipped) == 0:
            return _error("No files matched the given patterns")

        # ------------------------------------------------------------------
        # Build response
        # ------------------------------------------------------------------

        files_read = len(files)
        files_skipped = len(skipped)

        if files_read == 0:
            return _error("No files could be read successfully")

        # Build summary for LLM
        file_list = list(files.keys())
        preview_files = file_list[:5]
        file_preview = ", ".join(preview_files)
        if len(file_list) > 5:
            file_preview += f", ... (+{len(file_list) - 5} more)"

        llm_content = f"Read {files_read} files{f' ({files_skipped} skipped)' if files_skipped else ''}: {file_preview}"

        # Build response message
        message = f"Read {files_read} files successfully"
        if files_skipped:
            message += f" ({files_skipped} skipped)"

        # Prepare detailed statistics
        statistics = {
            "files_read": files_read,
            "files_skipped": files_skipped,
            "files_processed": files_processed,
            "total_bytes": total_bytes,
            "largest_file": largest_file if largest_file else "N/A"
        }

        limits_info = {
            "max_files": max_files,
            "max_total_size": max_total_size,
            "stopped_early": stopped_early
        }

        response_data = {
            "files": files,
            "statistics": statistics,
            "limits_applied": limits_info
        }

        if skipped:
            response_data["skipped"] = skipped

        return _success(message, llm_content, **response_data)

    except Exception as exc:  # pylint: disable=broad-except
        return _error(f"Unexpected error: {exc}")

# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_read_many_files_tool(mcp: FastMCP):
    common = dict(tags={"filesystem", "coding"}, annotations={"category": "coding"})
    mcp.tool(**common)(read_many_files) 