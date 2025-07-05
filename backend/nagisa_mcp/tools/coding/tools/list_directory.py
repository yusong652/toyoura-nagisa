"""list_directory tool (split from coding.fs_tools)."""

from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import Field
from fastmcp import FastMCP  # type: ignore
from datetime import datetime, timezone

from .workspace import validate_path_in_workspace, WORKSPACE_ROOT
from ..utils.file_filter import FileFilter
from ..utils.tool_result import ToolResult

# Optional dependency for .gitignore parsing
try:
    from pathspec import PathSpec  # type: ignore
except ModuleNotFoundError:  # pragma: no cover – optional feature
    PathSpec = None  # type: ignore

__all__ = ["list_directory", "register_list_directory_tool"]


def list_directory(
    path: str = Field("", description="Directory path to list contents from (workspace-relative)"),
    show_hidden: bool = Field(False, description="Whether to include hidden .* files"),
    respect_git_ignore: bool = Field(
        True, description="Whether to respect .gitignore patterns when listing files"
    ),
    ignore: Optional[List[str]] = Field(
        None, description="Glob ignore patterns (e.g. '*.pyc')"
    ),
) -> Dict[str, Any]:
    """Return directory listing in a consistent response wrapper.

    Success::
        {
          "status": "success",
          "items": [ {"name": ..., "type": "file"|"directory", ...}, ... ]
        }

    Error::
        {"status": "error", "error": "message"}
    """

    abs_path = validate_path_in_workspace(path)
    if abs_path is None:
        return {"status": "error", "error": f"Path is outside of workspace: {path}"}

    p = Path(abs_path)
    if not p.exists():
        return {"status": "error", "error": f"Path does not exist: {path}"}
    if not p.is_dir():
        return {"status": "error", "error": f"Path is not a directory: {path}"}

    # ------------------------------------------------------------------
    # Build reusable file filter
    # ------------------------------------------------------------------
    file_filter = FileFilter(
        workspace_root=WORKSPACE_ROOT,
        show_hidden=show_hidden,
        ignore_patterns=ignore,
        respect_git_ignore=respect_git_ignore,
    )

    items: List[Dict[str, Any]] = []
    for child in p.iterdir():
        if not file_filter.include(child):
            continue

        items.append(
            {
                "name": child.name,
                "type": "directory" if child.is_dir() else "file",
                "size": child.stat().st_size if child.is_file() else 0,
                "modified_time": datetime.fromtimestamp(
                    child.stat().st_mtime, tz=timezone.utc
                ).isoformat(),
                "path": str(child),
            }
        )

    # ------------------------------------------------------------------
    # Sort: directories first, then alphabetical (case-insensitive)
    # ------------------------------------------------------------------
    items.sort(key=lambda x: (x["type"] != "directory", x["name"].lower()))

    payload: Dict[str, Any] = {"items": items}
    if file_filter.gitignored:
        payload["git_ignored"] = file_filter.gitignored

    extra: Dict[str, Any] = {}
    if respect_git_ignore and "PathSpec" in globals() and PathSpec is None:
        extra["warning"] = "pathspec library not installed – gitignore filtering skipped"

    resp = ToolResult(
        status="success",
        message=f"Listed {len(items)} item(s).",
        llm_content=None,
        data=payload,
        **extra,
    )

    return resp.model_dump()


# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_list_directory_tool(mcp: FastMCP):
    common = dict(tags={"filesystem", "coding"}, annotations={"category": "coding"})
    mcp.tool(**common)(list_directory) 