from pathlib import Path
from typing import List, Dict

from fastmcp import FastMCP
from pydantic import Field

from ..workspace import validate_path_in_workspace

__all__ = [
    "register_fs_tools",
]

# ---------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------

def _safe_read(path: Path, max_bytes: int, encoding: str = "utf-8") -> str:
    """Read up to *max_bytes* from *path* and return decoded text (replace errors)."""
    chunk = path.read_bytes()[: max_bytes]
    return chunk.decode(encoding, errors="replace")


# ---------------------------------------------------------------------
#   TOOL IMPLEMENTATIONS
# ---------------------------------------------------------------------

DEFAULT_EXCLUDES = {
    "node_modules", ".git", ".idea", ".vscode", "dist", "build", "coverage", "__pycache__",
}


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


def read_many_files(
    paths: List[str] = Field(
        ..., description="Glob patterns or relative paths of files to read (e.g. 'src/**/*.py')"
    ),
    include: List[str] | None = Field(
        None, description="Additional include glob patterns (relative to workspace)"
    ),
    exclude: List[str] | None = Field(
        None, description="Glob patterns to exclude (relative to workspace)"
    ),
    max_bytes: int = Field(131_072, ge=1, description="Clip each file to at most this many bytes"),
    use_default_excludes: bool = Field(True, description="Apply default ignore list such as node_modules"),
) -> Dict[str, str]:
    """Read multiple text files and return a mapping path->content.

    • Supports glob patterns.
    • Binary files are skipped unless size ≤ max_bytes and have no NUL bytes.
    • Duplicate paths are deduplicated.
    """

    workspace_root = Path(validate_path_in_workspace("."))

    # Expand initial patterns
    patterns = list(paths)
    if include:
        patterns.extend(include)
    files: list[Path] = _expand_globs(workspace_root, patterns)

    # Apply exclude patterns/default excludes
    if use_default_excludes:
        excl_set = set(DEFAULT_EXCLUDES)
    else:
        excl_set = set()
    if exclude:
        excl_set.update(exclude)

    def _excluded(p: Path) -> bool:
        rel = p.relative_to(workspace_root)
        parts = set(rel.parts)
        if parts & DEFAULT_EXCLUDES:
            return True
        for ex in excl_set:
            if rel.match(ex):
                return True
        return False

    files = [f for f in files if f.is_file() and not _excluded(f)]

    out: Dict[str, str] = {}
    for f in files:
        rel = str(f.relative_to(workspace_root))
        try:
            if _is_binary(f):
                out[rel] = "[SKIPPED_BINARY]"
                continue
            out[rel] = _safe_read(f, max_bytes)
        except Exception as exc:
            out[rel] = f"[ERROR] {exc}"

    return out


def write_file(
    path: str = Field(..., description="Path where to write (workspace-relative)"),
    content: str = Field(..., description="Text content to write"),
    encoding: str = Field("utf-8", description="File encoding"),
    append: bool = Field(False, description="Append instead of overwrite")
) -> Dict[str, str]:
    """Simpler wrapper around file write (mirrors existing coding.file_io)."""
    abs_path = validate_path_in_workspace(path)
    if abs_path is None:
        return {"error": f"Path is outside of workspace: {path}"}
    try:
        mode = "a" if append else "w"
        Path(abs_path).parent.mkdir(parents=True, exist_ok=True)
        with open(abs_path, mode, encoding=encoding) as fh:
            fh.write(content)
        return {"status": "success", "size": Path(abs_path).stat().st_size}
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------
# Directory listing & deletion helpers (ported from old file_io)
# ---------------------------------------------------------------------


def list_directory(
    path: str = Field("", description="Directory path to list contents from (workspace-relative)"),
    show_hidden: bool = Field(False, description="Whether to include hidden .* files"),
):
    """Return a JSON-serialisable list of entries in *path* inside workspace."""

    abs_path = validate_path_in_workspace(path)
    if abs_path is None:
        return [{"error": f"Path is outside of workspace: {path}"}]
    p = Path(abs_path)
    if not p.exists():
        return [{"error": f"Path does not exist: {path}"}]
    if not p.is_dir():
        return [{"error": f"Path is not a directory: {path}"}]

    items: list[dict] = []
    for child in p.iterdir():
        if not show_hidden and child.name.startswith("."):
            continue
        items.append(
            {
                "name": child.name,
                "type": "directory" if child.is_dir() else "file",
                "size": child.stat().st_size if child.is_file() else None,
                "path": str(child),
            }
        )
    return items


def delete_file(path: str = Field(..., description="File path to delete (workspace-relative)")):
    abs_path = validate_path_in_workspace(path)
    if abs_path is None:
        return {"error": f"Path is outside of workspace: {path}"}
    f = Path(abs_path)
    if not f.exists():
        return {"error": f"File does not exist: {path}"}
    if not f.is_file():
        return {"error": f"Path is not a file: {path}"}
    try:
        f.unlink()
        return {"status": "success", "message": f"File deleted: {path}"}
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------
#   REGISTRATION ENTRYPOINT
# ---------------------------------------------------------------------

def register_fs_tools(mcp: FastMCP):
    """Register filesystem coding tools to the provided FastMCP instance."""
    common = dict(tags={"filesystem", "coding"}, annotations={"category": "coding"})
    for fn in (list_directory, read_many_files, write_file, delete_file):
        mcp.tool(**common)(fn) 