"""Shell execution infrastructure.

Provides stateless shell command execution for the application layer.
The executor receives cwd as a parameter - state management is handled
by the application/business layer.
"""

from .executor import ShellExecutor
from .utils import detect_python_command, enhance_python_command, prepare_shell_env

__all__ = [
    "ShellExecutor",
    "detect_python_command",
    "enhance_python_command",
    "prepare_shell_env",
]
