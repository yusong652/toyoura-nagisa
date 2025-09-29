"""
Background Process Manager for aiNagisa Bash Tool Background Execution.

Provides session-isolated background process management with output buffering,
process lifecycle tracking, and cleanup capabilities aligned with Claude Code behavior.
"""

import os
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

    # Output management
    stdout_buffer: List[str] = field(default_factory=list)
    stderr_buffer: List[str] = field(default_factory=list)
    last_stdout_position: int = 0
    last_stderr_position: int = 0

    # Metadata
    last_accessed: datetime = field(default_factory=datetime.now)
    working_directory: str = ""

    # Output reading tracking
    _stdout_thread: Optional[Thread] = None
    _stderr_thread: Optional[Thread] = None
    _output_lock: Lock = field(default_factory=Lock)


class BackgroundProcessManager:
    """
    Manages background bash processes with session isolation and output buffering.

    Features:
    - Session-isolated process tracking
    - Real-time output buffering with incremental reading
    - Process lifecycle management (start, monitor, kill, cleanup)
    - Automatic cleanup of completed processes
    - Memory-efficient circular buffering
    """

    # Configuration constants
    MAX_PROCESSES_PER_SESSION = 5
    MAX_BUFFER_LINES = 1000  # Keep last 1000 lines per stream
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
            for line in iter(stream.readline, ''):
                if line:
                    with process._output_lock:
                        buffer.append(line.rstrip('\n\r'))
                        # Implement circular buffer
                        if len(buffer) > self.MAX_BUFFER_LINES:
                            buffer.pop(0)
                else:
                    break
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
        Start a background bash process.

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

                # Start the subprocess
                popen = subprocess.Popen(
                    command,
                    shell=True,
                    cwd=str(work_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=os.environ.copy()
                )

                # Create process tracking object
                bg_process = BackgroundProcess(
                    process_id=process_id,
                    session_id=session_id,
                    command=command,
                    description=description,
                    process=popen,
                    start_time=datetime.now(),
                    status="running",
                    working_directory=str(work_dir)
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

                return success_response(
                    message=f"Command running in background with ID: {process_id}",
                    llm_content=f"Command running in background with ID: {process_id}",
                    process_id=process_id,
                    command=command,
                    background=True,
                    working_directory=str(work_dir)
                )

            except Exception as e:
                return error_response(f"Failed to start background process: {e}")

    def get_process_output(
        self,
        process_id: str,
        filter_regex: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get output from a background process.

        Args:
            process_id: Process ID to retrieve output from
            filter_regex: Optional regex to filter output lines

        Returns:
            Dict containing process status and output
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

            # Get new output since last check
            with bg_process._output_lock:
                new_stdout_lines = bg_process.stdout_buffer[bg_process.last_stdout_position:]
                new_stderr_lines = bg_process.stderr_buffer[bg_process.last_stderr_position:]

                # Update positions
                bg_process.last_stdout_position = len(bg_process.stdout_buffer)
                bg_process.last_stderr_position = len(bg_process.stderr_buffer)

            # Apply filtering if requested
            if filter_regex:
                try:
                    pattern = re.compile(filter_regex)
                    new_stdout_lines = [line for line in new_stdout_lines if pattern.search(line)]
                    new_stderr_lines = [line for line in new_stderr_lines if pattern.search(line)]
                except re.error as e:
                    return error_response(f"Invalid regex pattern: {e}")

            # Format output
            stdout_text = '\n'.join(new_stdout_lines) if new_stdout_lines else ''
            stderr_text = '\n'.join(new_stderr_lines) if new_stderr_lines else ''

            # Create LLM content similar to Claude Code format
            llm_content_parts = [f"<status>{bg_process.status}</status>"]

            if bg_process.exit_code is not None:
                llm_content_parts.append(f"<exit_code>{bg_process.exit_code}</exit_code>")

            if stdout_text:
                llm_content_parts.append(f"<stdout>\n{stdout_text}\n</stdout>")

            if stderr_text:
                llm_content_parts.append(f"<stderr>\n{stderr_text}\n</stderr>")

            llm_content_parts.append(f"<timestamp>{datetime.now().isoformat()}Z</timestamp>")

            return success_response(
                message="Retrieved output from background process",
                llm_content='\n\n'.join(llm_content_parts),
                process_id=process_id,
                status=bg_process.status,
                exit_code=bg_process.exit_code,
                stdout=stdout_text,
                stderr=stderr_text,
                command=bg_process.command,
                has_more_output=(bg_process.status == "running"),
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
                    final_stdout = '\n'.join(bg_process.stdout_buffer[bg_process.last_stdout_position:])
                    final_stderr = '\n'.join(bg_process.stderr_buffer[bg_process.last_stderr_position:])

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
                llm_content = f'{{"message":"{kill_message}","shell_id":"{process_id}"}}'

                return success_response(
                    message=kill_message,
                    llm_content=llm_content,
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
            cutoff_time = datetime.now() - timedelta(hours=1)  # Keep completed processes for 1 hour
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