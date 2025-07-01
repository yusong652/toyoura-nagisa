"""read_file tool — single-file reader with offset/limit support.

Ported & simplified from gemini-cli ReadFileTool.  Provides fine-grained access
 to a *single* file inside the coding workspace, including pagination and basic
binary handling.
"""

import base64
import mimetypes
from pathlib import Path
from typing import Dict, Any, Union, Optional

from fastmcp import FastMCP  # type: ignore
from pydantic import Field
from pydantic.fields import FieldInfo

from .workspace import validate_path_in_workspace, DEFAULT_WORKSPACE as _WS_PATH


__all__ = ["read_file", "register_read_file_tool"]

_TEXT_CHARSET_DEFAULT = "utf-8"
_MAX_BYTES_DEFAULT = 131_072  # 128 KiB cap per read


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _read_text_segment(path: Path, offset: int | None, limit: int | None, encoding=_TEXT_CHARSET_DEFAULT) -> str:
    """Return *limit* bytes (not characters) from *path* starting at *offset*."""
    size = path.stat().st_size
    start = offset or 0
    if start > size:
        return ""
    with path.open("rb") as fh:
        fh.seek(start)
        chunk = fh.read(limit or _MAX_BYTES_DEFAULT)
    return chunk.decode(encoding, errors="replace")


def _inline_data(path: Path) -> Dict[str, Any]:
    mime, _ = mimetypes.guess_type(str(path))
    mime = mime or "application/octet-stream"
    data = base64.b64encode(path.read_bytes()).decode()
    return {"inline_data": {"mime_type": mime, "data": data}}


# -----------------------------------------------------------------------------
# Tool implementation
# -----------------------------------------------------------------------------

def read_file(
    path: str = Field(..., description="File path to read (workspace-relative or absolute)"),
    offset: Optional[int] = Field(None, ge=0, description="Byte offset to start reading from"),
    limit: Optional[int] = Field(None, gt=0, description="Maximum number of bytes to read"),
) -> Dict[str, Any]:
    """Read part of a file with optional byte-range.

    * For text files: returns `content` (string).
    * For recognised binary (e.g. images): returns `inline_data` with base64.
    * For other binary files: returns an error message.
    """

    # Normalize defaults coming from Pydantic FieldInfo when invoked programmatically
    if isinstance(offset, FieldInfo):
        offset = None
    if isinstance(limit, FieldInfo):
        limit = None

    # Resolve path (validate absolute or relative)
    abs_candidate = validate_path_in_workspace(path)

    if abs_candidate is None:
        return {"status": "error", "error": f"Path is outside of workspace: {path}"}

    abs_path_str = abs_candidate
    file_path = Path(abs_path_str)
    if not file_path.exists():
        return {"status": "error", "error": f"File does not exist: {path}"}
    if not file_path.is_file():
        return {"status": "error", "error": f"Path is not a file: {path}"}

    mime, _ = mimetypes.guess_type(str(file_path))
    is_text = (mime is None) or mime.startswith("text/") or mime in {"application/json", "application/xml"}

    try:
        if is_text:
            content = _read_text_segment(file_path, offset, limit)
            return {
                "status": "success",
                "path": str(file_path),
                "content": content,
            }
        else:
            # Binary — inline base64 if size reasonable
            if file_path.stat().st_size > _MAX_BYTES_DEFAULT:
                return {"status": "error", "error": "Binary file too large to inline."}
            return {
                "status": "success",
                "path": str(file_path),
                **_inline_data(file_path),
            }
    except Exception as exc:  # pylint: disable=broad-except
        return {"status": "error", "error": str(exc)}


# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_read_file_tool(mcp: FastMCP):
    common = dict(tags={"filesystem", "coding"}, annotations={"category": "coding"})
    mcp.tool(**common)(read_file) 