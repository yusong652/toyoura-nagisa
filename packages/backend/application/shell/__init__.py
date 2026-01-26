"""Shell services for command execution.

Provides business logic for:
- User shell commands (CLI `!` prefix) with cwd management
- Bash tool execution with ctrl+b foreground-to-background support
"""

from .shell_service import ShellService
from .bash_execution_service import BashExecutionService, get_bash_execution_service

__all__ = [
    "ShellService",
    "BashExecutionService",
    "get_bash_execution_service",
]
