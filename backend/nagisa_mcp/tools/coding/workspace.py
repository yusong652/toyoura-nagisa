import os
from typing import Dict
from pydantic import Field

# Define the project root and the default workspace root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../'))
DEFAULT_WORKSPACE = os.path.join(PROJECT_ROOT, 'workspace', 'default')

# Global variable to store the current working directory
CURRENT_CODING_CWD = DEFAULT_WORKSPACE

# Ensure the default workspace directory exists upon startup.
os.makedirs(DEFAULT_WORKSPACE, exist_ok=True)

def get_current_workspace() -> Dict[str, str]:
    """
    Get the current workspace path.
    
    Returns:
        Dict[str, str]: A dictionary containing:
            - workspace: Current workspace path
            - root: Root workspace path
    """
    global CURRENT_CODING_CWD
    return {
        "workspace": CURRENT_CODING_CWD,
        "root": DEFAULT_WORKSPACE
    }

def change_workspace(path: str = Field(..., description="Workspace path to change to. Can be relative or absolute path.")) -> Dict[str, str]:
    """
    Change the current workspace path.
    
    Args:
        path (str): The workspace path to change to. Can be relative or absolute path.
    
    Returns:
        Dict[str, str]: A dictionary containing:
            - status: 'success' if the change was successful
            - workspace: New workspace path
            - root: Root workspace path
            - error: Error message if the change failed
    """
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
        "root": DEFAULT_WORKSPACE
    }

def validate_path_in_workspace(path: str) -> str | None:
    """Return absolute path if *path* is inside ``DEFAULT_WORKSPACE``.

    Supports both workspace-relative paths **and** absolute paths, so long as the
    final resolved location is within the workspace root.
    """

    # Absolute path provided → verify containment
    if os.path.isabs(path):
        abs_path = os.path.abspath(path)
        return abs_path if abs_path.startswith(DEFAULT_WORKSPACE) else None

    # Relative path → resolve against workspace root
    abs_path = os.path.abspath(os.path.join(DEFAULT_WORKSPACE, path))
    return abs_path if abs_path.startswith(DEFAULT_WORKSPACE) else None

def register_workspace_tools(mcp):
    common_kwargs = dict(tags={"coding"}, annotations={"category": "coding"})
    mcp.tool(**common_kwargs)(get_current_workspace)
    mcp.tool(**common_kwargs)(change_workspace) 