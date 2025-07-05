"""read_many_files tool – bulk reader for multiple workspace files.

This tool mirrors the public-facing contract used by the other coding.tools
(e.g. `read_file`, `write_file`, `run_shell_command`) so that *all* file-system
helpers share a consistent return format suitable for FastMCP / Gemini-CLI.

At a glance
-----------
• **Reads many text files** at once, accepting glob patterns ("src/**/*.py") or
  concrete relative paths.
• **Safe by default** – skips obviously binary files, respects an ignore list
  (`node_modules`, `.git`, …) and caps the bytes read per file.
• **Returns a rich, structured payload** with both user-friendly and LLM-ready
  fields, plus per-file error reporting.

Example
~~~~~~~
```python
read_many_files(paths=["src/**/*.py"], exclude=["**/tests/**"], max_bytes=4096)
```
"""

from pathlib import Path
from typing import List, Dict, Any
import base64
import mimetypes
import os

from pydantic import Field
from fastmcp import FastMCP  # type: ignore

from .workspace import validate_path_in_workspace
from .config import get_tools_config

# -----------------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------------

DEFAULT_EXCLUDES = {
    "node_modules",
    ".git",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "coverage",
    "__pycache__",
}

# Same inline cap as read_file.py – avoids huge base64 blobs.
_INLINE_MAX_BYTES = 131_072  # 128 KiB


def _safe_read(path: Path, max_bytes: int, encoding: str = "utf-8") -> str:
    """Read up to *max_bytes* from *path* and return decoded text (replace errors)."""
    chunk = path.read_bytes()[:max_bytes]
    return chunk.decode(encoding, errors="replace")


def _is_binary(path: Path) -> bool:
    """Rudimentary binary detection (check for NUL bytes in first 8000 bytes)."""
    try:
        with path.open("rb") as fh:
            head = fh.read(8000)
        return b"\0" in head
    except Exception:
        return True


def _expand_globs(base: Path, patterns: List[str]) -> List[Path]:
    """Return unique Paths matching the given glob patterns inside *base*."""
    files: set[Path] = set()
    for pat in patterns:
        files.update(base.glob(pat))
    return sorted(files)


# -----------------------------------------------------------------------------
# Internal helpers (shared with other tools)
# -----------------------------------------------------------------------------

def _make_error(msg: str) -> Dict[str, Any]:
    """Return a *standardised* error payload matching other coding.tools."""

    return {
        "status": "error",
        "error": msg,
        "llm_content": f"Error: {msg}",
        "return_display": f"❌ {msg}",
    }


# -----------------------------------------------------------------------------
# Public tool implementation
# -----------------------------------------------------------------------------

