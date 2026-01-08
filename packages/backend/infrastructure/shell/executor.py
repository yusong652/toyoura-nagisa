"""Unified shell command executor.

Provides subprocess-based shell command execution with:
- Unified process creation for foreground and background execution
- Timeout handling for foreground execution
- Output processing (combine, normalize, truncate)
- Cross-platform path normalization

The executor is stateless - cwd is passed as a parameter.
State management (current directory, environment) is handled
by the application layer.
"""

import asyncio
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Optional

from backend.infrastructure.mcp.utils.path_normalization import normalize_windows_paths
from backend.infrastructure.mcp.utils.shell import (
    ShellExecutionResult,
    process_shell_output,
    DEFAULT_MAX_OUTPUT_LINES,
)
from .utils import enhance_python_command, prepare_shell_env


# Constants
DEFAULT_TIMEOUT_MS = 120000  # 2 minutes


class ShellExecutorError(Exception):
    """Base exception for shell executor errors."""
    pass


class TimeoutError(ShellExecutorError):
    """Command execution timed out."""
    pass


@dataclass
class BackgroundProcessHandle:
    """Handle for a started background process.

    Contains all information needed by BackgroundProcessManager
    to track and manage the process lifecycle.
    """
    process: subprocess.Popen
    command: str              # Original command
    enhanced_command: str     # Command after enhancement
    cwd: str
    is_python: bool
    start_time: float


