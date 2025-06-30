import os
from typing import Dict
from pydantic import Field

# -----------------------------------------------------------------------------
# Workspace helpers (moved from coding.workspace to coding.tools.workspace)
# -----------------------------------------------------------------------------

# We are five directory levels beneath the repo root at
# backend/nagisa_mcp/tools/coding/tools/workspace.py
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../../'))

# Location of the default workspace used by coding-tools
DEFAULT_WORKSPACE = os.path.join(PROJECT_ROOT, 'workspace', 'default')

# Global variable storing the current working directory (within DEFAULT_WORKSPACE)
CURRENT_CODING_CWD = DEFAULT_WORKSPACE

# Ensure the default workspace directory exists on import
os.makedirs(DEFAULT_WORKSPACE, exist_ok=True)


def get_current_workspace() -> Dict[str, str]:
    """Return the current coding workspace and its root directory."""
    return {
        "workspace": CURRENT_CODING_CWD,
        "root": DEFAULT_WORKSPACE,
    }


def change_workspace(
    path: str = Field(
        ..., description="Workspace path to change to. Can be relative or absolute path."
    )
) -> Dict[str, str]:
    """Change the current workspace directory (still confined to DEFAULT_WORKSPACE)."""
    global CURRENT_CODING_CWD

    abs_path = os.path.abspath(os.path.join(DEFAULT_WORKSPACE, path))

    if not abs_path.startswith(DEFAULT_WORKSPACE):
        return {"error": "Path is outside of workspace"}
    if not os.path.exists(abs_path):
        return {"error": f"Directory does not exist: {path}"}
    if not os.path.isdir(abs_path):
        return {"error": f"Path is not a directory: {path}"}

    CURRENT_CODING_CWD = abs_path
    return {
        "status": "success",
        "workspace": abs_path,
        "root": DEFAULT_WORKSPACE,
    }


def validate_path_in_workspace(path: str) -> str | None:
    """Return absolute path if *path* is inside the workspace else None."""
    abs_path = os.path.abspath(os.path.join(DEFAULT_WORKSPACE, path))
    if not abs_path.startswith(DEFAULT_WORKSPACE):
        return None
    return abs_path


# -----------------------------------------------------------------------------
# Registration helpers
# -----------------------------------------------------------------------------

def register_workspace_tools(mcp):
    common_kwargs = dict(tags={"coding"}, annotations={"category": "coding"})
    mcp.tool(**common_kwargs)(get_current_workspace)
    mcp.tool(**common_kwargs)(change_workspace) 