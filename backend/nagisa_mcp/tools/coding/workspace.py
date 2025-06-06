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

def validate_path_in_workspace(path: str) -> str:
    """
    Validate that a path is within the workspace.
    
    Args:
        path (str): The path to validate.
    
    Returns:
        str: The absolute path if valid, None if invalid.
    """
    abs_path = os.path.abspath(os.path.join(DEFAULT_WORKSPACE, path))
    if not abs_path.startswith(DEFAULT_WORKSPACE):
        return None
    return abs_path

def register_workspace_tools(mcp):
    mcp.tool()(get_current_workspace)
    mcp.tool()(change_workspace) 