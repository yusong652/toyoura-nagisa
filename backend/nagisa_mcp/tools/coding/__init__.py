# This package has been refactored – individual tools now live in
# `coding.tools.*`. The imports below provide backward-compatibility for external
# callers that still rely on the previous public interface (e.g. `from
# nagisa_mcp.tools.coding import list_directory`).

from .tools import (
    # Public tool functions
    list_directory,
    read_many_files as read_files,
    write_file,
    delete_file,
    get_current_workspace,
    change_workspace,
    execute_python_script,
    validate_path_in_workspace,
    # Registration helper
    register_coding_tools as _register_coding_tools_new,
)

# -----------------------------------------------------------------------------
# Public re-exports
# -----------------------------------------------------------------------------

__all__ = [
    'register_coding_tools',
    'list_directory',
    'read_files',
    'write_file',
    'delete_file',
    'get_current_workspace',
    'change_workspace',
    'execute_python_script',
    'validate_path_in_workspace',
]

# -----------------------------------------------------------------------------
# Backwards-compatible registration wrapper
# -----------------------------------------------------------------------------

def register_coding_tools(mcp):
    """Aggregate registration of all coding-related tools (new implementation)."""
    _register_coding_tools_new(mcp)
