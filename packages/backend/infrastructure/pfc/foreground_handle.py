"""PFC Foreground Execution Handle for ctrl+b signal handling.

Provides interruptible wait for foreground PFC task execution:
- Wait for task completion OR move-to-background signal
- Timeout handling with automatic conversion to background
- Polling pfc-server for status updates (not local cache)

Mirrors ForegroundExecutionHandle from shell module.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional, Union, Any, Callable, Awaitable


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


# Type alias for the status polling callback
# Returns (is_terminal, status, output, result, error, git_commit)
StatusPollResult = tuple[bool, str, str, Optional[Any], Optional[str], Optional[str]]
StatusPollCallback = Callable[[str], Awaitable[StatusPollResult]]


@dataclass
class PfcForegroundExecutionHandle:
    """Handle for foreground PFC task execution with interruptible wait.

    Supports ctrl+b to move the task to background without stopping it.
    The wait() method returns either:
    - PfcForegroundExecutionResult (normal completion)
    - PfcMoveToBackgroundRequest (user requested background conversion)

    Key differences from shell ForegroundExecutionHandle:
    - No local subprocess; task runs remotely on pfc-server
    - Polls pfc-server for status (via callback) instead of waiting on Future
    - Status polling callback provided at construction time
    """
    task_id: str
    poll_status_callback: StatusPollCallback  # Callback to poll pfc-server
    timeout_seconds: Optional[float] = None   # None = no timeout
    poll_interval_seconds: float = 2.0        # Status polling interval

    # Internal state
    _move_to_bg_event: asyncio.Event = field(default_factory=asyncio.Event)
    _completion_event: asyncio.Event = field(default_factory=asyncio.Event)
    _last_status: str = field(default="running")
    _last_output: str = field(default="")
    _last_result: Optional[Any] = field(default=None)
    _last_error: Optional[str] = field(default=None)
    _last_git_commit: Optional[str] = field(default=None)
    _elapsed_seconds: float = field(default=0.0)

    def request_move_to_background(self) -> None:
        """Signal the wait() method to return PfcMoveToBackgroundRequest.

        Called by PfcForegroundTaskRegistry when user presses ctrl+b.
        """
        self._move_to_bg_event.set()

    async def _poll_status(self) -> None:
        """Poll pfc-server for task status until completion or interruption."""
        import time
        start_time = time.time()

        while not self._completion_event.is_set() and not self._move_to_bg_event.is_set():
            try:
                # Poll pfc-server via callback
                is_terminal, status, output, result, error, git_commit = await self.poll_status_callback(self.task_id)

                # Update cached state
                self._last_status = status
                self._last_output = output
                self._last_result = result
                self._last_error = error
                self._last_git_commit = git_commit
                self._elapsed_seconds = time.time() - start_time

                if is_terminal:
                    self._completion_event.set()
                    return

            except Exception as e:
                # Log but continue polling on transient errors
                print(f"[PfcForegroundHandle] Poll error: {e}")

            await asyncio.sleep(self.poll_interval_seconds)

    async def wait(self) -> Union[PfcForegroundExecutionResult, PfcMoveToBackgroundRequest]:
        """Wait for task completion or move-to-background signal.

        Returns:
            PfcForegroundExecutionResult: Task completed normally
            PfcMoveToBackgroundRequest: User pressed ctrl+b or timeout

        Note:
            Unlike bash tasks, PFC tasks continue running on pfc-server
            even when moved to background. The move-to-background just
            changes how the backend tracks and reports the task.
        """
        # Task 1: Poll pfc-server for task completion
        poll_task = asyncio.create_task(self._poll_status())
        # Task 2: Wait for move-to-background signal
        signal_task = asyncio.create_task(self._move_to_bg_event.wait())

        try:
            done, pending = await asyncio.wait(
                [poll_task, signal_task],
                timeout=self.timeout_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Case 1: Move-to-background signal received
            if signal_task in done:
                poll_task.cancel()
                return PfcMoveToBackgroundRequest(
                    task_id=self.task_id,
                    reason="user_request"
                )

            # Case 2: Timeout (neither completed)
            if not done:
                poll_task.cancel()
                signal_task.cancel()
                # Task continues in background on pfc-server
                return PfcMoveToBackgroundRequest(
                    task_id=self.task_id,
                    reason="timeout"
                )

            # Case 3: Task completed (poll_task finished)
            signal_task.cancel()

            return PfcForegroundExecutionResult(
                task_id=self.task_id,
                status=self._last_status,
                output=self._last_output,
                result=self._last_result,
                error=self._last_error,
                elapsed_seconds=self._elapsed_seconds,
                git_commit=self._last_git_commit,
            )

        except asyncio.CancelledError:
            poll_task.cancel()
            signal_task.cancel()
            raise
        except Exception as e:
            poll_task.cancel()
            signal_task.cancel()
            # Return error result instead of raising
            return PfcForegroundExecutionResult(
                task_id=self.task_id,
                status="failed",
                output="",
                error=f"Wait failed: {type(e).__name__}: {e}",
            )
