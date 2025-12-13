"""Stateless shell command executor.

Provides subprocess-based shell command execution with:
- Timeout handling
- Output processing (combine, normalize, truncate)
- Cross-platform path normalization

The executor is stateless - cwd is passed as a parameter.
State management (current directory, environment) is handled
by the application layer.
"""

import subprocess
import time
from pathlib import Path
from typing import Optional

from backend.infrastructure.mcp.utils.path_normalization import normalize_windows_paths
from backend.infrastructure.mcp.utils.shell import (
    ShellExecutionResult,
    process_shell_output,
    DEFAULT_MAX_OUTPUT_SIZE,
)
from .utils import enhance_python_command, prepare_shell_env


# Constants
DEFAULT_TIMEOUT_MS = 120000  # 2 minutes
MAX_TIMEOUT_MS = 600000      # 10 minutes
MIN_TIMEOUT_MS = 1000        # 1 second


class ShellExecutorError(Exception):
    """Base exception for shell executor errors."""
    pass


class TimeoutError(ShellExecutorError):
    """Command execution timed out."""
    pass


class ValidationError(ShellExecutorError):
    """Invalid parameters."""
    pass


class ShellExecutor:
    """Stateless shell command executor.

    Executes shell commands via subprocess with timeout and output processing.
    Each execution is independent - no state is maintained between calls.

    Example:
        executor = ShellExecutor()
        result = await executor.execute(
            command="git status",
            cwd="/path/to/repo",
            timeout_ms=30000
        )
        print(result.stdout)
    """

    def __init__(
        self,
        max_output_size: int = DEFAULT_MAX_OUTPUT_SIZE,
        normalize_paths: bool = True,
    ):
        """Initialize the executor.

        Args:
            max_output_size: Maximum output size before truncation
            normalize_paths: Whether to normalize Windows paths in output
        """
        self.max_output_size = max_output_size
        self.normalize_paths = normalize_paths

    async def execute(
        self,
        command: str,
        cwd: str,
        timeout_ms: Optional[int] = None,
        env: Optional[dict] = None,
    ) -> ShellExecutionResult:
        """Execute a shell command.

        Args:
            command: The shell command to execute
            cwd: Working directory for command execution
            timeout_ms: Timeout in milliseconds (default: 120000, max: 600000)
            env: Optional environment variables (defaults to current env)

        Returns:
            ShellExecutionResult with stdout, stderr, exit_code, etc.

        Raises:
            ValidationError: If command is empty or timeout is invalid
            TimeoutError: If command exceeds timeout
            ShellExecutorError: If execution fails unexpectedly
        """
        # Validate command
        if not command or not command.strip():
            raise ValidationError("Command cannot be empty")

        # Validate and set timeout
        timeout_ms = timeout_ms if timeout_ms is not None else DEFAULT_TIMEOUT_MS
        if timeout_ms > MAX_TIMEOUT_MS:
            raise ValidationError(f"Timeout cannot exceed {MAX_TIMEOUT_MS}ms (10 minutes)")
        if timeout_ms < MIN_TIMEOUT_MS:
            raise ValidationError(f"Timeout must be at least {MIN_TIMEOUT_MS}ms (1 second)")
        timeout_seconds = timeout_ms / 1000.0

        # Validate cwd
        cwd_path = Path(cwd)
        if not cwd_path.exists():
            raise ValidationError(f"Working directory does not exist: {cwd}")
        if not cwd_path.is_dir():
            raise ValidationError(f"Path is not a directory: {cwd}")

        # Normalize Windows paths in command
        normalized_command = normalize_windows_paths(command)

        # Enhance Python commands for unbuffered output
        enhanced_command, is_python = enhance_python_command(normalized_command)

        # Prepare environment with shell-friendly settings
        process_env = prepare_shell_env(base_env=env, force_unbuffered=is_python)

        try:
            return await self._execute_subprocess(
                command=enhanced_command,
                original_command=command if enhanced_command != command else None,
                cwd=str(cwd_path),
                timeout_seconds=timeout_seconds,
                env=process_env,
            )
        except TimeoutError:
            raise
        except Exception as e:
            raise ShellExecutorError(f"Command execution failed: {e}") from e

    async def _execute_subprocess(
        self,
        command: str,
        cwd: str,
        timeout_seconds: float,
        env: dict,
        original_command: Optional[str] = None,
    ) -> ShellExecutionResult:
        """Execute command via subprocess.

        This is separated to allow potential future async implementations.
        Currently uses synchronous subprocess for compatibility.
        """
        start_time = time.time()

        process = subprocess.Popen(
            command,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
            exit_code = process.returncode
            execution_time = time.time() - start_time

        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()  # Clean up
            raise TimeoutError(f"Command timed out after {timeout_seconds:.1f} seconds")

        # Process output
        combined_output = process_shell_output(
            stdout=stdout,
            stderr=stderr,
            max_size=self.max_output_size,
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
