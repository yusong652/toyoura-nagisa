"""read_file tool — safe file reader with pagination & inline binary support."""

from typing import Any, Dict, List, Optional, Tuple

import base64
import mimetypes
from pathlib import Path

from fastmcp import FastMCP  # type: ignore
from pydantic import Field
from pydantic.fields import FieldInfo

from .workspace import validate_path_in_workspace, WORKSPACE_ROOT as _WS_PATH


__all__ = ["read_file", "register_read_file_tool"]

# ---------------------------------------------------------------------------
# Constants mirroring gemini-cli defaults
# ---------------------------------------------------------------------------

_TEXT_CHARSET_DEFAULT = "utf-8"

# Hard limits
_MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MiB

# Text rendering limits (lines & length per line)
DEFAULT_MAX_LINES_TEXT_FILE = 2_000
MAX_LINE_LENGTH_TEXT_FILE = 2_000

# Binary inline cap (to avoid embedding huge base64 blobs)
_INLINE_MAX_BYTES = 1024 * 512 # 512 KiB


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _file_size_ok(path: "Path") -> bool:
    return path.stat().st_size <= _MAX_FILE_SIZE_BYTES


def _is_binary_file(path: "Path", sample_size: int = 1024) -> bool:
    """Heuristic binary detector – looks for NUL bytes in the first *sample_size* bytes."""

    with path.open("rb") as fh:
        chunk = fh.read(sample_size)
    # If we find NUL bytes, assume binary
    return b"\x00" in chunk


def _detect_file_type(path: "Path") -> str:
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

    # Known binary extensions list (subset of gemini-cli for practicality)
    _binary_exts = {
        ".zip",
        ".tar",
        ".gz",
        ".exe",
        ".dll",
        ".so",
        ".class",
        ".jar",
        ".war",
        ".7z",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".odt",
        ".ods",
        ".odp",
        ".bin",
        ".dat",
        ".obj",
        ".o",
        ".a",
        ".lib",
        ".wasm",
        ".pyc",
        ".pyo",
    }
    if ext in _binary_exts:
        return "binary"

    # Fallback – treat as binary if heuristic detects non-text
    if _is_binary_file(path):
        return "binary"

    return "text"


def _read_text_lines(path: "Path", offset: int | None, limit: int | None) -> Tuple[str, bool, int, Tuple[int, int]]:
    """Return (content, is_truncated, original_line_count, (start, end))."""

    content = path.read_text(encoding=_TEXT_CHARSET_DEFAULT, errors="replace")
    all_lines = content.splitlines()
    original_count = len(all_lines)

    start = offset or 0
    effective_limit = limit if limit is not None else DEFAULT_MAX_LINES_TEXT_FILE
    end = min(start + effective_limit, original_count)

    # Guard against offset > original_count
    actual_start = min(start, original_count)
    selected = all_lines[actual_start:end]

    lines_were_truncated_in_length = False
    processed: List[str] = []
    for line in selected:
        if len(line) > MAX_LINE_LENGTH_TEXT_FILE:
            lines_were_truncated_in_length = True
            processed.append(line[:MAX_LINE_LENGTH_TEXT_FILE] + "... [truncated]")
        else:
            processed.append(line)

    is_truncated = (end < original_count) or lines_were_truncated_in_length

    header = ""
    if end < original_count:
        header += f"[File content truncated: showing lines {actual_start + 1}-{end} of {original_count} total lines. Use offset/limit parameters to view more.]\n"
    elif lines_were_truncated_in_length:
        header += (
            f"[File content partially truncated: some lines exceeded maximum length of {MAX_LINE_LENGTH_TEXT_FILE} characters.]\n"
        )

    return header + "\n".join(processed), is_truncated, original_count, (actual_start + 1, end)


def _inline_data(path: "Path", mime_type: str) -> Dict[str, Any]:
    data = base64.b64encode(path.read_bytes()).decode()
    return {
        "inline_data": {"mime_type": mime_type, "data": data},
    }


# ---------------------------------------------------------------------------
# Main implementation
# ---------------------------------------------------------------------------


