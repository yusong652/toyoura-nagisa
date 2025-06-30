"""delete_file tool (split from coding.fs_tools)."""

from pathlib import Path
from typing import Dict
from pydantic import Field
from fastmcp import FastMCP  # type: ignore

from .workspace import validate_path_in_workspace

__all__ = ["delete_file", "register_delete_file_tool"]


def delete_file(path: str = Field(..., description="File path to delete (workspace-relative)")) -> Dict[str, str]:
    """Delete a file inside the workspace."""

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


# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_delete_file_tool(mcp: FastMCP):
    common = dict(tags={"filesystem", "coding"}, annotations={"category": "coding"})
    mcp.tool(**common)(delete_file) 