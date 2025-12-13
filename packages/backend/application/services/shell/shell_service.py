"""Shell service for user shell command execution.

Business logic layer for user shell commands (CLI `!` prefix):
- Command execution via ShellExecutor
- Working directory state management
- cd command parsing and cwd updates
- LLM context formatting with caveat
"""

import os
import re
from pathlib import Path
from typing import Optional, Tuple

from backend.infrastructure.shell import ShellExecutor, ShellStateStorage
from backend.infrastructure.mcp.utils.shell import (
    ShellExecutionResult,
    format_with_caveat,
)


class ShellService:
    """Service for executing user shell commands.

    Manages shell command execution with persistent working directory state.
    Designed for user-initiated shell commands (CLI `!` prefix).

    Key responsibilities:
    - Execute commands in the current working directory
    - Parse and handle `cd` commands to update cwd
    - Format results for LLM context injection (with caveat)

    Example:
        service = ShellService(workspace_root=Path("/path/to/workspace"))

        # Execute a command
        result, context = await service.execute("ls -la")
        print(result.stdout)

        # Change directory
        result, context = await service.execute("cd src")
        print(service.get_cwd())  # /path/to/workspace/src
    """

    def __init__(self, workspace_root: Path):
        """Initialize the shell service.

        Args:
            workspace_root: Root directory of the workspace
        """
        self.workspace_root = workspace_root
        self._executor = ShellExecutor()
        self._state_storage = ShellStateStorage(workspace_root)

    def get_cwd(self) -> str:
        """Get current working directory.

        Returns:
            Absolute path of current working directory
        """
        return self._state_storage.load().cwd

    def set_cwd(self, path: str) -> str:
        """Set current working directory.

        Args:
            path: New working directory (absolute or relative to current cwd)

        Returns:
            New absolute cwd path

        Raises:
            ValueError: If path doesn't exist or is not a directory
        """
        resolved = self._resolve_path(path)
        if not resolved.exists():
            raise ValueError(f"Directory does not exist: {path}")
        if not resolved.is_dir():
            raise ValueError(f"Path is not a directory: {path}")

        self._state_storage.update_cwd(str(resolved))
        return str(resolved)

    async def execute(
        self,
        command: str,
        timeout_ms: Optional[int] = None,
    ) -> Tuple[ShellExecutionResult, str]:
        """Execute a shell command.

        Handles cd commands specially by updating the persistent cwd state.
        For other commands, executes them in the current working directory.
        Returns result with caveat-formatted context for LLM injection.

        Args:
            command: Shell command to execute
            timeout_ms: Optional timeout in milliseconds

        Returns:
            Tuple of (ShellExecutionResult, llm_context_with_caveat)
            - result: Execution result with stdout, stderr, exit_code
            - context: Formatted string with caveat for LLM context injection
        """
        command = command.strip()
        cwd = self.get_cwd()

        # Handle cd command specially
        cd_target = self._parse_cd_command(command)
        if cd_target is not None:
            return await self._handle_cd(cd_target, command)

        # Execute regular command
        result = await self._executor.execute(
            command=command,
            cwd=cwd,
            timeout_ms=timeout_ms,
        )

        # Format for LLM context with caveat
        context = format_with_caveat(
            command=command,
            stdout=result.stdout,
            stderr=result.stderr,
        )

        return result, context

    def _parse_cd_command(self, command: str) -> Optional[str]:
        """Parse cd command and extract target directory.

        Handles various cd patterns:
        - cd           -> home directory
        - cd ~         -> home directory
        - cd ~/path    -> path relative to home
        - cd path      -> relative path
        - cd /path     -> absolute path
        - cd -         -> previous directory (not supported, returns None)
        - cd .. && cmd -> not a pure cd, returns None

        Args:
            command: Command string to parse

        Returns:
            Target directory if this is a cd command, None otherwise
        """
        # Must start with 'cd' followed by space or end of string
        if not re.match(r'^cd(\s|$)', command):
            return None

        # Check if it's a compound command (cd && something)
        if '&&' in command or '||' in command or ';' in command or '|' in command:
            return None

        # Extract the argument
        parts = command.split(maxsplit=1)
        if len(parts) == 1:
            # Just "cd" - go to home
            return os.path.expanduser("~")

        target = parts[1].strip()

        # Handle quotes
        if (target.startswith('"') and target.endswith('"')) or \
           (target.startswith("'") and target.endswith("'")):
            target = target[1:-1]

        # Handle cd - (previous directory) - not supported
        if target == '-':
            return None

        # Expand ~ and environment variables
        target = os.path.expanduser(target)
        target = os.path.expandvars(target)

        return target

    async def _handle_cd(
        self,
        target: str,
        original_command: str,
    ) -> Tuple[ShellExecutionResult, str]:
        """Handle cd command by updating cwd state.

        Args:
            target: Target directory path
            original_command: Original cd command string

        Returns:
            Tuple of (ShellExecutionResult, llm_context_with_caveat)
        """
        try:
            resolved = self._resolve_path(target)

            if not resolved.exists():
                result = ShellExecutionResult(
                    stdout="",
                    stderr=f"cd: no such file or directory: {target}",
                    exit_code=1,
                    command=original_command,
                    working_directory=self.get_cwd(),
                )
            elif not resolved.is_dir():
                result = ShellExecutionResult(
                    stdout="",
                    stderr=f"cd: not a directory: {target}",
                    exit_code=1,
                    command=original_command,
                    working_directory=self.get_cwd(),
                )
            else:
                # Success - update cwd
                new_cwd = str(resolved)
                self._state_storage.update_cwd(new_cwd)

                result = ShellExecutionResult(
                    stdout="",
                    stderr="",
                    exit_code=0,
                    command=original_command,
                    working_directory=new_cwd,
                )

        except Exception as e:
            result = ShellExecutionResult(
                stdout="",
                stderr=f"cd: {e}",
                exit_code=1,
                command=original_command,
                working_directory=self.get_cwd(),
            )

        context = format_with_caveat(
            command=original_command,
            stdout=result.stdout,
            stderr=result.stderr,
        )

        return result, context

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path relative to current working directory.

        Args:
            path: Path to resolve (absolute or relative)

        Returns:
            Resolved absolute Path
        """
        p = Path(path)
        if p.is_absolute():
            return p.resolve()
        else:
            cwd = Path(self.get_cwd())
            return (cwd / path).resolve()
