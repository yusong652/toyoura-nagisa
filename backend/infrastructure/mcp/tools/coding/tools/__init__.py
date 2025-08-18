"""Split-module implementation of coding tools.

This package hosts individual tool implementations migrated from the legacy
`coding.fs_tools` module so that each tool lives in its own file, mirroring the
structure used by Google's gemini-cli project.
"""

from ..utils.path_security import validate_path_in_workspace
from .write import write, register_write_tool
from .ls import ls, register_ls_tool
from .read import read, register_read_tool
from .bash import bash, register_bash_tool
from .glob import glob, register_glob_tool  # New simplified glob tool
from .grep import grep, register_grep_tool
from .edit import edit, register_edit_tool
from ...builtin.web_search import web_search, register_web_search_tool
from . import constants

__all__ = [
    "register_coding_tools",
    "ls",
    "glob",
    "write",
    "read",
    "bash",
    "grep",
    "edit",
    "web_search",
]

def register_coding_tools(mcp):
    """Aggregate registration of all coding tools.

    This helper keeps external code unchanged: instead of registering each tool
    one by one, callers can simply invoke `register_coding_tools(mcp)` once.
    """
    # workspace tools removed (stateful cd no longer needed)
    register_write_tool(mcp)
    register_ls_tool(mcp)  # New simplified ls tool
    register_read_tool(mcp)
    register_bash_tool(mcp)
    register_glob_tool(mcp)  # New simplified glob tool
    register_grep_tool(mcp)
    register_edit_tool(mcp)
    register_web_search_tool(mcp) 