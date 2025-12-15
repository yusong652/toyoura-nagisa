"""
Improved Background Process Manager for toyoura-nagisa with better output handling.

Key improvements:
1. Force unbuffered output for Python scripts
2. Provide helpful hints when no output is available
3. Better align with Claude Code behavior while fixing its limitations
"""

import asyncio
import re
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Set, Optional, List, Any, Literal
from threading import Lock, Thread

from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.shell.utils import (
    detect_python_command,
    enhance_python_command,
    prepare_shell_env,
)
from ..utils.path_security import validate_path_in_workspace, WORKSPACE_ROOT


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
    is_python_script: bool = False  # Track if command is running Python
    completion_notified: bool = False  # Track if completion/error has been notified

    # Output reading tracking
    _stdout_thread: Optional[Thread] = None
    _stderr_thread: Optional[Thread] = None
    _output_lock: Lock = field(default_factory=Lock)
    _last_output_time: datetime = field(default_factory=datetime.now)


class BackgroundProcessManager:
    """
    Manages background bash processes with improved output handling.

    Design Philosophy:
    1. Align with Claude Code's complete output approach (not incremental)
    2. Fix Python buffering issues automatically
    3. Provide helpful feedback when processes have no output
    4. Maintain session isolation and resource limits
    """

    # Configuration constants
    MAX_PROCESSES_PER_SESSION = 10
    MAX_BUFFER_LINES = 10000  # Store more lines since we return complete output
    PROCESS_TIMEOUT_HOURS = 2
    CLEANUP_INTERVAL_MINUTES = 10

    def __init__(self):
        """Initialize the background process manager."""
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
                    buffer.append(cleaned_line)
                    process._last_output_time = datetime.now()

                    # Implement circular buffer to prevent memory issues
                    if len(buffer) > self.MAX_BUFFER_LINES:
                        # For incremental mode, we need to adjust the position tracker
                        excess = len(buffer) - self.MAX_BUFFER_LINES
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
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Start a background bash process with improved output handling.

        Args:
            session_id: Session ID for process isolation
            command: Shell command to execute
            description: Optional description for the command

        Returns:
            Dict containing success/error response with process_id
        """
        with self._lock:
            # Check session process limits
            session_process_count = len(self.session_processes.get(session_id, set()))
            if session_process_count >= self.MAX_PROCESSES_PER_SESSION:
                return error_response(
                    f"Maximum {self.MAX_PROCESSES_PER_SESSION} background processes per session exceeded"
                )

            # Validate workspace access
            if not validate_path_in_workspace("."):
                return error_response("Cannot access workspace directory")

            work_dir = Path(str(WORKSPACE_ROOT))

            try:
                # Generate unique process ID
                process_id = self._generate_process_id()
                while process_id in self.processes:
                    process_id = self._generate_process_id()

                # Detect and enhance Python commands using shared utils
                is_python = detect_python_command(command)
                enhanced_command, _ = enhance_python_command(command)

                # Prepare environment with unbuffered output using shared utils
                env = prepare_shell_env(force_unbuffered=True, encoding='utf-8')

                # Start the subprocess with line buffering
                popen = subprocess.Popen(
                    enhanced_command,
                    shell=True,
                    cwd=str(work_dir),
                    stdin=subprocess.DEVNULL,  # Prevent blocking on interactive commands
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,  # Line buffered
                    env=env
                )

                # Create process tracking object
                bg_process = BackgroundProcess(
                    process_id=process_id,
                    session_id=session_id,
                    command=command,  # Store original command
                    description=description,
                    process=popen,
                    start_time=datetime.now(),
                    status="running",
                    working_directory=str(work_dir),
                    is_python_script=is_python
                )

                # Start output reading threads
                bg_process._stdout_thread = Thread(
                    target=self._read_output_stream,
                    args=(bg_process, popen.stdout, False),
                    daemon=True
                )
                bg_process._stderr_thread = Thread(
                    target=self._read_output_stream,
                    args=(bg_process, popen.stderr, True),
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

                # Provide helpful hint for Python scripts
                hint = ""
                if is_python:
                    hint = " (Python output will be unbuffered for real-time display)"

                return success_response(
                    message=f"Command running in background with ID: {process_id}{hint}",
                    llm_content={
                        "parts": [
                            {"type": "text", "text": f"Command running in background with ID: {process_id}"}
                        ]
                    },
                    process_id=process_id,
                    command=command,
                    background=True,
                    working_directory=str(work_dir),
                    python_detected=is_python
                )

            except Exception as e:
                return error_response(f"Failed to start background process: {e}")

    def get_process_output(
        self,
        process_id: str,
        filter_regex: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get incremental output from a background process.

        Returns only NEW output since last query to save context window.
        Perfect for long-running simulations and monitoring tasks.

        Args:
            process_id: Process ID to retrieve output from
            filter_regex: Optional regex to filter output lines

        Returns:
            Dict containing process status and incremental output
        """
        with self._lock:
            if process_id not in self.processes:
                return error_response(f"Process {process_id} not found")

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

            # Apply filtering if requested
            if filter_regex:
                try:
                    pattern = re.compile(filter_regex)
                    new_stdout = [line for line in new_stdout if pattern.search(line)]
                    new_stderr = [line for line in new_stderr if pattern.search(line)]
                except re.error as e:
                    return error_response(f"Invalid regex pattern: {e}")

            # Format output
            stdout_text = '\n'.join(new_stdout) if new_stdout else ''
            stderr_text = '\n'.join(new_stderr) if new_stderr else ''

            # Check if we have no new output (common for buffered processes or between outputs)
            no_new_output = not stdout_text and not stderr_text and bg_process.status == "running"

            # Create LLM content similar to Claude Code format
            llm_content_text_parts = [f"<status>{bg_process.status}</status>"]

            if bg_process.exit_code is not None:
                llm_content_text_parts.append(f"<exit_code>{bg_process.exit_code}</exit_code>")

            if stdout_text:
                llm_content_text_parts.append(f"<stdout>\n{stdout_text}\n</stdout>")
            elif no_new_output:
                # Provide helpful context when no new output
                time_running = (datetime.now() - bg_process.start_time).total_seconds()
                hint = ""
                if bg_process.is_python_script and time_running < 5:
                    hint = " (Python unbuffered mode enabled, checking for output...)"
                elif time_running > 10:
                    hint = " (Process may be idle or computing)"

                # For incremental mode, indicate no new output
                llm_content_text_parts.append(f"<info>No new output since last check{hint}</info>")

            if stderr_text:
                llm_content_text_parts.append(f"<stderr>\n{stderr_text}\n</stderr>")

            llm_content_text_parts.append(f"<timestamp>{datetime.now().isoformat()}Z</timestamp>")

            # Add statistics for monitoring
            with bg_process._output_lock:
                total_stdout_lines = len(bg_process.stdout_buffer)
                total_stderr_lines = len(bg_process.stderr_buffer)

            llm_content_text_parts.append(f"<stats>")
            llm_content_text_parts.append(f"  <new_lines>{len(new_stdout) + len(new_stderr)}</new_lines>")
            llm_content_text_parts.append(f"  <total_lines>{total_stdout_lines + total_stderr_lines}</total_lines>")
            llm_content_text_parts.append(f"  <runtime_seconds>{(datetime.now() - bg_process.start_time).total_seconds():.1f}</runtime_seconds>")
            llm_content_text_parts.append(f"</stats>")

            return success_response(
                message="Retrieved incremental output from background process",
                llm_content={
                    "parts": [
                        {"type": "text", "text": '\n\n'.join(llm_content_text_parts)}
                    ]
                },
                process_id=process_id,
                status=bg_process.status,
                exit_code=bg_process.exit_code,
                stdout=stdout_text,
                stderr=stderr_text,
                command=bg_process.command,
                has_new_output=(bool(stdout_text) or bool(stderr_text)),
                incremental_mode=True,
                new_line_count=len(new_stdout) + len(new_stderr),
                total_line_count=total_stdout_lines + total_stderr_lines,
                timestamp=datetime.now().isoformat()
            )

    def kill_process(self, process_id: str) -> Dict[str, Any]:
        """
        Kill a background process.

        Args:
            process_id: Process ID to kill

        Returns:
            Dict containing kill result
        """
        with self._lock:
            if process_id not in self.processes:
                return error_response(f"Process {process_id} not found")

            bg_process = self.processes[process_id]

            if bg_process.status != "running":
                return error_response(f"Process {process_id} is not running (status: {bg_process.status})")

            try:
                # Get any remaining output before killing
                with bg_process._output_lock:
                    # Get only unread output for final message
                    final_stdout_lines = bg_process.stdout_buffer[bg_process.last_stdout_position:]
                    final_stderr_lines = bg_process.stderr_buffer[bg_process.last_stderr_position:]
                    final_stdout = '\n'.join(final_stdout_lines) if final_stdout_lines else ''
                    final_stderr = '\n'.join(final_stderr_lines) if final_stderr_lines else ''

                # Kill the process
                bg_process.process.terminate()
                try:
                    bg_process.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    bg_process.process.kill()
                    bg_process.process.wait()

                bg_process.status = "killed"
                bg_process.exit_code = bg_process.process.returncode

                # Format response similar to Claude Code
                kill_message = f"Successfully killed shell: {process_id} ({bg_process.command})"

                return success_response(
                    message=kill_message,
                    llm_content={
                        "parts": [
                            {"type": "text", "text": f'{{"message":"{kill_message}","shell_id":"{process_id}"}}'}
                        ]
                    },
                    shell_id=process_id,
                    command=bg_process.command,
                    kill_successful=True,
                    final_output=final_stdout + final_stderr,
                    timestamp=datetime.now().isoformat()
                )

            except Exception as e:
                return error_response(f"Failed to kill process {process_id}: {e}")

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
                        try:
                            bg_process.process.terminate()
                            bg_process.process.wait(timeout=5)
                        except (subprocess.TimeoutExpired, Exception):
                            try:
                                bg_process.process.kill()
                                bg_process.process.wait()
                            except Exception:
                                pass
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
                    try:
                        bg_process.process.terminate()
                        bg_process.process.wait(timeout=5)
                    except (subprocess.TimeoutExpired, Exception):
                        try:
                            bg_process.process.kill()
                            bg_process.process.wait()
                        except Exception:
                            pass
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

    for process_id, bg_process in list(process_manager.processes.items()):
        if bg_process.status == "running":
            try:
                bg_process.process.terminate()
                bg_process.process.wait(timeout=2)
            except Exception:
                try:
                    bg_process.process.kill()
                except Exception:
                    pass
            bg_process.status = "killed"