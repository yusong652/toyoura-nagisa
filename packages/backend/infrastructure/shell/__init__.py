"""Shell execution infrastructure.

Provides:
- ShellExecutor: Stateless shell command execution
- ShellStateStorage: Persistent shell state (cwd, etc.)
- BackgroundProcessManager: Background process lifecycle management
- Shared utilities: Python detection, command enhancement, env preparation

The executor receives cwd as a parameter - state management is handled
by ShellStateStorage and the application/business layer.

Note: BackgroundProcessManager is not imported at module level to avoid
circular imports with MCP tools. Import directly from submodule:
    from backend.infrastructure.shell.background_process_manager import get_process_manager
"""

from .executor import ShellExecutor, BackgroundProcessHandle
from .state import ShellState, ShellStateStorage
from .utils import (
    detect_python_command,
    prepare_shell_env,
    MAX_LINE_LENGTH,
    MAX_BUFFER_LINES,
)

__all__ = [
    # Executor
    "ShellExecutor",
    "BackgroundProcessHandle",
    # State
    "ShellState",
    "ShellStateStorage",
    # Utilities
    "detect_python_command",
    "prepare_shell_env",
    # Constants
    "MAX_LINE_LENGTH",
    "MAX_BUFFER_LINES",
]
