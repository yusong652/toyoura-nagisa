"""
Background Process Manager for toyoura-nagisa.

Manages background bash process lifecycle:
- Process tracking and session isolation
- Output buffering and incremental reading
- Resource limits and cleanup
- Notification integration

Uses ShellExecutor for unified process creation.
"""

import asyncio
import os
import signal
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Set, Optional, List, Any, Literal
from threading import Lock, Thread

from .executor import (
    ShellExecutor,
    BackgroundProcessHandle,
    ShellExecutorError,
    ForegroundExecutionHandle,
)
from .utils import MAX_LINE_LENGTH, MAX_BUFFER_LINES


def _terminate_process_tree(process: subprocess.Popen, timeout: float = 5.0) -> None:
    """Terminate a process and all its children.

    On Unix with start_new_session=True, the process is a session leader
    and can be killed along with all children using os.killpg().

    On Windows, uses taskkill /T to kill the process tree.

    Args:
        process: The Popen process to terminate
        timeout: Seconds to wait after SIGTERM before using SIGKILL
    """
    if process.poll() is not None:
        return  # Already terminated

    try:
        if sys.platform == "win32":
            # Windows: Use taskkill with /T flag to kill process tree
            # /F = force, /T = tree (kill child processes), /PID = process ID
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                capture_output=True,
                timeout=timeout,
            )
        else:
            # Unix: Kill the entire process group with SIGTERM first
            pgid = os.getpgid(process.pid)
            os.killpg(pgid, signal.SIGTERM)

            # Wait for termination
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                # Force kill if SIGTERM didn't work
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    pass
                process.wait()

    except (ProcessLookupError, OSError, subprocess.TimeoutExpired):
        # Process already terminated or doesn't exist
        pass


@dataclass
class BackgroundProcess:
    """Represents a background bash process with output management."""
    process_id: str
    session_id: str
    command: str
    description: Optional[str]
    process: subprocess.Popen
    start_time: datetime
    status: Literal["running", "completed", "killed"]
    exit_code: Optional[int] = None

    # Output management - Incremental tracking for efficiency
    stdout_buffer: List[str] = field(default_factory=list)
    stderr_buffer: List[str] = field(default_factory=list)
    last_stdout_position: int = 0  # Track last returned position
    last_stderr_position: int = 0  # Track last returned position

    # Metadata
    last_accessed: datetime = field(default_factory=datetime.now)
    working_directory: str = ""
    completion_notified: bool = False  # Track if completion/error has been notified

    # Output reading tracking
    _stdout_thread: Optional[Thread] = None
    _stderr_thread: Optional[Thread] = None
    _output_lock: Lock = field(default_factory=Lock)
    _last_output_time: datetime = field(default_factory=datetime.now)


@dataclass
class StartProcessResult:
    """Result of starting a background process.

    Infrastructure layer returns this; tool layer converts to success_response/error_response.
    """
    success: bool
    process_id: Optional[str] = None
    command: Optional[str] = None
    working_directory: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ProcessOutputResult:
    """Result of getting process output.

    Infrastructure layer returns this; tool layer converts to success_response/error_response.
    """
    success: bool
    # Process info
    process_id: Optional[str] = None
    status: Optional[str] = None  # "running", "completed", "killed"
    exit_code: Optional[int] = None
    command: Optional[str] = None
    # Output
    stdout: str = ""
    stderr: str = ""
    has_new_output: bool = False
    new_line_count: int = 0
    total_line_count: int = 0
    # Metadata
    runtime_seconds: float = 0.0
    # Error
    error: Optional[str] = None


@dataclass
class KillProcessResult:
    """Result of killing a background process.

    Infrastructure layer returns this; tool layer converts to success_response/error_response.
    """
    success: bool
    process_id: Optional[str] = None
    command: Optional[str] = None
    final_output: str = ""
    error: Optional[str] = None


