import os
from typing import List, Dict
from pydantic import Field
from .workspace import validate_path_in_workspace

# All file operations are sandboxed to the default workspace

def list_directory(
    path: str = Field('', description="Directory path to list contents from."),
    show_hidden: bool = Field(False, description="Whether to show hidden files and directories.")
) -> List[Dict[str, str]]:
    """
    List all files and folders in a directory inside the coding workspace.
    
    Parameters:
        path: The directory path to list. If empty, lists the root of the workspace.
        show_hidden: If True, include hidden files (starting with .).
    
    Returns:
        A list of dictionaries, each with:
            - name: File or folder name
            - type: 'file' or 'directory'
            - size: File size in bytes (None for folders)
            - path: Absolute path
        If the path is invalid, returns a list with one dict containing an 'error' key.
    """
    abs_path = validate_path_in_workspace(path)
    if abs_path is None:
        return [{"error": f"Path is outside of workspace: {path}"}]
    if not os.path.exists(abs_path):
        return [{"error": f"Path does not exist: {path}"}]
    if not os.path.isdir(abs_path):
        return [{"error": f"Path is not a directory: {path}"}]
    items = []
    for item in os.listdir(abs_path):
        if not show_hidden and item.startswith('.'):
            continue
        full_path = os.path.join(abs_path, item)
        item_info = {
            "name": item,
            "type": "directory" if os.path.isdir(full_path) else "file",
            "size": os.path.getsize(full_path) if os.path.isfile(full_path) else None,
            "path": full_path
        }
        items.append(item_info)
    return items

def read_file(
    path: str = Field(..., description="Path to the file to read."),
    encoding: str = Field("utf-8", description="File encoding to use.")
) -> Dict[str, str]:
    """
    Read the content of a file in the coding workspace.
    
    Parameters:
        path: The file path to read (relative to workspace or absolute inside workspace).
        encoding: The file encoding (default: utf-8).
    
    Returns:
        A dictionary with:
            - content: The file content as a string
            - size: File size in bytes
            - encoding: The encoding used
        If the path is invalid or not a file, returns a dict with an 'error' key.
    """
    abs_path = validate_path_in_workspace(path)
    if abs_path is None:
        return {"error": f"Path is outside of workspace: {path}"}
    if not os.path.exists(abs_path):
        return {"error": f"File does not exist: {path}"}
    if not os.path.isfile(abs_path):
        return {"error": f"Path is not a file: {path}"}
    try:
        with open(abs_path, 'r', encoding=encoding) as f:
            content = f.read()
        return {
            "content": content,
            "size": os.path.getsize(abs_path),
            "encoding": encoding
        }
    except Exception as e:
        return {"error": f"Failed to read file: {str(e)}"}

def write_file(
    path: str = Field(..., description="Path where to write the file."),
    content: str = Field(..., description="Content to write to the file."),
    encoding: str = Field("utf-8", description="File encoding to use."),
    append: bool = Field(False, description="Whether to append to existing file.")
) -> Dict[str, str]:
    """
    Write content to a file in the coding workspace. Creates the file if it does not exist.
    
    Parameters:
        path: The file path to write (relative to workspace or absolute inside workspace).
        content: The text content to write to the file.
        encoding: The file encoding (default: utf-8).
        append: If True, append to the file. If False, overwrite the file.
    
    Returns:
        A dictionary with:
            - status: 'success' if write succeeded
            - message: Description of the operation
            - size: File size in bytes after writing
        If the path is invalid, returns a dict with an 'error' key.
    """
    abs_path = validate_path_in_workspace(path)
    if abs_path is None:
        return {"error": f"Path is outside of workspace: {path}"}
    try:
        mode = 'a' if append else 'w'
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, mode, encoding=encoding) as f:
            f.write(content)
        return {
            "status": "success",
            "message": f"Content {'appended to' if append else 'written to'} file: {path}",
            "size": os.path.getsize(abs_path)
        }
    except Exception as e:
        return {"error": f"Failed to write file: {str(e)}"}

def delete_file(
    path: str = Field(..., description="Path to the file to delete.")
) -> Dict[str, str]:
    """
    Delete a file in the coding workspace.
    
    Parameters:
        path: The file path to delete (relative to workspace or absolute inside workspace).
    
    Returns:
        A dictionary with:
            - status: 'success' if deletion succeeded
            - message: Description of the operation
        If the path is invalid or not a file, returns a dict with an 'error' key.
    """
    abs_path = validate_path_in_workspace(path)
    if abs_path is None:
        return {"error": f"Path is outside of workspace: {path}"}
    if not os.path.exists(abs_path):
        return {"error": f"File does not exist: {path}"}
    if not os.path.isfile(abs_path):
        return {"error": f"Path is not a file: {path}"}
    try:
        os.remove(abs_path)
        return {
            "status": "success",
            "message": f"File deleted: {path}"
        }
    except Exception as e:
        return {"error": f"Failed to delete file: {str(e)}"}

def register_file_io_tools(mcp):
    mcp.tool()(list_directory)
    mcp.tool()(read_file)
    mcp.tool()(write_file)
    mcp.tool()(delete_file) 