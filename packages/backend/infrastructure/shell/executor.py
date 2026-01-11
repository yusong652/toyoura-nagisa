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
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .executor import ShellExecutor

from backend.infrastructure.mcp.utils.path_normalization import normalize_windows_paths
from backend.infrastructure.mcp.utils.shell import (
    ShellExecutionResult,
    process_shell_output,
    DEFAULT_MAX_OUTPUT_CHARS,
)
from .utils import prepare_shell_env

# Default timeout for foreground execution (30 seconds)
DEFAULT_TIMEOUT_MS = 30000


def _kill_process_group(process: subprocess.Popen) -> None:
    """Kill a process and all its children using process group.

    On Unix with start_new_session=True, we can kill all children
    by killing the process group.

    On Windows, uses taskkill /T to kill the process tree.
    """
    if process.poll() is not None:
        return  # Already dead

    try:
        if sys.platform == "win32":
            # Windows: Use taskkill with /T flag to kill process tree
            # /F = force, /T = tree (kill child processes), /PID = process ID
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                capture_output=True,
                timeout=5,
            )
        else:
            # Unix: Kill the entire process group with SIGKILL
            pgid = os.getpgid(process.pid)
            os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, OSError, subprocess.TimeoutExpired):
        # Process already terminated or taskkill timed out
        pass


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
    prepared_command: str     # Command after preparation (path normalization, etc.)
    cwd: str
    start_time: float


@dataclass
class MoveToBackgroundRequest:
    """Request to move a foreground process to background.

    Returned by ForegroundExecutionHandle.wait() when user triggers ctrl+b.
    This is a normal control flow result, not an exception.
    """
    handle: "ForegroundExecutionHandle"


