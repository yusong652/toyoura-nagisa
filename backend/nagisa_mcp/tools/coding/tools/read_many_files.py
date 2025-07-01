"""read_many_files tool (split from coding.fs_tools).

Reads multiple text files inside the coding workspace with glob support and
returns a mapping of file path → content.
"""

from pathlib import Path
from typing import List, Dict

from pydantic import Field
from fastmcp import FastMCP  # type: ignore

from .workspace import validate_path_in_workspace

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
# Public tool implementation
# -----------------------------------------------------------------------------

def read_many_files(
    paths: List[str] = Field(
        ..., description="Glob patterns or relative paths of files to read (e.g. 'src/**/*.py')",
    ),
    include: List[str] | None = Field(
        None, description="Additional include glob patterns (relative to workspace)",
    ),
    exclude: List[str] | None = Field(
        None, description="Glob patterns to exclude (relative to workspace)",
    ),
    max_bytes: int = Field(
        131_072, ge=1, description="Clip each file to at most this many bytes",
    ),
    use_default_excludes: bool = Field(
        True, description="Apply default ignore list such as node_modules",
    ),
) -> Dict[str, str]:
    """Read multiple text files and return a mapping *path → content*.

    Binary files are skipped unless size ≤ max_bytes and contain no NUL bytes.
    Duplicate paths are deduplicated.
    """

    workspace_root = Path(validate_path_in_workspace("."))

    patterns = list(paths)
    if include:
        patterns.extend(include)

    files: list[Path] = _expand_globs(workspace_root, patterns)

    # ------------------------------------------------------------------
    # Build exclude matchers
    # ------------------------------------------------------------------

    default_excl_dirs: set[str] = set(DEFAULT_EXCLUDES) if use_default_excludes else set()

    pattern_excludes: set[str] = set()
    if exclude:
        pattern_excludes.update(exclude)

    # Pre-compile glob patterns (Path.match uses the raw pattern each time –
    # storing them in a list avoids rebuilding the set for every path).
    compiled_globs = list(pattern_excludes)

    def _excluded(p: Path) -> bool:
        """Return *True* if *p* (absolute) should be excluded."""

        rel = p.relative_to(workspace_root)

        # Fast directory-name exclusion (node_modules, .git, …)
        if any(part in default_excl_dirs for part in rel.parts):
            return True

        # Glob pattern exclusion
        return any(rel.match(glob_pat) for glob_pat in compiled_globs)

    files = [f for f in files if f.is_file() and not _excluded(f)]

    out: Dict[str, str] = {}
    for f in files:
        rel = str(f.relative_to(workspace_root))
        try:
            if _is_binary(f):
                out[rel] = "[SKIPPED_BINARY]"
                continue
            out[rel] = _safe_read(f, max_bytes)
        except Exception as exc:  # pylint: disable=broad-except
            out[rel] = f"[ERROR] {exc}"

    return out


# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_read_many_files_tool(mcp: FastMCP):
    common = dict(tags={"filesystem", "coding"}, annotations={"category": "coding"})
    mcp.tool(**common)(read_many_files) 