def read_many_files(
    paths: List[str] = Field(
        ...,
        description="Glob patterns or relative file paths to read – e.g. `src/**/*.py` or `README.md`.",
    ),
    include: List[str] | None = Field(
        None,
        description=(
            "Additional file patterns to merge with `paths`.  *Tip:* list image / PDF "
            "names here (e.g. `'diagram.png'`, `'manual.pdf'`) to **explicitly request** "
            "those non-text assets – they will be inlined as Base-64 if small enough."
        ),
    ),
    exclude: List[str] | None = Field(
        None,
        description="Glob patterns to *exclude* from the final result – evaluated **after** the include list.",
    ),
    max_bytes: int = Field(
        131_072,
        ge=1,
        description="Maximum number of bytes to read *per file* (hard cap to protect context size).",
    ),
    use_default_excludes: bool = Field(
        True,
        description="Enable the built-in ignore list (`node_modules`, `.git`, `dist`, …).",
    ),
) -> Dict[str, Any]:
    """Read **many** text files at once.

    The tool walks each supplied *glob pattern* (relative to the workspace root),
    reads matching *text* files up to ``max_bytes`` and returns their content.

    Returned mapping uses **workspace-relative paths** as keys.  Binary files
    are skipped automatically; errors are reported per-file.

    Returns
    -------
    Dict with the following schema (mirrors other coding.tools):

    status : "success" | "error"
        Overall tool outcome.
    files : Dict[str, str]
        Mapping *path → content* for successfully read files.
    skipped : Dict[str, str] (optional)
        Paths that were ignored and the corresponding reason ("binary", "error: …").
    llm_content : str
        Detailed factual summary – suitable for adding to the LLM context.
    return_display : str
        Short user-facing message (truncated if ``debug_mode`` is *False*).
    error : str (only when *status == "error"*)
        Human-readable error description.
    """

    workspace_root = Path(validate_path_in_workspace("."))

    # ------------------------------------------------------------------
    # Expand include patterns → concrete Path list
    # ------------------------------------------------------------------
    patterns: List[str] = list(paths)
    if include:
        patterns.extend(include)

    candidate_files: list[Path] = _expand_globs(workspace_root, patterns)

    # ------------------------------------------------------------------
    # Build exclusion rules
    # ------------------------------------------------------------------
    default_excl_dirs: set[str] = set(DEFAULT_EXCLUDES) if use_default_excludes else set()

    pattern_excludes: set[str] = set(exclude or [])
    compiled_globs = list(pattern_excludes)

    def _excluded(p: Path) -> bool:
        rel = p.relative_to(workspace_root)
        if any(part in default_excl_dirs for part in rel.parts):
            return True
        return any(rel.match(glob_pat) for glob_pat in compiled_globs)

    selected_files = [f for f in candidate_files if f.is_file() and not _excluded(f)]

    if not selected_files:
        return _make_error("No files matched the given patterns.")

    # ------------------------------------------------------------------
    # Read files (text vs assets)
    # ------------------------------------------------------------------
    files: Dict[str, Any] = {}
    skipped: Dict[str, str] = {}

    # Cache lower-case explicit patterns for quick substring checks
    explicit_patterns_lc = [p.lower() for p in patterns]

    for f in selected_files:
        rel = str(f.relative_to(workspace_root))

        try:
            f_type = _detect_file_type(f)

            if f_type == "text":
                files[rel] = _safe_read(f, max_bytes)
                continue

            if f_type in {"image", "pdf", "audio", "video"}:
                # Determine if explicitly requested (ext or filename appears in patterns)
                ext_lc = f.suffix.lower()
                name_lc = f.name.lower()
                requested = any(ext_lc in pat or name_lc in pat for pat in explicit_patterns_lc)

                if not requested:
                    skipped[rel] = "asset_not_explicit"
                    continue

                if f.stat().st_size > _INLINE_MAX_BYTES:
                    skipped[rel] = "asset_too_large"
                    continue

                mime_type = mimetypes.guess_type(str(f))[0] or "application/octet-stream"
                files[rel] = _inline_data(f, mime_type)
                continue

            # Default: treat as binary-skip
            skipped[rel] = "binary"

        except Exception as exc:  # pylint: disable=broad-except
            skipped[rel] = f"error: {exc}"

    # ------------------------------------------------------------------
    # Compose return payload
    # ------------------------------------------------------------------
    debug = get_tools_config().debug_mode
    file_count = len(files)
    skipped_count = len(skipped)

    # Truncate list for readability
    preview_paths = list(files.keys())[:10]
    joined = ", ".join(preview_paths) + (", …" if file_count > 10 else "")

    llm_content = (
        f"Read {file_count} file(s){' (+' + str(skipped_count) + ' skipped)' if skipped_count else ''}: "
        f"{joined}"
    )

    return_display = llm_content if debug else f"Read {file_count} file(s)."

    payload: Dict[str, Any] = {
        "status": "success",
        "files": files,
        "llm_content": llm_content,
        "return_display": return_display,
    }

    if skipped:
        payload["skipped"] = skipped

    return payload


# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_read_many_files_tool(mcp: FastMCP):
    common = dict(tags={"filesystem", "coding"}, annotations={"category": "coding"})
    mcp.tool(**common)(read_many_files)


# ---------------------------------------------------------------------------
# File-type helpers (mirrors logic in read_file.py for consistency)
# ---------------------------------------------------------------------------

def _detect_file_type(path: "Path") -> str:
    """Return 'text' | 'image' | 'pdf' | 'audio' | 'video' | 'binary'."""

    mime, _ = mimetypes.guess_type(str(path))
    ext = path.suffix.lower()

    if mime and mime.startswith("image/"):
        return "image"
    if mime == "application/pdf" or ext == ".pdf":
        return "pdf"
    if mime and mime.startswith("audio/"):
        return "audio"
    if mime and mime.startswith("video/"):
        return "video"

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

    # Fallback heuristic
    return "binary" if _is_binary(path) else "text"


def _inline_data(path: "Path", mime_type: str) -> Dict[str, Any]:
    data_b64 = base64.b64encode(path.read_bytes()).decode()
    return {"inline_data": {"mime_type": mime_type, "data": data_b64}} 