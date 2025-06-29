# (file_io module deprecated; functionality moved into fs_tools)
from .workspace import get_current_workspace, change_workspace, validate_path_in_workspace, register_workspace_tools
from .python_executor import execute_python_script, register_python_executor_tools
from .fs_tools import register_fs_tools, list_directory, read_many_files as read_files, write_file, delete_file

__all__ = [
    'register_coding_tools',
    'list_directory',
    'read_files',
    'write_file',
    'delete_file',
    'get_current_workspace',
    'change_workspace',
    'execute_python_script',
]

def register_coding_tools(mcp):
    """Aggregate registration of all coding-related tools."""
    register_fs_tools(mcp)
    register_workspace_tools(mcp)
    register_python_executor_tools(mcp)
