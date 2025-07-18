"""Split-module implementation of coding tools.

This package hosts individual tool implementations migrated from the legacy
`coding.fs_tools` module so that each tool lives in its own file, mirroring the
structure used by Google's gemini-cli project.
"""

from ..utils.path_security import validate_path_in_workspace
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
from .delete_directory import delete_directory, register_delete_directory_tool
from .read_file import read_file, register_read_file_tool
from .shell_command import run_shell_command, register_shell_command_tool
from .glob import glob, register_glob_tool
from .grep import grep, register_grep_tool
from .replace import replace, register_replace_tool
from ...builtin.google_web_search import google_web_search, register_google_web_search_tool
from . import constants

__all__ = [
    "register_coding_tools",
    "list_directory",
    "read_many_files",
    "write_file",
    "read_file",
    "delete_file",
    "delete_directory",
    "execute_python_script",
    "run_shell_command",
    "glob",
    "grep",
    "replace",
    "google_web_search",
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
    register_delete_directory_tool(mcp)
    register_read_file_tool(mcp)
    register_shell_command_tool(mcp)
    register_glob_tool(mcp)
    register_grep_tool(mcp)
    register_replace_tool(mcp)
    register_google_web_search_tool(mcp) 