# This package has been refactored – individual tools now live in
# `coding.tools.*`. The imports below provide backward-compatibility for external
# callers that still rely on the previous public interface.

from .tools import (
    # Public tool functions
    glob,  # New simplified glob pattern matching tool
    write,
    read,
    bash,
    bash_output,  # Background bash output tool
    kill_shell,   # Background bash kill tool
    grep,
    edit,
    # Registration helper
    register_coding_tools,
)

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
