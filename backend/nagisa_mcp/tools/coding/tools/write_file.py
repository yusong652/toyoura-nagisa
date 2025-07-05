"""Filesystem helper tools — *write_file* implementation.

This module exposes a single FastMCP-compatible tool that writes UTF-8 text
files inside the workspace directory. The only public symbol meant to be
registered is :pyfunc:`write_file`.
"""

from pathlib import Path
from typing import Dict, Any

from pydantic import Field
from fastmcp import FastMCP  # type: ignore

from .workspace import validate_path_in_workspace, WORKSPACE_ROOT
from .config import get_tools_config

__all__ = ["write_file", "register_write_file_tool"]


def _make_error(msg: str) -> Dict[str, Any]:
    """Helper to build a standardized error payload."""

    return {
        "status": "error",
        "error": msg,
        "llm_content": f"Error: {msg}",
        "return_display": f"❌ {msg}",
    }


def write_file(
    path: str = Field(..., description="Path (relative to workspace) to write to."),
    content: str = Field(..., description="Text content to write"),
    encoding: str = Field("utf-8", description="File encoding"),
    append: bool = Field(False, description="Append instead of overwrite"),
) -> Dict[str, Any]:
    """Write *content* to ``path`` (relative to workspace root).

    Returns
    -------
    Dict
        status          : "success" | "error"
        llm_content     : str – factual summary for LLM history
        return_display  : str – short user-facing message
        size            : int – final file size in bytes (success only)
        path            : str – absolute path to the written file (success only)
        error           : str – error details (error only)
    """

    abs_path = validate_path_in_workspace(path)
    if abs_path is None:
        return _make_error(f"Path is outside of workspace: {path}")

    mode = "a" if append else "w"
    try:
        abs_p = Path(abs_path)
        abs_p.parent.mkdir(parents=True, exist_ok=True)
        with abs_p.open(mode, encoding=encoding) as fh:
            fh.write(content)

        size = abs_p.stat().st_size
        rel_display = abs_p.relative_to(WORKSPACE_ROOT)

        llm_msg = (
            f"Wrote {size} bytes to {rel_display} (append={append}, encoding={encoding})"
        )
        display = llm_msg if get_tools_config().debug_mode else "File written successfully."

        return {
            "status": "success",
            "size": size,
            "path": str(abs_p),
            "llm_content": llm_msg,
            "return_display": display,
        }
    except PermissionError:
        return _make_error("Permission denied when writing file")
    except IsADirectoryError:
        return _make_error("Specified path is a directory, not a file")
    except OSError as exc:
        return _make_error(str(exc))


# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_write_file_tool(mcp: FastMCP):
    common = dict(tags={"filesystem", "coding"}, annotations={"category": "coding"})
    mcp.tool(**common)(write_file) 