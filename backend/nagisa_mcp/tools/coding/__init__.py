from .file_io import list_directory, read_file, write_file, delete_file, register_file_io_tools
from .workspace import get_current_workspace, change_workspace, validate_path_in_workspace, register_workspace_tools
from .python_executor import execute_python_script, register_python_executor_tools

__all__ = [
    'get_or_create_session',
    'validate_path_in_workspace',
    'register_coding_tools',
    'list_directory',
    'read_file',
    'write_file',
    'delete_file',
    'get_current_workspace',
    'change_workspace',
    'execute_python_script',
]

def register_coding_tools(mcp):
    register_file_io_tools(mcp)
    register_workspace_tools(mcp)
    register_python_executor_tools(mcp)