class ShellExecutor:
    """Unified shell command executor.

    Provides both foreground (blocking) and background (non-blocking) execution
    through a unified process creation mechanism.

    Example (foreground):
        executor = ShellExecutor()
        result = await executor.execute(
            command="git status",
            cwd="/path/to/repo",
            timeout_ms=30000
        )
        print(result.stdout)

    Example (background):
        executor = ShellExecutor()
        handle = executor.start_background(
            command="npm run dev",
            cwd="/path/to/project"
        )
        # handle.process is the Popen object for lifecycle management
    """

    def __init__(
        self,
        max_output_lines: int = DEFAULT_MAX_OUTPUT_LINES,
        normalize_paths: bool = True,
    ):
        """Initialize the executor.

        Args:
            max_output_lines: Maximum output lines before truncation (foreground only)
            normalize_paths: Whether to normalize Windows paths in output
        """
        self.max_output_lines = max_output_lines
        self.normalize_paths = normalize_paths

    def _prepare_command(self, command: str) -> tuple[str, bool]:
        """Prepare command for execution.

        Performs:
        - Windows path normalization
        - Python command enhancement for unbuffered output
        - Windows UTF-8 encoding setup

        Args:
            command: Raw command string

        Returns:
            Tuple of (enhanced_command, is_python)
        """
        # Normalize Windows paths in command
        normalized_command = normalize_windows_paths(command)

        # Enhance Python commands for unbuffered output
        enhanced_command, is_python = enhance_python_command(normalized_command)

        # On Windows, prepend chcp 65001 to force UTF-8 output from CMD
        if sys.platform == "win32":
            enhanced_command = f"chcp 65001 >nul && {enhanced_command}"

        return enhanced_command, is_python

    def _create_process(
        self,
        command: str,
        cwd: str,
        env: dict,
        line_buffered: bool = False,
    ) -> subprocess.Popen:
        """Create a subprocess with unified configuration.

        This is the single point of Popen creation, ensuring consistent
        configuration across foreground and background execution.

        Args:
            command: The enhanced command to execute
            cwd: Working directory
            env: Environment variables
            line_buffered: If True, use line buffering (for background processes
                          that need real-time output). If False, use default
                          buffering (for foreground processes).

        Returns:
            subprocess.Popen instance
        """
        return subprocess.Popen(
            command,
            shell=True,
            cwd=cwd,
            stdin=subprocess.DEVNULL,  # Prevent blocking on interactive commands
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',  # Replace undecodable bytes instead of raising
            bufsize=1 if line_buffered else -1,  # Line buffered or system default
            env=env,
        )

    async def execute(
        self,
        command: str,
        cwd: str,
        timeout_ms: Optional[int] = None,
        env: Optional[dict] = None,
    ) -> ShellExecutionResult:
        """Execute a shell command (foreground, blocking).

        Blocks until command completes or timeout is reached.

        Args:
            command: The shell command to execute
            cwd: Working directory for command execution
            timeout_ms: Timeout in milliseconds (default: 120000, max: 600000)
            env: Optional environment variables (defaults to current env)

        Returns:
            ShellExecutionResult with stdout, stderr, exit_code, etc.

        Raises:
            TimeoutError: If command exceeds timeout
            ShellExecutorError: If execution fails unexpectedly
        """
        # Set timeout (validation is done at tool layer via Pydantic)
        timeout_ms = timeout_ms if timeout_ms is not None else DEFAULT_TIMEOUT_MS
        timeout_seconds = timeout_ms / 1000.0

        # Prepare command
        enhanced_command, is_python = self._prepare_command(command)

        # Prepare environment
        process_env = prepare_shell_env(base_env=env, force_unbuffered=is_python)

        try:
            return await self._execute_foreground(
                command=enhanced_command,
                original_command=command if enhanced_command != command else None,
                cwd=cwd,
                timeout_seconds=timeout_seconds,
                env=process_env,
            )
        except TimeoutError:
            raise
        except ShellExecutorError:
            raise
        except Exception as e:
            raise ShellExecutorError(f"Command execution failed: {type(e).__name__}: {e}") from e

    async def _execute_foreground(
        self,
        command: str,
        cwd: str,
        timeout_seconds: float,
        env: dict,
        original_command: Optional[str] = None,
    ) -> ShellExecutionResult:
        """Execute command in foreground using native asyncio subprocess.

        Uses asyncio.create_subprocess_shell for true async execution
        without blocking the event loop or consuming thread pool resources.
        """
        start_time = time.time()

        try:
            # Create subprocess using native asyncio
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
                cwd=cwd,
                env=env,
            )

            # Wait for completion with timeout
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                # Kill the process on timeout
                process.kill()
                await process.communicate()  # Clean up
                raise TimeoutError(f"Command timed out after {timeout_seconds:.1f} seconds")

            # Decode output (handle encoding errors gracefully)
            stdout = stdout_bytes.decode('utf-8', errors='replace') if stdout_bytes else ''
            stderr = stderr_bytes.decode('utf-8', errors='replace') if stderr_bytes else ''
            # returncode is guaranteed to be set after communicate() completes
            exit_code: int = process.returncode if process.returncode is not None else -1

        except TimeoutError:
            raise
        except Exception as e:
            raise ShellExecutorError(f"Subprocess execution failed: {type(e).__name__}: {e}") from e

        execution_time = time.time() - start_time

        # Process output (foreground only - background handles its own output)
        process_shell_output(
            stdout=stdout,
            stderr=stderr,
            max_lines=self.max_output_lines,
            normalize_paths=self.normalize_paths,
        )

        return ShellExecutionResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            command=command,
            execution_time=execution_time,
            working_directory=cwd,
            timed_out=False,
            original_command=original_command,
        )

    def start_background(
        self,
        command: str,
        cwd: str,
        env: Optional[dict] = None,
    ) -> BackgroundProcessHandle:
        """Start a background process (non-blocking).

        Creates the process and returns immediately with a handle.
        The caller (BackgroundProcessManager) is responsible for:
        - Managing process lifecycle
        - Reading output streams
        - Cleanup on completion

        Args:
            command: The shell command to execute
            cwd: Working directory for command execution
            env: Optional environment variables (defaults to current env)

        Returns:
            BackgroundProcessHandle with process and metadata

        Raises:
            ShellExecutorError: If process creation fails
        """
        # Prepare command
        enhanced_command, is_python = self._prepare_command(command)

        # Prepare environment - always force unbuffered for background
        # to ensure real-time output availability
        process_env = prepare_shell_env(base_env=env, force_unbuffered=True)

        try:
            process = self._create_process(
                command=enhanced_command,
                cwd=cwd,
                env=process_env,
                line_buffered=True,  # Background uses line buffering for real-time output
            )

            return BackgroundProcessHandle(
                process=process,
                command=command,
                enhanced_command=enhanced_command,
                cwd=cwd,
                is_python=is_python,
                start_time=time.time(),
            )

        except Exception as e:
            raise ShellExecutorError(f"Failed to start background process: {type(e).__name__}: {e}") from e
