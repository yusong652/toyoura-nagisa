"""Split-module implementation of coding tools.

This package hosts individual tool implementations migrated from the legacy
`coding.fs_tools` module so that each tool lives in its own file, mirroring the
structure used by Google's gemini-cli project.
"""

from .write import write, register_write_tool
from .read import read, register_read_tool
from .bash import bash, register_bash_tool
from .bash_output import bash_output, register_bash_output_tool
from .kill_shell import kill_shell, register_kill_shell_tool
from .glob import glob, register_glob_tool  # New simplified glob tool
from .grep import grep, register_grep_tool
from .edit import edit, register_edit_tool

__all__ = [
    "register_coding_tools",
    "glob",
    "write",
    "read",
    "bash",
    "bash_output",
    "kill_shell",
    "grep",
    "edit",
]

def register_coding_tools(mcp):
    """Aggregate registration of all coding tools.

    This helper keeps external code unchanged: instead of registering each tool
    one by one, callers can simply invoke `register_coding_tools(mcp)` once.
    """
    # workspace tools removed (stateful cd no longer needed)
    register_write_tool(mcp)
    register_read_tool(mcp)
    register_bash_tool(mcp)
    register_bash_output_tool(mcp)  # Background bash output tool
    register_kill_shell_tool(mcp)   # Background bash kill tool
    register_glob_tool(mcp)  # New simplified glob tool
    register_grep_tool(mcp)
    register_edit_tool(mcp) 