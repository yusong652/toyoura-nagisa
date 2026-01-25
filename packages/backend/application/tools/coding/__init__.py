# This package has been refactored – individual tools now live in
"""Coding tools package."""

from .glob import glob, register_glob_tool
from .write import write, register_write_tool
from .read import read, register_read_tool
from .bash import bash, register_bash_tool
from .bash_output import bash_output, register_bash_output_tool
from .kill_shell import kill_shell, register_kill_shell_tool
from .grep import grep, register_grep_tool
from .edit import edit, register_edit_tool

# -----------------------------------------------------------------------------
# Public re-exports
# -----------------------------------------------------------------------------

__all__ = [
    'register_coding_tools',
    'glob',  # New simplified glob pattern matching tool
    'write',
    'read',
    'bash',
    'bash_output',  # Background bash output tool
    'kill_shell',   # Background bash kill tool
    'grep',
    'edit',
]


def register_coding_tools(registrar):
    """Aggregate registration of all coding tools."""
    # workspace tools removed (stateful cd no longer needed)
    register_write_tool(registrar)
    register_read_tool(registrar)
    register_bash_tool(registrar)
    register_bash_output_tool(registrar)
    register_kill_shell_tool(registrar)
    register_glob_tool(registrar)
    register_grep_tool(registrar)
    register_edit_tool(registrar)
