"""list_directory tool (split from coding.fs_tools)."""

from pathlib import Path
from typing import List, Dict, Any
from pydantic import Field
from fastmcp import FastMCP  # type: ignore

from .workspace import validate_path_in_workspace

__all__ = ["list_directory", "register_list_directory_tool"]


def list_directory(
    path: str = Field("", description="Directory path to list contents from (workspace-relative)"),
    show_hidden: bool = Field(False, description="Whether to include hidden .* files"),
) -> List[Dict[str, Any]]:
    """Return a serialisable list of entries in *path* inside the workspace."""

    abs_path = validate_path_in_workspace(path)
    if abs_path is None:
        return [{"error": f"Path is outside of workspace: {path}"}]

    p = Path(abs_path)
    if not p.exists():
        return [{"error": f"Path does not exist: {path}"}]
    if not p.is_dir():
        return [{"error": f"Path is not a directory: {path}"}]

    items: List[Dict[str, Any]] = []
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


# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_list_directory_tool(mcp: FastMCP):
    common = dict(tags={"filesystem", "coding"}, annotations={"category": "coding"})
    mcp.tool(**common)(list_directory) 