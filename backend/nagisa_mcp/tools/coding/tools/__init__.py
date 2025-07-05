"""Split-module implementation of coding tools.

This package hosts individual tool implementations migrated from the legacy
`coding.fs_tools` module so that each tool lives in its own file, mirroring the
structure used by Google's gemini-cli project.
"""

from .workspace import validate_path_in_workspace
from .python_executor import (
    execute_python_script,
    register_python_executor_tools,
)
from .read_many_files import (
    read_many_files,
    register_read_many_files_tool,
)
from .write_file import write_file, register_write_file_tool
from .list_directory import list_directory, register_list_directory_tool
from .delete_file import delete_file, register_delete_file_tool
from .read_file import read_file, register_read_file_tool
from .shell_command import run_shell_command, register_shell_command_tool

# Backwards-compatibility alias (old name used in some places)
read_files = read_many_files

__all__ = [
    "register_coding_tools",
    "list_directory",
    "read_many_files",
    "read_files",
    "write_file",
    "read_file",
    "delete_file",
    "execute_python_script",
    "run_shell_command",
]

def register_coding_tools(mcp):
    """Aggregate registration of all coding tools.

    This helper keeps external code unchanged: instead of registering each tool
    one by one, callers can simply invoke `register_coding_tools(mcp)` once.
    """
    # workspace tools removed (stateful cd no longer needed)
    register_python_executor_tools(mcp)
    register_read_many_files_tool(mcp)
    register_write_file_tool(mcp)
    register_list_directory_tool(mcp)
    register_delete_file_tool(mcp)
    register_read_file_tool(mcp)
    register_shell_command_tool(mcp) 