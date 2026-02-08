"""PFC Task Manager for toyoura-nagisa.

Manages PFC simulation task lifecycle on the backend side:
- Task ID generation (6-char UUID, matching bash pattern)
- Task status tracking (source of truth)
- Incremental output management
- Session isolation
- System reminders generation

Follows the same pattern as BackgroundProcessManager for bash tasks.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Lock, Thread
from typing import Dict, Set, Optional, List, Literal, Any


# Output buffer limits (matching bash tool)
MAX_LINE_LENGTH = 10000
MAX_BUFFER_LINES = 10000


@dataclass
class PfcTask:
    """Represents a PFC simulation task with full lifecycle tracking."""
    task_id: str                          # 6-char UUID, backend-generated
    session_id: str
    script_path: str
    description: Optional[str]
    status: Literal["pending", "submitted", "running", "completed", "failed", "interrupted"]
    start_time: datetime
    end_time: Optional[datetime] = None

    # PFC-specific fields
    git_commit: Optional[str] = None      # Version snapshot hash
    source: str = "agent"                 # "agent" or "user_console"
    bridge_task_id: Optional[str] = None      # Task ID from pfc-bridge (for reference)

    # Result data
    result: Optional[Any] = None          # Script return value
    error: Optional[str] = None           # Error message if failed

    # Output management - Incremental tracking for efficiency
    output_lines: List[str] = field(default_factory=list)
    last_output_position: int = 0         # Track last returned position

    # Metadata
    last_accessed: datetime = field(default_factory=datetime.now)
    completion_notified: bool = False     # Track if completion has been notified

    # Thread-safe output access
    _output_lock: Lock = field(default_factory=Lock)

    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

    @property
    def is_terminal(self) -> bool:
        """Check if task is in a terminal state."""
        return self.status in ("completed", "failed", "interrupted")


@dataclass
class TaskOutputResult:
    """Result of getting task output."""
    success: bool
    task_id: Optional[str] = None
    status: Optional[str] = None
    output: str = ""
    has_new_output: bool = False
    new_line_count: int = 0
    total_line_count: int = 0
    elapsed_seconds: float = 0.0
    error: Optional[str] = None


@dataclass
class TaskStatusResult:
    """Result of getting task status."""
    success: bool
    task_id: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    script_path: Optional[str] = None
    git_commit: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    elapsed_seconds: float = 0.0
    result: Optional[Any] = None
    error: Optional[str] = None


class PfcTaskManager:
    """
    Manages PFC task lifecycle on the backend side.

    Mirrors BackgroundProcessManager pattern:
    - Task ID generation (6-char UUID)
    - Session isolation
    - Incremental output tracking
    - System reminders generation

    Key difference from bash: Tasks are remote (pfc-bridge),
    not local subprocesses. This manager tracks state and
    coordinates with pfc-bridge via WebSocket.
    """

    # Configuration constants
    MAX_TASKS_PER_SESSION = 10
    MAX_TASKS_GLOBAL = 50
    TASK_TIMEOUT_HOURS = 24  # PFC simulations can run for a long time
    CLEANUP_INTERVAL_MINUTES = 30

    def __init__(self):
        """Initialize the PFC task manager."""
        self.tasks: Dict[str, PfcTask] = {}
        self.session_tasks: Dict[str, Set[str]] = {}  # session_id -> task_ids
        self._lock = Lock()
        self._cleanup_thread: Optional[Thread] = None
        self._start_cleanup_thread()

    def _start_cleanup_thread(self) -> None:
        """Start the background cleanup thread."""
        if self._cleanup_thread is None or not self._cleanup_thread.is_alive():
            self._cleanup_thread = Thread(target=self._cleanup_worker, daemon=True)
            self._cleanup_thread.start()

    def _cleanup_worker(self) -> None:
        """Background worker for cleaning up old tasks."""
        import time
        while True:
            try:
                time.sleep(self.CLEANUP_INTERVAL_MINUTES * 60)
                self.cleanup_old_tasks()
            except Exception as e:
                print(f"[PfcTaskManager] Cleanup worker error: {e}")

    def _generate_task_id(self) -> str:
        """Generate a unique 6-character task ID (matches bash pattern)."""
        return str(uuid.uuid4()).replace('-', '')[:6]

    def create_task(
        self,
        session_id: str,
        script_path: str,
        description: Optional[str] = None,
        git_commit: Optional[str] = None,
        source: str = "agent",
    ) -> str:
        """Create and register a new PFC task.

        Args:
            session_id: Session ID for task isolation
            script_path: Path to the script being executed
            description: Optional description for the task
            git_commit: Optional git commit hash for version tracking
            source: Task source ("agent" or "user_console")

        Returns:
            task_id: The assigned 6-character task ID
        """
        with self._lock:
            # Check limits
            global_count = len([t for t in self.tasks.values() if not t.is_terminal])
            if global_count >= self.MAX_TASKS_GLOBAL:
                raise ValueError(f"Maximum {self.MAX_TASKS_GLOBAL} concurrent global PFC tasks")

            session_count = len([
                tid for tid in self.session_tasks.get(session_id, set())
                if tid in self.tasks and not self.tasks[tid].is_terminal
            ])
            if session_count >= self.MAX_TASKS_PER_SESSION:
                raise ValueError(f"Maximum {self.MAX_TASKS_PER_SESSION} concurrent PFC tasks per session")

            # Generate unique task ID
            task_id = self._generate_task_id()
            while task_id in self.tasks:
                task_id = self._generate_task_id()

            # Create task
            task = PfcTask(
                task_id=task_id,
                session_id=session_id,
                script_path=script_path,
                description=description,
                status="pending",
                start_time=datetime.now(),
                git_commit=git_commit,
                source=source,
            )

            # Register
            self.tasks[task_id] = task
            if session_id not in self.session_tasks:
                self.session_tasks[session_id] = set()
            self.session_tasks[session_id].add(task_id)

            return task_id

    def update_status(
        self,
        task_id: str,
        status: str,
        bridge_task_id: Optional[str] = None,
        result: Optional[Any] = None,
        error: Optional[str] = None,
    ) -> bool:
        """Update task status and metadata.

        Args:
            task_id: Task ID to update
            status: New status
            bridge_task_id: Optional pfc-bridge task ID for reference
            result: Optional result data
            error: Optional error message

        Returns:
            True if updated, False if task not found
        """
        with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return False

            task.status = status

            if bridge_task_id:
                task.bridge_task_id = bridge_task_id

            if result is not None:
                task.result = result

            if error is not None:
                task.error = error

            # Set end time for terminal states
            if status in ("completed", "failed", "interrupted"):
                task.end_time = datetime.now()

            return True

    def append_output(self, task_id: str, output_lines: List[str]) -> bool:
        """Append output lines to a task (thread-safe).

        Args:
            task_id: Task ID to update
            output_lines: Lines to append

        Returns:
            True if updated, False if task not found
        """
        with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return False

        # Use task's own lock for output updates
        with task._output_lock:
            for line in output_lines:
                # Truncate very long lines
                if len(line) > MAX_LINE_LENGTH:
                    line = line[:MAX_LINE_LENGTH] + "... (truncated)"
                task.output_lines.append(line)

            # Implement circular buffer
            if len(task.output_lines) > MAX_BUFFER_LINES:
                excess = len(task.output_lines) - MAX_BUFFER_LINES
                task.last_output_position = max(0, task.last_output_position - excess)
                del task.output_lines[:excess]

        return True

    def set_output(self, task_id: str, output: str) -> bool:
        """Set full output for a task (replaces existing).

        Used when receiving complete output from pfc-bridge.

        Args:
            task_id: Task ID to update
            output: Full output text

        Returns:
            True if updated, False if task not found
        """
        with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return False

        lines = output.split('\n') if output else []

        with task._output_lock:
            task.output_lines = []
            task.last_output_position = 0
            for line in lines:
                if len(line) > MAX_LINE_LENGTH:
                    line = line[:MAX_LINE_LENGTH] + "... (truncated)"
                task.output_lines.append(line)

            # Implement circular buffer
            if len(task.output_lines) > MAX_BUFFER_LINES:
                excess = len(task.output_lines) - MAX_BUFFER_LINES
                del task.output_lines[:excess]

        return True

    def get_incremental_output(self, task_id: str) -> TaskOutputResult:
        """Get new output since last position.

        Args:
            task_id: Task ID to get output for

        Returns:
            TaskOutputResult with incremental output
        """
        with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return TaskOutputResult(
                    success=False,
                    error=f"Task {task_id} not found"
                )

            task.last_accessed = datetime.now()

            # Mark completion as notified when actively checking
            if task.is_terminal:
                task.completion_notified = True

        # Get incremental output
        with task._output_lock:
            new_lines = task.output_lines[task.last_output_position:]
            task.last_output_position = len(task.output_lines)
            total_lines = len(task.output_lines)

        output_text = '\n'.join(new_lines) if new_lines else ''

        return TaskOutputResult(
            success=True,
            task_id=task_id,
            status=task.status,
            output=output_text,
            has_new_output=bool(new_lines),
            new_line_count=len(new_lines),
            total_line_count=total_lines,
            elapsed_seconds=task.elapsed_seconds,
        )

    def get_full_output(self, task_id: str) -> TaskOutputResult:
        """Get full output (does not update position).

        Args:
            task_id: Task ID to get output for

        Returns:
            TaskOutputResult with full output
        """
        with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return TaskOutputResult(
                    success=False,
                    error=f"Task {task_id} not found"
                )

            task.last_accessed = datetime.now()

        with task._output_lock:
            all_lines = list(task.output_lines)

        output_text = '\n'.join(all_lines) if all_lines else ''

        return TaskOutputResult(
            success=True,
            task_id=task_id,
            status=task.status,
            output=output_text,
            has_new_output=False,
            new_line_count=0,
            total_line_count=len(all_lines),
            elapsed_seconds=task.elapsed_seconds,
        )

    def get_task_status(self, task_id: str) -> TaskStatusResult:
        """Get task status and metadata.

        Args:
            task_id: Task ID to get status for

        Returns:
            TaskStatusResult with task info
        """
        with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return TaskStatusResult(
                    success=False,
                    error=f"Task {task_id} not found"
                )

            task.last_accessed = datetime.now()

            return TaskStatusResult(
                success=True,
                task_id=task_id,
                status=task.status,
                description=task.description,
                script_path=task.script_path,
                git_commit=task.git_commit,
                start_time=task.start_time,
                end_time=task.end_time,
                elapsed_seconds=task.elapsed_seconds,
                result=task.result,
                error=task.error,
            )

    def get_task(self, task_id: str) -> Optional[PfcTask]:
        """Get task by ID.

        Args:
            task_id: Task ID to get

        Returns:
            PfcTask if found, None otherwise
        """
        with self._lock:
            return self.tasks.get(task_id)

    def list_tasks(
        self,
        session_id: Optional[str] = None,
        source: Optional[str] = None,
        include_terminal: bool = True,
        offset: int = 0,
        limit: int = 32,
    ) -> List[PfcTask]:
        """List tasks with optional filtering.

        Args:
            session_id: Filter by session ID
            source: Filter by source ("agent" or "user_console")
            include_terminal: Include completed/failed/interrupted tasks
            offset: Number of tasks to skip
            limit: Maximum number of tasks to return

        Returns:
            List of PfcTask objects
        """
        with self._lock:
            tasks = list(self.tasks.values())

            # Apply filters
            if session_id:
                tasks = [t for t in tasks if t.session_id == session_id]
            if source:
                tasks = [t for t in tasks if t.source == source]
            if not include_terminal:
                tasks = [t for t in tasks if not t.is_terminal]

            # Sort by start time (newest first)
            tasks.sort(key=lambda t: t.start_time, reverse=True)

            # Apply pagination
            return tasks[offset:offset + limit]

    def clear_all_tasks(self) -> int:
        """Clear all tasks from local state. Returns count of cleared tasks."""
        with self._lock:
            count = len(self.tasks)
            self.tasks.clear()
            return count

    def has_active_tasks(self, session_id: str) -> bool:
        """Check if session has any active (non-terminal) tasks.

        Args:
            session_id: Session ID to check

        Returns:
            True if session has active tasks
        """
        with self._lock:
            if session_id not in self.session_tasks:
                return False

            for task_id in self.session_tasks[session_id]:
                task = self.tasks.get(task_id)
                if task and not task.is_terminal:
                    return True

            return False

    def get_active_task_ids(self, session_id: str) -> List[str]:
        """Get list of active task IDs for a session.

        Args:
            session_id: Session ID to check

        Returns:
            List of active task IDs
        """
        with self._lock:
            active_ids = []
            if session_id in self.session_tasks:
                for task_id in self.session_tasks[session_id]:
                    task = self.tasks.get(task_id)
                    if task and not task.is_terminal:
                        active_ids.append(task_id)
            return active_ids

    def get_system_reminders(self, session_id: str) -> List[str]:
        """Get system reminder messages for PFC tasks.

        Returns formatted reminder strings based on task state:
        1. Running tasks: Remind about status
        2. First-time completion: Remind about completion
        3. After notification: No more reminders

        Args:
            session_id: Session ID to get reminders for

        Returns:
            List of formatted reminder strings
        """
        with self._lock:
            if session_id not in self.session_tasks:
                return []

            reminders = []
            for task_id in self.session_tasks[session_id]:
                task = self.tasks.get(task_id)
                if not task:
                    continue

                display_info = task.description or task.script_path

                # Case 1: Running/pending tasks - remind about status
                if task.status in ("pending", "submitted", "running"):
                    has_new_output = False
                    with task._output_lock:
                        has_new_output = len(task.output_lines) > task.last_output_position

                    if has_new_output:
                        reminder = (
                            f"PFC Task {task_id} "
                            f"(description: {display_info}) "
                            f"(status: {task.status}) "
                            f"Has new output available. Use pfc_check_task_status('{task_id}') to check."
                        )
                    else:
                        runtime = task.elapsed_seconds
                        reminder = (
                            f"PFC Task {task_id} "
                            f"(description: {display_info}) "
                            f"(status: {task.status}, runtime: {runtime:.1f}s) "
                            f"Is running. Use pfc_check_task_status('{task_id}') to check."
                        )
                    reminders.append(reminder)

                # Case 2: First-time completion - remind once
                elif task.is_terminal and not task.completion_notified:
                    task.completion_notified = True
                    status_info = task.status
                    if task.error:
                        status_info += f" ({task.error[:50]}...)" if len(task.error) > 50 else f" ({task.error})"
                    reminder = (
                        f"PFC Task {task_id} "
                        f"(description: {display_info}) "
                        f"Has finished with status: {status_info}. "
                        f"Use pfc_check_task_status('{task_id}') to see results."
                    )
                    reminders.append(reminder)

                # Case 3: Already notified - no more reminders

            return reminders

    def cleanup_session(self, session_id: str) -> None:
        """Clean up all tasks for a session.

        Args:
            session_id: Session ID to clean up
        """
        with self._lock:
            if session_id not in self.session_tasks:
                return

            task_ids = list(self.session_tasks[session_id])
            for task_id in task_ids:
                if task_id in self.tasks:
                    del self.tasks[task_id]

            del self.session_tasks[session_id]

    def cleanup_old_tasks(self) -> None:
        """Remove old completed tasks to prevent memory leaks."""
        with self._lock:
            cutoff_time = datetime.now() - timedelta(hours=6)
            tasks_to_remove = []

            for task_id, task in self.tasks.items():
                # Remove old completed tasks
                if task.is_terminal and task.last_accessed < cutoff_time:
                    tasks_to_remove.append(task_id)

                # Mark stale running tasks (pfc-bridge may have restarted)
                elif (task.status in ("pending", "submitted", "running") and
                      task.start_time < datetime.now() - timedelta(hours=self.TASK_TIMEOUT_HOURS)):
                    task.status = "failed"
                    task.error = "Task timed out (pfc-bridge may have restarted)"
                    task.end_time = datetime.now()

            # Remove old tasks
            for task_id in tasks_to_remove:
                task = self.tasks[task_id]
                session_id = task.session_id

                del self.tasks[task_id]

                if session_id in self.session_tasks:
                    self.session_tasks[session_id].discard(task_id)
                    if not self.session_tasks[session_id]:
                        del self.session_tasks[session_id]


# Singleton instance
_task_manager: Optional[PfcTaskManager] = None


def get_pfc_task_manager() -> PfcTaskManager:
    """Get the global PFC task manager instance."""
    global _task_manager
    if _task_manager is None:
        _task_manager = PfcTaskManager()
    return _task_manager


def cleanup_session_tasks(session_id: str) -> None:
    """Clean up all PFC tasks for a session."""
    manager = get_pfc_task_manager()
    manager.cleanup_session(session_id)
