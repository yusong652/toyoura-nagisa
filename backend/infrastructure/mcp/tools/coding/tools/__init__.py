"""Split-module implementation of coding tools.

This package hosts individual tool implementations migrated from the legacy
`coding.fs_tools` module so that each tool lives in its own file, mirroring the
structure used by Google's gemini-cli project.
"""

from ..utils.path_security import validate_path_in_workspace
from .read_many_files import (
    read_many_files,
    register_read_many_files_tool,
)
from .write_file import write_file, register_write_file_tool
from .ls import ls, register_ls_tool
from .read_file import read_file, register_read_file_tool
from .shell_command import run_shell_command, register_shell_command_tool
from .glob import glob, register_glob_tool  # New simplified glob tool
from .grep import grep, register_grep_tool
from .replace import replace, register_replace_tool
from ...builtin.web_search import web_search, register_web_search_tool
from . import constants

__all__ = [
    "register_coding_tools",
    "ls",
    "glob",
    "read_many_files",
    "write_file",
    "read_file",
    "run_shell_command",
    "grep",
    "replace",
    "web_search",
]

def register_coding_tools(mcp):
    """Aggregate registration of all coding tools.

    This helper keeps external code unchanged: instead of registering each tool
    one by one, callers can simply invoke `register_coding_tools(mcp)` once.
    """
    # workspace tools removed (stateful cd no longer needed)
    register_read_many_files_tool(mcp)
    register_write_file_tool(mcp)
    register_ls_tool(mcp)  # New simplified ls tool
    register_read_file_tool(mcp)
    register_shell_command_tool(mcp)
    register_glob_tool(mcp)  # New simplified glob tool
    register_grep_tool(mcp)
    register_replace_tool(mcp)
    register_web_search_tool(mcp) 