class BackgroundProcessManager:
    """
    Manages background bash process lifecycle.

    Responsibilities:
    - Process tracking and session isolation
    - Output buffering with incremental reading
    - Resource limits (per-session, global)
    - Automatic cleanup of old processes
    - Notification integration

    Uses ShellExecutor for process creation, ensuring unified
    command preparation and Popen configuration.
    """

    # Configuration constants
    MAX_PROCESSES_PER_SESSION = 10
    MAX_PROCESSES_GLOBAL = 50  # Global limit across all sessions
    PROCESS_TIMEOUT_HOURS = 2
    CLEANUP_INTERVAL_MINUTES = 10

    def __init__(self, executor: Optional[ShellExecutor] = None):
        """Initialize the background process manager.

        Args:
            executor: ShellExecutor instance for process creation.
                     If None, creates a default instance.
        """
        self.executor = executor or ShellExecutor()
        self.processes: Dict[str, BackgroundProcess] = {}
        self.session_processes: Dict[str, Set[str]] = {}  # session_id -> process_ids
        self._lock = Lock()
        self._cleanup_thread: Optional[Thread] = None
        self._start_cleanup_thread()

    def _start_cleanup_thread(self) -> None:
        """Start the background cleanup thread."""
        if self._cleanup_thread is None or not self._cleanup_thread.is_alive():
            self._cleanup_thread = Thread(target=self._cleanup_worker, daemon=True)
            self._cleanup_thread.start()

    def _start_notification_monitoring(
        self,
        session_id: str,
        process_id: str,
        command: str,
        description: Optional[str] = None
    ) -> None:
        """
        Start background process notification monitoring.

        Args:
            session_id: Session ID
            process_id: Process ID
            command: Shell command
            description: Optional command description
        """
        try:
            from backend.application.services.notifications.background_process_notification_service import (
                get_background_process_notification_service
            )

            notification_service = get_background_process_notification_service()
            if notification_service:
                # Schedule the async monitoring task
                asyncio.create_task(
                    notification_service.start_monitoring(
                        session_id=session_id,
                        process_id=process_id,
                        command=command,
                        description=description
                    )
                )
        except Exception as e:
            # Don't fail process start if notification service unavailable
            print(f"[BackgroundProcessManager] Could not start notification monitoring: {e}")

    def _cleanup_worker(self) -> None:
        """Background worker for cleaning up old processes."""
        import time
        while True:
            try:
                time.sleep(self.CLEANUP_INTERVAL_MINUTES * 60)
                self.cleanup_completed_processes()
            except Exception as e:
                print(f"[BackgroundProcessManager] Cleanup worker error: {e}")

    def _generate_process_id(self) -> str:
        """Generate a unique 6-character process ID."""
        return str(uuid.uuid4()).replace('-', '')[:6]

    def _read_output_stream(self, process: BackgroundProcess, stream: Any, is_stderr: bool) -> None:
        """
        Read output from a process stream in a separate thread.

        Args:
            process: BackgroundProcess object
            stream: Process stdout or stderr stream
            is_stderr: True if reading stderr, False for stdout
        """
        buffer = process.stderr_buffer if is_stderr else process.stdout_buffer

        try:
            # Use iter with sentinel for cleaner reading
            for line in iter(stream.readline, ''):
                if not line:
                    break

                with process._output_lock:
                    # Store lines for incremental reading
                    cleaned_line = line.rstrip('\n\r')
                    # Truncate very long lines to prevent memory issues
                    if len(cleaned_line) > MAX_LINE_LENGTH:
                        cleaned_line = cleaned_line[:MAX_LINE_LENGTH] + "... (truncated)"
                    buffer.append(cleaned_line)
                    process._last_output_time = datetime.now()

                    # Implement circular buffer to prevent memory issues
                    if len(buffer) > MAX_BUFFER_LINES:
                        # For incremental mode, we need to adjust the position tracker
                        excess = len(buffer) - MAX_BUFFER_LINES
                        if is_stderr:
                            process.last_stderr_position = max(0, process.last_stderr_position - excess)
                        else:
                            process.last_stdout_position = max(0, process.last_stdout_position - excess)
                        del buffer[:excess]

        except Exception as e:
            with process._output_lock:
                error_msg = f"Error reading {'stderr' if is_stderr else 'stdout'}: {e}"
                buffer.append(error_msg)
        finally:
            stream.close()

    def start_process(
        self,
        session_id: str,
        command: str,
        cwd: str,
        description: Optional[str] = None
    ) -> StartProcessResult:
        """
        Start a background bash process.

        Args:
            session_id: Session ID for process isolation
            command: Shell command to execute
            cwd: Working directory for command execution
            description: Optional description for the command

        Returns:
            StartProcessResult with process info or error
        """
        with self._lock:
            # Check global process limit (only count running processes)
            global_running = sum(
                1 for p in self.processes.values() if p.status == "running"
            )
            if global_running >= self.MAX_PROCESSES_GLOBAL:
                return StartProcessResult(
                    success=False,
                    error=f"Maximum {self.MAX_PROCESSES_GLOBAL} concurrent global background processes"
                )

            # Check session process limits (only count running processes)
            running_count = sum(
                1 for pid in self.session_processes.get(session_id, set())
                if pid in self.processes and self.processes[pid].status == "running"
            )
            if running_count >= self.MAX_PROCESSES_PER_SESSION:
                return StartProcessResult(
                    success=False,
                    error=f"Maximum {self.MAX_PROCESSES_PER_SESSION} concurrent background processes per session"
                )

            try:
                # Generate unique process ID
                process_id = self._generate_process_id()
                while process_id in self.processes:
                    process_id = self._generate_process_id()

                # Use ShellExecutor for unified process creation
                handle: BackgroundProcessHandle = self.executor.start_background(
                    command=command,
                    cwd=cwd,
                )

                # Create process tracking object
                bg_process = BackgroundProcess(
                    process_id=process_id,
                    session_id=session_id,
                    command=handle.command,  # Original command
                    description=description,
                    process=handle.process,
                    start_time=datetime.fromtimestamp(handle.start_time),
                    status="running",
                    working_directory=handle.cwd,
                )

                # Start output reading threads
                bg_process._stdout_thread = Thread(
                    target=self._read_output_stream,
                    args=(bg_process, handle.process.stdout, False),
                    daemon=True
                )
                bg_process._stderr_thread = Thread(
                    target=self._read_output_stream,
                    args=(bg_process, handle.process.stderr, True),
                    daemon=True
                )

                bg_process._stdout_thread.start()
                bg_process._stderr_thread.start()

                # Register the process
                self.processes[process_id] = bg_process
                if session_id not in self.session_processes:
                    self.session_processes[session_id] = set()
                self.session_processes[session_id].add(process_id)

                # Start notification service monitoring
                self._start_notification_monitoring(session_id, process_id, command, description)

                return StartProcessResult(
                    success=True,
                    process_id=process_id,
                    command=handle.command,
                    working_directory=handle.cwd,
                )

            except ShellExecutorError as e:
                return StartProcessResult(
                    success=False,
                    error=str(e)
                )
            except Exception as e:
                return StartProcessResult(
                    success=False,
                    error=f"Failed to start background process: {e}"
                )

    def adopt_process(
        self,
        session_id: str,
        handle: ForegroundExecutionHandle,
        description: Optional[str] = None,
    ) -> str:
        """Adopt a running foreground process into background management.

        Called when user presses ctrl+b to move a foreground process to background.
        The process is already running; we just need to start tracking it.

        Args:
            session_id: Session ID for process isolation
            handle: ForegroundExecutionHandle from the foreground process
            description: Optional description for the command

        Returns:
            process_id: The assigned background process ID
        """
        with self._lock:
            # Generate unique process ID
            process_id = self._generate_process_id()
            while process_id in self.processes:
                process_id = self._generate_process_id()

            # Convert to background handle
            bg_handle = handle.to_background_handle()

            # Create process tracking object
            bg_process = BackgroundProcess(
                process_id=process_id,
                session_id=session_id,
                command=bg_handle.command,
                description=description,
                process=bg_handle.process,
                start_time=datetime.fromtimestamp(bg_handle.start_time),
                status="running",
                working_directory=bg_handle.cwd,
            )

            # Start output reading threads
            bg_process._stdout_thread = Thread(
                target=self._read_output_stream,
                args=(bg_process, bg_handle.process.stdout, False),
                daemon=True
            )
            bg_process._stderr_thread = Thread(
                target=self._read_output_stream,
                args=(bg_process, bg_handle.process.stderr, True),
                daemon=True
            )

            bg_process._stdout_thread.start()
            bg_process._stderr_thread.start()

            # Register the process
            self.processes[process_id] = bg_process
            if session_id not in self.session_processes:
                self.session_processes[session_id] = set()
            self.session_processes[session_id].add(process_id)

            # Start notification service monitoring
            self._start_notification_monitoring(
                session_id, process_id, bg_handle.command, description
            )

            return process_id

    def get_process_output(self, process_id: str) -> ProcessOutputResult:
        """
        Get incremental output from a background process.

        Returns only NEW output since last query to save context window.
        Perfect for long-running simulations and monitoring tasks.

        Args:
            process_id: Process ID to retrieve output from

        Returns:
            ProcessOutputResult with output data or error
        """
        with self._lock:
            if process_id not in self.processes:
                return ProcessOutputResult(
                    success=False,
                    error=f"Process {process_id} not found"
                )

            bg_process = self.processes[process_id]
            bg_process.last_accessed = datetime.now()

            # Check if process has completed
            if bg_process.status == "running" and bg_process.process.poll() is not None:
                bg_process.status = "completed"
                bg_process.exit_code = bg_process.process.returncode

            # Mark completion as notified when LLM actively checks the status
            # This prevents duplicate reminders via get_system_reminders()
            if bg_process.status in ["completed", "killed"]:
                bg_process.completion_notified = True

            # Get INCREMENTAL output (efficient for long-running processes)
            with bg_process._output_lock:
                # Get new lines since last position
                new_stdout = bg_process.stdout_buffer[bg_process.last_stdout_position:]
                new_stderr = bg_process.stderr_buffer[bg_process.last_stderr_position:]

                # Update positions for next query
                bg_process.last_stdout_position = len(bg_process.stdout_buffer)
                bg_process.last_stderr_position = len(bg_process.stderr_buffer)

            # Format output
            stdout_text = '\n'.join(new_stdout) if new_stdout else ''
            stderr_text = '\n'.join(new_stderr) if new_stderr else ''

            # Get statistics
            with bg_process._output_lock:
                total_stdout_lines = len(bg_process.stdout_buffer)
                total_stderr_lines = len(bg_process.stderr_buffer)

            runtime_seconds = (datetime.now() - bg_process.start_time).total_seconds()

            return ProcessOutputResult(
                success=True,
                process_id=process_id,
                status=bg_process.status,
                exit_code=bg_process.exit_code,
                command=bg_process.command,
                stdout=stdout_text,
                stderr=stderr_text,
                has_new_output=(bool(stdout_text) or bool(stderr_text)),
                new_line_count=len(new_stdout) + len(new_stderr),
                total_line_count=total_stdout_lines + total_stderr_lines,
                runtime_seconds=runtime_seconds,
            )

    def kill_process(self, process_id: str) -> KillProcessResult:
        """
        Kill a background process.

        Args:
            process_id: Process ID to kill

        Returns:
            KillProcessResult with kill status or error
        """
        with self._lock:
            if process_id not in self.processes:
                return KillProcessResult(
                    success=False,
                    error=f"Process {process_id} not found"
                )

            bg_process = self.processes[process_id]

            if bg_process.status != "running":
                return KillProcessResult(
                    success=False,
                    error=f"Process {process_id} is not running (status: {bg_process.status})"
                )

            try:
                # Get any remaining output before killing
                with bg_process._output_lock:
                    # Get only unread output for final message
                    final_stdout_lines = bg_process.stdout_buffer[bg_process.last_stdout_position:]
                    final_stderr_lines = bg_process.stderr_buffer[bg_process.last_stderr_position:]
                    final_stdout = '\n'.join(final_stdout_lines) if final_stdout_lines else ''
                    final_stderr = '\n'.join(final_stderr_lines) if final_stderr_lines else ''

                # Kill the process and all its children
                _terminate_process_tree(bg_process.process, timeout=5.0)

                bg_process.status = "killed"
                bg_process.exit_code = bg_process.process.returncode

                return KillProcessResult(
                    success=True,
                    process_id=process_id,
                    command=bg_process.command,
                    final_output=final_stdout + final_stderr,
                )

            except Exception as e:
                return KillProcessResult(
                    success=False,
                    error=f"Failed to kill process {process_id}: {e}"
                )

    def has_active_processes(self, session_id: str) -> bool:
        """
        Check if a session has any active (running) background processes.

        Args:
            session_id: Session ID to check

        Returns:
            True if session has running processes, False otherwise
        """
        with self._lock:
            if session_id not in self.session_processes:
                return False

            for process_id in self.session_processes[session_id]:
                if process_id in self.processes:
                    bg_process = self.processes[process_id]
                    # Update status if process completed
                    if bg_process.status == "running" and bg_process.process.poll() is not None:
                        bg_process.status = "completed"
                        bg_process.exit_code = bg_process.process.returncode

                    if bg_process.status == "running":
                        return True

            return False

    def get_active_process_ids(self, session_id: str) -> List[str]:
        """
        Get list of active process IDs for a session.

        Args:
            session_id: Session ID to check

        Returns:
            List of active process IDs
        """
        with self._lock:
            active_ids = []
            if session_id in self.session_processes:
                for process_id in self.session_processes[session_id]:
                    if process_id in self.processes:
                        bg_process = self.processes[process_id]
                        # Update status if needed
                        if bg_process.status == "running" and bg_process.process.poll() is not None:
                            bg_process.status = "completed"
                            bg_process.exit_code = bg_process.process.returncode

                        if bg_process.status == "running":
                            active_ids.append(process_id)

            return active_ids

    def get_system_reminders(self, session_id: str) -> List[str]:
        """
        Get system reminder messages for background processes.

        Returns formatted reminder strings based on process state:
        1. Running processes: Remind when new output is available
        2. First-time completion: Remind when status changes to completed/killed
        3. After notification: No more reminders

        Args:
            session_id: Session ID to get reminders for

        Returns:
            List[str]: List of formatted reminder strings
        """
        with self._lock:
            # Get active process IDs (inline to avoid nested lock)
            if session_id not in self.session_processes:
                return []

            reminders = []
            for process_id in self.session_processes[session_id]:
                bg_process = self.processes.get(process_id)
                if not bg_process:
                    continue

                # Update status if needed
                if bg_process.status == "running" and bg_process.process.poll() is not None:
                    bg_process.status = "completed"
                    bg_process.exit_code = bg_process.process.returncode

                # Use description if available, fallback to command
                display_info = bg_process.description or bg_process.command

                # Case 1: Running processes - always remind (with or without new output)
                if bg_process.status == "running":
                    has_new_output = (
                        len(bg_process.stdout_buffer) > bg_process.last_stdout_position or
                        len(bg_process.stderr_buffer) > bg_process.last_stderr_position
                    )

                    if has_new_output:
                        reminder = (
                            f"Background Bash {process_id} "
                            f"(description: {display_info}) "
                            f"(status: {bg_process.status}) "
                            f"Has new output available. You can check its output using the BashOutput tool."
                        )
                    else:
                        # No new output, but still remind about running process
                        runtime = (datetime.now() - bg_process.start_time).total_seconds()
                        reminder = (
                            f"Background Bash {process_id} "
                            f"(description: {display_info}) "
                            f"(status: {bg_process.status}, runtime: {runtime:.1f}s) "
                            f"Is running. You can check its output using the BashOutput tool."
                        )
                    reminders.append(reminder)

                # Case 2: First-time completion/error - remind once about status change
                elif bg_process.status in ["completed", "killed"] and not bg_process.completion_notified:
                    bg_process.completion_notified = True
                    exit_info = f"exit_code={bg_process.exit_code}" if bg_process.exit_code is not None else ""
                    reminder = (
                        f"Background Bash {process_id} "
                        f"(description: {display_info}) "
                        f"Has finished with status: {bg_process.status} {exit_info}. "
                        f"You can check its final output using the BashOutput tool."
                    )
                    reminders.append(reminder)

                # Case 3: Already notified completion - no more reminders

            return reminders

    def cleanup_session(self, session_id: str) -> None:
        """
        Kill all processes for a session and clean up resources.

        Args:
            session_id: Session ID to clean up
        """
        with self._lock:
            if session_id not in self.session_processes:
                return

            process_ids_to_kill = list(self.session_processes[session_id])

            for process_id in process_ids_to_kill:
                if process_id in self.processes:
                    bg_process = self.processes[process_id]
                    if bg_process.status == "running":
                        _terminate_process_tree(bg_process.process, timeout=5.0)
                        bg_process.status = "killed"

                    # Remove from tracking
                    del self.processes[process_id]

            # Clean up session tracking
            del self.session_processes[session_id]

    def cleanup_completed_processes(self) -> None:
        """Remove old completed/killed processes to prevent memory leaks."""
        with self._lock:
            cutoff_time = datetime.now() - timedelta(hours=1)
            processes_to_remove = []

            for process_id, bg_process in self.processes.items():
                # Update status if needed
                if bg_process.status == "running" and bg_process.process.poll() is not None:
                    bg_process.status = "completed"
                    bg_process.exit_code = bg_process.process.returncode

                # Remove old completed/killed processes
                if (bg_process.status in ["completed", "killed"] and
                    bg_process.last_accessed < cutoff_time):
                    processes_to_remove.append(process_id)

                # Kill processes that have been running too long
                elif (bg_process.status == "running" and
                      bg_process.start_time < datetime.now() - timedelta(hours=self.PROCESS_TIMEOUT_HOURS)):
                    _terminate_process_tree(bg_process.process, timeout=5.0)
                    bg_process.status = "killed"
                    processes_to_remove.append(process_id)

            # Remove old processes
            for process_id in processes_to_remove:
                bg_process = self.processes[process_id]
                session_id = bg_process.session_id

                # Remove from processes
                del self.processes[process_id]

                # Remove from session tracking
                if session_id in self.session_processes:
                    self.session_processes[session_id].discard(process_id)
                    if not self.session_processes[session_id]:
                        del self.session_processes[session_id]


# Global process manager instance
_process_manager: Optional[BackgroundProcessManager] = None


def get_process_manager() -> BackgroundProcessManager:
    """
    Get the global background process manager instance.

    Returns:
        BackgroundProcessManager: Singleton instance
    """
    global _process_manager
    if _process_manager is None:
        _process_manager = BackgroundProcessManager()
    return _process_manager


def cleanup_session_processes(session_id: str) -> None:
    """
    Cleanup all background processes for a session.

    Args:
        session_id: Session ID to clean up
    """
    process_manager = get_process_manager()
    process_manager.cleanup_session(session_id)


def shutdown_all_processes() -> None:
    """
    Shutdown all background processes across all sessions.

    Called during application shutdown to ensure clean termination.
    """
    process_manager = get_process_manager()

    for _, bg_process in list(process_manager.processes.items()):
        if bg_process.status == "running":
            _terminate_process_tree(bg_process.process, timeout=2.0)
            bg_process.status = "killed"
