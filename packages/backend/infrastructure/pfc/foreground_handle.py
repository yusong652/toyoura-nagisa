"""PFC Foreground Execution Handle for ctrl+b signal handling.

Provides interruptible wait for foreground PFC task execution:
- Wait for task completion OR move-to-background signal
- No polling logic - polling is handled by PfcTaskNotificationService
- Receives completion signal from notification service

Mirrors ForegroundExecutionHandle from shell module.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional, Union, Any


@dataclass
class PfcMoveToBackgroundRequest:
    """Request to move PFC task to background.

    Returned by PfcForegroundExecutionHandle.wait() when user triggers ctrl+b.
    This is a normal control flow result, not an exception.
    """
    task_id: str
    reason: str = "user_request"  # "user_request" or "timeout"


@dataclass
class PfcForegroundExecutionResult:
    """Result of foreground PFC task execution."""
    task_id: str
    status: str  # "completed", "failed", "interrupted"
    output: str
    result: Optional[Any] = None
    error: Optional[str] = None
    elapsed_seconds: float = 0.0
    git_commit: Optional[str] = None


@dataclass
class PfcForegroundExecutionHandle:
    """Handle for foreground PFC task execution with interruptible wait.

    Supports ctrl+b to move the task to background without stopping it.
    The wait() method returns either:
    - PfcForegroundExecutionResult (normal completion)
    - PfcMoveToBackgroundRequest (user requested background conversion)

    This handle does NOT poll - it only waits for signals:
    - Completion signal from PfcTaskNotificationService
    - Move-to-background signal from ctrl+b handler

    The polling and notification logic is centralized in PfcTaskNotificationService.
    """
    task_id: str
    timeout_seconds: Optional[float] = None  # None = no timeout

    # Internal state - set by external signals
    _move_to_bg_event: asyncio.Event = field(default_factory=asyncio.Event)
    _completion_event: asyncio.Event = field(default_factory=asyncio.Event)

    # Result data - set by notification service when signaling completion
    _status: str = field(default="running")
    _output: str = field(default="")
    _result: Optional[Any] = field(default=None)
    _error: Optional[str] = field(default=None)
    _git_commit: Optional[str] = field(default=None)
    _elapsed_seconds: float = field(default=0.0)

    def request_move_to_background(self) -> None:
        """Signal the wait() method to return PfcMoveToBackgroundRequest.

        Called by PfcForegroundTaskRegistry when user presses ctrl+b.
        """
        self._move_to_bg_event.set()

    def signal_completion(
        self,
        status: str,
        output: str,
        elapsed_seconds: float,
        result: Optional[Any] = None,
        error: Optional[str] = None,
        git_commit: Optional[str] = None,
    ) -> None:
        """Signal that the task has completed.

        Called by PfcTaskNotificationService when task reaches terminal state.

        Args:
            status: Final task status (completed/failed/interrupted)
            output: Full task output
            elapsed_seconds: Total elapsed time
            result: Script result (if any)
            error: Error message (if failed)
            git_commit: Git commit hash (if any)
        """
        self._status = status
        self._output = output
        self._elapsed_seconds = elapsed_seconds
        self._result = result
        self._error = error
        self._git_commit = git_commit
        self._completion_event.set()

    def update_elapsed(self, elapsed_seconds: float) -> None:
        """Update elapsed time (called periodically by notification service).

        Args:
            elapsed_seconds: Current elapsed time
        """
        self._elapsed_seconds = elapsed_seconds

    async def wait(self) -> Union[PfcForegroundExecutionResult, PfcMoveToBackgroundRequest]:
        """Wait for task completion or move-to-background signal.

        This method does NOT poll - it waits for external signals:
        - PfcTaskNotificationService signals completion via signal_completion()
        - ctrl+b handler signals via request_move_to_background()

        Returns:
            PfcForegroundExecutionResult: Task completed normally
            PfcMoveToBackgroundRequest: User pressed ctrl+b or timeout
        """
        # Create tasks for both events
        completion_task = asyncio.create_task(self._completion_event.wait())
        signal_task = asyncio.create_task(self._move_to_bg_event.wait())

        try:
            done, pending = await asyncio.wait(
                [completion_task, signal_task],
                timeout=self.timeout_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel pending tasks
            for task in pending:
                task.cancel()

            # Case 1: Move-to-background signal received (ctrl+b)
            if signal_task in done:
                return PfcMoveToBackgroundRequest(
                    task_id=self.task_id,
                    reason="user_request"
                )

            # Case 2: Timeout (neither completed)
            if not done:
                return PfcMoveToBackgroundRequest(
                    task_id=self.task_id,
                    reason="timeout"
                )

            # Case 3: Task completed
            return PfcForegroundExecutionResult(
                task_id=self.task_id,
                status=self._status,
                output=self._output,
                result=self._result,
                error=self._error,
                elapsed_seconds=self._elapsed_seconds,
                git_commit=self._git_commit,
            )

        except asyncio.CancelledError:
            completion_task.cancel()
            signal_task.cancel()
            raise
        except Exception as e:
            completion_task.cancel()
            signal_task.cancel()
            # Return error result instead of raising
            return PfcForegroundExecutionResult(
                task_id=self.task_id,
                status="failed",
                output="",
                error=f"Wait failed: {type(e).__name__}: {e}",
            )
