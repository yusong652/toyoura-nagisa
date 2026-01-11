"""Shell service for user shell command execution.

Business logic layer for user shell commands (CLI `!` prefix):
- Command execution via ShellExecutor
- Working directory state management
- cd command parsing and cwd updates
- LLM context formatting with caveat
- Foreground execution with Ctrl+B support
"""

import os
import re
from pathlib import Path
from typing import Optional, Tuple, Union

from backend.infrastructure.shell import ShellExecutor, ShellStateStorage
from backend.infrastructure.shell.executor import (
    ForegroundExecutionHandle,
    MoveToBackgroundRequest,
)
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

        # Check if command contains cd (compound command like "cd dir && ls")
        has_cd = self._contains_cd_command(command)

        # For compound commands with cd, append pwd to track final directory
        actual_command = command
        if has_cd:
            actual_command = f"{command} && pwd"

        # Execute command
        result = await self._executor.execute(
            command=actual_command,
            cwd=cwd,
            timeout_ms=timeout_ms,
        )

        # If compound command with cd succeeded, extract pwd and update cwd
        stdout = result.stdout
        if has_cd and result.exit_code == 0 and stdout:
            lines = stdout.rstrip('\n').split('\n')
            if lines:
                # Last line is pwd output
                pwd_output = lines[-1]
                if pwd_output.startswith('/') and os.path.isdir(pwd_output):
                    self._state_storage.update_cwd(pwd_output)
                    # Remove pwd output from stdout
                    stdout = '\n'.join(lines[:-1])
                    if stdout:
                        stdout += '\n'

        # Create result with cleaned stdout
        clean_result = ShellExecutionResult(
            stdout=stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            command=command,  # Original command, not the one with pwd
            working_directory=self.get_cwd(),
        )

        # Format for LLM context with caveat
        context = format_with_caveat(
            command=command,
            stdout=clean_result.stdout,
            stderr=clean_result.stderr,
        )

        return clean_result, context

    def _contains_cd_command(self, command: str) -> bool:
        """Check if command contains a cd command (for compound commands).

        Detects cd in compound commands like:
        - cd dir && ls
        - cd dir; cat file
        - cd dir || echo "failed"

        Args:
            command: Command string to check

        Returns:
            True if command contains cd, False otherwise
        """
        # Check for cd at start or after command separators
        # Pattern: start of string or separator, then 'cd' followed by space or separator
        return bool(re.search(r'(^|&&|\|\||;|\|)\s*cd(\s|$|&&|\|\||;|\|)', command))

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

    # =====================
    # Foreground Execution (Ctrl+B support)
    # =====================

    async def start_foreground(
        self,
        command: str,
        timeout_ms: Optional[int] = None,
    ) -> Tuple[Optional[ForegroundExecutionHandle], Optional[Tuple[ShellExecutionResult, str]], str, bool]:
        """Start a foreground execution with Ctrl+B support.

        For pure `cd` commands, returns result immediately (no handle needed).
        For other commands, returns a ForegroundExecutionHandle for async wait.

        Args:
            command: Shell command to execute
            timeout_ms: Optional timeout in milliseconds

        Returns:
            Tuple of (handle, immediate_result, actual_command, has_cd):
            - handle: ForegroundExecutionHandle if process started, None for pure cd
            - immediate_result: (ShellExecutionResult, context) for pure cd, None otherwise
            - actual_command: The command being executed (may have && pwd appended)
            - has_cd: Whether command contains cd (for cwd update after completion)
        """
        command = command.strip()
        cwd = self.get_cwd()

        # Handle pure cd command specially (no process needed)
        cd_target = self._parse_cd_command(command)
        if cd_target is not None:
            result, context = await self._handle_cd(cd_target, command)
            return None, (result, context), command, False

        # Check if command contains cd (compound command)
        has_cd = self._contains_cd_command(command)

        # For compound commands with cd, append pwd to track final directory
        actual_command = command
        if has_cd:
            actual_command = f"{command} && pwd"

        # Start foreground process
        handle = self._executor.start_foreground(
            command=actual_command,
            cwd=cwd,
            timeout_ms=timeout_ms,
        )

        return handle, None, actual_command, has_cd

    def process_foreground_result(
        self,
        result: ShellExecutionResult,
        original_command: str,
        has_cd: bool,
    ) -> Tuple[ShellExecutionResult, str]:
        """Process the result from foreground execution.

        Handles cwd updates for compound cd commands and formats the result.

        Args:
            result: Raw execution result
            original_command: The original command (without && pwd)
            has_cd: Whether the command contained cd

        Returns:
            Tuple of (cleaned_result, llm_context_with_caveat)
        """
        stdout = result.stdout

        # If compound command with cd succeeded, extract pwd and update cwd
        if has_cd and result.exit_code == 0 and stdout:
            lines = stdout.rstrip('\n').split('\n')
            if lines:
                # Last line is pwd output
                pwd_output = lines[-1]
                if pwd_output.startswith('/') and os.path.isdir(pwd_output):
                    self._state_storage.update_cwd(pwd_output)
                    # Remove pwd output from stdout
                    stdout = '\n'.join(lines[:-1])
                    if stdout:
                        stdout += '\n'

        # Create result with cleaned stdout
        clean_result = ShellExecutionResult(
            stdout=stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            command=original_command,
            working_directory=self.get_cwd(),
        )

        # Format for LLM context with caveat
        context = format_with_caveat(
            command=original_command,
            stdout=clean_result.stdout,
            stderr=clean_result.stderr,
        )

        return clean_result, context