def read_file(
    path: str = Field(..., description="File path to read (workspace-relative or absolute)"),
    offset: Optional[int] = Field(None, ge=0, description="0-based line offset to start reading from"),
    limit: Optional[int] = Field(
        None, gt=0, description="Number of lines to read (omit for default max)"
    ),
    force_inline_images: bool = Field(
        False, 
        description="Force embedding images as base64 (may consume many tokens). Default: false (returns path info only)"
    ),
) -> Dict[str, Any]:
    """Read a workspace file with optional line pagination.

    Returns
    -------
    Dict
        status          : "success" | "error"
        llm_content     : str | dict – factual payload for LLM history
        return_display  : str – short user-facing message
        path            : str – absolute path of the file (success only)
        content         : str – text content (text files)
        inline_data     : {mime_type, data} – base64 blob (inline binaries)
        truncated       : bool – flag when content was clipped (optional)
        original_line_count : int – total lines in file (optional)
        lines_shown     : [start, end] – line range returned (optional)
        error           : str – error details (error only)
    """

    # ------------------------------------------------------------------
    # Parameter validation (manual to stay lightweight)
    # ------------------------------------------------------------------

    # When invoked programmatically via FastMCP, `offset`/`limit` may come as
    # a Pydantic FieldInfo – coerce to None.
    if isinstance(offset, FieldInfo):
        offset = None
    if isinstance(limit, FieldInfo):
        limit = None

    # Validate numeric params
    for name, value in (("offset", offset), ("limit", limit)):
        if value is not None and value < 0:
            return {
                "status": "error",
                "error": f"{name} must be positive, got {value}",
            }

    # Resolve & validate path
    abs_candidate = validate_path_in_workspace(path)
    if abs_candidate is None:
        return {
            "status": "error",
            "error": f"Path is outside of workspace: {path}",
        }

    try:
        from pathlib import Path  # Local import to avoid top-level circular

        file_path = Path(abs_candidate)

        if not file_path.exists():
            return {"status": "error", "error": f"File does not exist: {path}"}
        if not file_path.is_file():
            return {"status": "error", "error": f"Path is not a file: {path}"}

        # Enforce 20 MiB limit
        if not _file_size_ok(file_path):
            size_mb = file_path.stat().st_size / (1024 * 1024)
            msg = f"File size exceeds the 20 MB limit ({size_mb:.2f} MB)."
            return {"status": "error", "error": msg}

        file_type = _detect_file_type(file_path)
        rel_display = (
            str(file_path.relative_to(_WS_PATH))
            if str(file_path).startswith(str(_WS_PATH))
            else str(file_path)
        )

        match file_type:
            case "text":
                content, is_truncated, original_count, (start_line, end_line) = _read_text_lines(
                    file_path, offset, limit
                )
                llm_content = content
                return_display = "(truncated)" if is_truncated else ""

                result = {
                    "llm_content": llm_content,
                    "return_display": return_display,
                    # Legacy keys ↓
                    "status": "success",
                    "path": str(file_path),
                    "content": content,
                }

                if is_truncated:
                    result.update(
                        {
                            "truncated": True,
                            "original_line_count": original_count,
                            "lines_shown": [start_line, end_line],
                        }
                    )
                return result

            case "image" | "pdf" | "audio" | "video":
                # Refuse to inline huge binaries to avoid blowing up the LLM context
                if file_path.stat().st_size > _INLINE_MAX_BYTES:
                    return {
                        "status": "error",
                        "error": "Binary file too large to inline.",
                    }

                mime_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
                inline_part = _inline_data(file_path, mime_type)
                result = {
                    "llm_content": inline_part,
                    "return_display": f"Read {file_type} file: {rel_display}",
                    # Legacy
                    "status": "success",
                    "path": str(file_path),
                    **inline_part,
                }
                return result

            case "binary":
                msg = f"Cannot display content of binary file: {rel_display}"
                return {
                    "llm_content": msg,
                    "return_display": f"Skipped binary file: {rel_display}",
                    "status": "error",
                    "error": "binary_file_not_supported",
                }

            case _:
                return {
                    "status": "error",
                    "error": "Unhandled file type",
                }

    except Exception as exc:  # pylint: disable=broad-except
        return {
            "status": "error",
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


def register_read_file_tool(mcp: FastMCP):
    common = dict(tags={"filesystem", "coding"}, annotations={"category": "coding"})
    mcp.tool(**common)(read_file) 