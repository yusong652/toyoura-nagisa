"""Shell service for user shell command execution.

Provides business logic for:
- Executing shell commands with cwd management
- Parsing cd commands to update working directory
- Formatting results for LLM context injection
"""

from .shell_service import ShellService

__all__ = ["ShellService"]