@dataclass
class ForegroundExecutionHandle:
    """Handle for a foreground process with interruptible wait.

    Supports ctrl+b to move the process to background without killing it.
    The wait() method returns either ShellExecutionResult (normal completion)
    or MoveToBackgroundRequest (user requested background conversion).
    """
    process: subprocess.Popen
    command: str              # Original command
    prepared_command: str     # Command after preparation
    cwd: str
    start_time: float
    timeout_seconds: float
    process_env: dict
    max_output_chars: int
    normalize_paths: bool
    _move_to_bg_event: asyncio.Event = field(default_factory=asyncio.Event)

    def request_move_to_background(self) -> None:
        """Signal the wait() method to return MoveToBackgroundRequest.

        Called by ForegroundTaskRegistry when user presses ctrl+b.
        """
        self._move_to_bg_event.set()

    def to_background_handle(self) -> BackgroundProcessHandle:
        """Convert this handle to a BackgroundProcessHandle for adoption."""
        return BackgroundProcessHandle(
            process=self.process,
            command=self.command,
            prepared_command=self.prepared_command,
            cwd=self.cwd,
            start_time=self.start_time,
        )

    async def wait(self) -> Union[ShellExecutionResult, MoveToBackgroundRequest]:
        """Wait for process completion or move-to-background signal.

        Returns:
            ShellExecutionResult: Process completed normally
            MoveToBackgroundRequest: User pressed ctrl+b

        Raises:
            TimeoutError: Process exceeded timeout
            ShellExecutorError: Unexpected execution error
        """
        # Task 1: Wait for process completion
        wait_task = asyncio.create_task(
            asyncio.to_thread(self.process.communicate)
        )
        # Task 2: Wait for move-to-background signal
        signal_task = asyncio.create_task(
            self._move_to_bg_event.wait()
        )

        try:
            done, pending = await asyncio.wait(
                [wait_task, signal_task],
                timeout=self.timeout_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Case 1: Move-to-background signal received
            if signal_task in done:
                wait_task.cancel()
                return MoveToBackgroundRequest(handle=self)

            # Case 2: Timeout (neither task completed)
            if not done:
                signal_task.cancel()
                _kill_process_group(self.process)
                # Wait for the thread to finish (communicate will return quickly after kill)
                try:
                    await asyncio.wait_for(wait_task, timeout=5.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    wait_task.cancel()
                raise TimeoutError(f"Command timed out after {self.timeout_seconds:.1f} seconds")

            # Case 3: Process completed normally
            signal_task.cancel()
            stdout, stderr = wait_task.result()

            # With text mode (from _create_process), output is already str
            stdout = stdout if stdout else ''
            stderr = stderr if stderr else ''
            exit_code: int = self.process.returncode if self.process.returncode is not None else -1

            execution_time = time.time() - self.start_time

            process_shell_output(
                stdout=stdout,
                stderr=stderr,
                max_chars=self.max_output_chars,
                normalize_paths=self.normalize_paths,
            )

            return ShellExecutionResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                command=self.prepared_command,
                execution_time=execution_time,
                working_directory=self.cwd,
                timed_out=False,
                original_command=self.command if self.prepared_command != self.command else None,
            )

        except TimeoutError:
            raise
        except Exception as e:
            signal_task.cancel()
            if self.process.poll() is None:
                _kill_process_group(self.process)
                # Wait for the thread to finish
                try:
                    await asyncio.wait_for(wait_task, timeout=5.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass
            wait_task.cancel()
            raise ShellExecutorError(f"Command execution failed: {type(e).__name__}: {e}") from e


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
        max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
        normalize_paths: bool = True,
    ):
        """Initialize the executor.

        Args:
            max_output_chars: Maximum output characters before truncation (foreground only)
            normalize_paths: Whether to normalize Windows paths in output
        """
        self.max_output_chars = max_output_chars
        self.normalize_paths = normalize_paths

    def _prepare_command(self, command: str) -> str:
        """Prepare command for execution.

        Performs:
        - Windows path normalization
        - Windows UTF-8 encoding setup

        Args:
            command: Raw command string

        Returns:
            Prepared command string
        """
        # Normalize Windows paths in command
        prepared_command = normalize_windows_paths(command)

        # On Windows, prepend chcp 65001 to force UTF-8 output from CMD
        if sys.platform == "win32":
            prepared_command = f"chcp 65001 >nul && {prepared_command}"

        return prepared_command

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
        # On Unix, start_new_session=True creates a new process group
        # This allows us to kill all child processes with os.killpg()
        popen_kwargs: dict = {
            "shell": True,
            "cwd": cwd,
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "bufsize": 1 if line_buffered else -1,
            "env": env,
        }

        # Enable process group for proper cleanup on Unix systems
        if sys.platform != "win32":
            popen_kwargs["start_new_session"] = True

        return subprocess.Popen(command, **popen_kwargs)

    async def execute(
        self,
        command: str,
        cwd: str,
        timeout_ms: Optional[int] = None,
        env: Optional[dict] = None,
    ) -> ShellExecutionResult:
        """Execute a shell command (foreground, blocking).

        Blocks until command completes or timeout is reached.
        Uses subprocess.Popen with asyncio.to_thread for cross-platform
        compatibility (works on Windows with both ProactorEventLoop
        and SelectorEventLoop).

        Args:
            command: The shell command to execute
            cwd: Working directory for command execution
            timeout_ms: Timeout in milliseconds (defaults to DEFAULT_TIMEOUT_MS)
            env: Optional environment variables (defaults to current env)

        Returns:
            ShellExecutionResult with stdout, stderr, exit_code, etc.

        Raises:
            TimeoutError: If command exceeds timeout
            ShellExecutorError: If execution fails unexpectedly
        """
        timeout_seconds = (timeout_ms or DEFAULT_TIMEOUT_MS) / 1000.0
        prepared_command = self._prepare_command(command)
        original_command = command if prepared_command != command else None
        process_env = prepare_shell_env(base_env=env, force_unbuffered=True)

        start_time = time.time()
        process: Optional[subprocess.Popen] = None

        try:
            process = subprocess.Popen(
                prepared_command,
                shell=True,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=process_env,
            )

            # Wait for completion with timeout using asyncio.to_thread
            # This runs communicate() in a thread pool, freeing the event loop
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    asyncio.to_thread(process.communicate),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                _kill_process_group(process)
                process.communicate()  # Clean up (blocking, but process is dead)
                raise TimeoutError(f"Command timed out after {timeout_seconds:.1f} seconds")

            # Decode output (handle encoding errors gracefully)
            stdout = stdout_bytes.decode('utf-8', errors='replace') if stdout_bytes else ''
            stderr = stderr_bytes.decode('utf-8', errors='replace') if stderr_bytes else ''
            exit_code: int = process.returncode if process.returncode is not None else -1

        except TimeoutError:
            raise
        except Exception as e:
            if process is not None and process.poll() is None:
                _kill_process_group(process)
                process.communicate()
            raise ShellExecutorError(f"Command execution failed: {type(e).__name__}: {e}") from e

        execution_time = time.time() - start_time

        process_shell_output(
            stdout=stdout,
            stderr=stderr,
            max_chars=self.max_output_chars,
            normalize_paths=self.normalize_paths,
        )

        return ShellExecutionResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            command=prepared_command,
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
        prepared_command = self._prepare_command(command)

        # Prepare environment (always unbuffered for real-time output)
        process_env = prepare_shell_env(base_env=env, force_unbuffered=True)

        try:
            process = self._create_process(
                command=prepared_command,
                cwd=cwd,
                env=process_env,
                line_buffered=True,  # Background uses line buffering for real-time output
            )

            return BackgroundProcessHandle(
                process=process,
                command=command,
                prepared_command=prepared_command,
                cwd=cwd,
                start_time=time.time(),
            )

        except Exception as e:
            raise ShellExecutorError(f"Failed to start background process: {type(e).__name__}: {e}") from e

    def start_foreground(
        self,
        command: str,
        cwd: str,
        timeout_ms: Optional[int] = None,
        env: Optional[dict] = None,
    ) -> ForegroundExecutionHandle:
        """Start a foreground process with interruptible wait support.

        Creates the process and returns a handle that can be awaited.
        The handle supports ctrl+b to move the process to background.

        Args:
            command: The shell command to execute
            cwd: Working directory for command execution
            timeout_ms: Timeout in milliseconds (defaults to DEFAULT_TIMEOUT_MS)
            env: Optional environment variables (defaults to current env)

        Returns:
            ForegroundExecutionHandle with wait() method

        Raises:
            ShellExecutorError: If process creation fails
        """
        timeout_seconds = (timeout_ms or DEFAULT_TIMEOUT_MS) / 1000.0
        prepared_command = self._prepare_command(command)
        process_env = prepare_shell_env(base_env=env, force_unbuffered=True)

        try:
            # Use unified _create_process() for consistent text mode handling.
            # This ensures compatibility with BackgroundProcessManager.adopt_process()
            # when user presses Ctrl+B to move foreground process to background.
            process = self._create_process(
                command=prepared_command,
                cwd=cwd,
                env=process_env,
                line_buffered=False,  # Foreground uses default buffering
            )

            return ForegroundExecutionHandle(
                process=process,
                command=command,
                prepared_command=prepared_command,
                cwd=cwd,
                start_time=time.time(),
                timeout_seconds=timeout_seconds,
                process_env=process_env,
                max_output_chars=self.max_output_chars,
                normalize_paths=self.normalize_paths,
            )

        except Exception as e:
            raise ShellExecutorError(f"Failed to start foreground process: {type(e).__name__}: {e}") from e
