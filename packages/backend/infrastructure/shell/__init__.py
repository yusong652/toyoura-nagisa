"""Shell execution infrastructure.

Provides:
- ShellExecutor: Stateless shell command execution
- ShellStateStorage: Persistent shell state (cwd, etc.)
- Shared utilities: Python detection, command enhancement, env preparation

The executor receives cwd as a parameter - state management is handled
by ShellStateStorage and the application/business layer.
"""

from .executor import ShellExecutor
from .state import ShellState, ShellStateStorage
from .utils import detect_python_command, enhance_python_command, prepare_shell_env

__all__ = [
    # Executor
    "ShellExecutor",
    # State
    "ShellState",
    "ShellStateStorage",
    # Utilities
    "detect_python_command",
    "enhance_python_command",
    "prepare_shell_env",
]
