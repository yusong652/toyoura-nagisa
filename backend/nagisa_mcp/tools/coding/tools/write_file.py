"""write_file tool (split from coding.fs_tools)."""

from pathlib import Path
from typing import Dict
from pydantic import Field
from fastmcp import FastMCP  # type: ignore

from .workspace import validate_path_in_workspace

__all__ = ["write_file", "register_write_file_tool"]


def write_file(
    path: str = Field(..., description="Path where to write (workspace-relative)"),
    content: str = Field(..., description="Text content to write"),
    encoding: str = Field("utf-8", description="File encoding"),
    append: bool = Field(False, description="Append instead of overwrite"),
) -> Dict[str, str]:
    """Write *content* to a file inside the workspace."""

    abs_path = validate_path_in_workspace(path)
    if abs_path is None:
        return {"status": "error", "error": f"Path is outside of workspace: {path}"}

    mode = "a" if append else "w"
    try:
        Path(abs_path).parent.mkdir(parents=True, exist_ok=True)
        with open(abs_path, mode, encoding=encoding) as fh:
            fh.write(content)
        return {"status": "success", "size": Path(abs_path).stat().st_size}
    except PermissionError:
        return {"status": "error", "error": "Permission denied when writing file"}
    except IsADirectoryError:
        return {"status": "error", "error": "Specified path is a directory, not a file"}
    except OSError as exc:
        return {"status": "error", "error": str(exc)}


# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_write_file_tool(mcp: FastMCP):
    common = dict(tags={"filesystem", "coding"}, annotations={"category": "coding"})
    mcp.tool(**common)(write_file) 