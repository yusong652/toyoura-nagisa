"""
Task Type Implementations - Script execution task class.

This module contains ScriptTask implementation, providing type-specific
behavior for Python script execution with real-time output capture.

Python 3.6 compatible implementation.
"""

import logging
from typing import Any, Dict, Optional

from .task_base import Task
from ..utils import TaskDataBuilder, build_response

# Module logger
logger = logging.getLogger("PFC-Server")


class ScriptTask(Task):
    """
    Task for Python script execution.

    Enhanced task type with real-time output capture via FileBuffer,
    suitable for long-running simulations with progress monitoring.
    Output is written directly to disk for complete preservation.
    Includes git-based version tracking via git_commit.
    """

    def __init__(self, task_id, session_id, future, script_name, script_path=None, output_buffer=None, description=None, on_status_change=None, git_commit=None, source="agent"):
        # type: (str, str, Any, str, Optional[str], Any, Optional[str], Any, Optional[str], str) -> None
        """
        Initialize script task.

        Args:
            task_id: Unique task identifier
            session_id: Session identifier for task isolation
            future: asyncio Future object for the task
            script_name: Name of the script file (e.g., "main.py")
            script_path: Optional full path to entry script for reference
            output_buffer: Optional FileBuffer for output capture (writes to disk)
            description: Task description from PFC agent (LLM-provided)
            on_status_change: Optional callback function(task) called when task status changes
            git_commit: Git commit hash on pfc-executions branch (version snapshot)
            source: Task source identifier ("agent" or "user_console")
        """
        # Use agent-provided description (default to empty string if None)
        super(ScriptTask, self).__init__(task_id, session_id, future, description or "", "script", on_status_change)
        self.script_name = script_name
        self.script_path = script_path  # Entry script path
        self.output_buffer = output_buffer
        self.git_commit = git_commit  # Git version snapshot
        self.source = source  # Task source: "agent" or "user_console"

        # Extract log path from FileBuffer for persistence
        self.log_path = None  # type: Optional[str]
        if output_buffer and hasattr(output_buffer, 'get_path'):
            self.log_path = output_buffer.get_path()

        logger.info("✓ Script task registered: {} (ID: {}, Session: {})".format(
            script_name, task_id, session_id
        ))

    def get_current_output(self):
        # type: () -> Optional[str]
        """Get current output from buffer (for running scripts)."""
        if self.output_buffer:
            try:
                return self.output_buffer.getvalue()
            except Exception as e:
                logger.warning("Failed to read output buffer: {}".format(e))
        return None

    def get_status_response(self):
        # type: () -> Dict[str, Any]
        """Get script task status with output and result data."""
        elapsed_time = self.get_elapsed_time()
        current_status = self.status  # Use property to get real-time status

        if current_status in ("pending", "running"):
            # Task pending or executing - include current output
            current_output = self.get_current_output()

            data = (TaskDataBuilder(
                    self.task_id, self.task_type, self.source,
                    self.script_name, self.script_path, self.description
                )
                .with_session(self.session_id)
                .with_git_commit(self.git_commit)
                .with_timing(self.start_time, elapsed_time=elapsed_time)
                .with_output(current_output)
                .build())

            # Message based on status
            if current_status == "pending":
                message = "Script queued (waiting for main thread): {}\nWaiting time: {:.2f}s".format(
                    self.description, elapsed_time
                )
            else:
                message = "Script executing: {}\nElapsed time: {:.2f}s".format(
                    self.description, elapsed_time
                )

            return build_response(current_status, message, data)

        # Task completed or failed - retrieve result for status/data only
        # Output is ALWAYS retrieved from buffer (single source of truth)
        try:
            result = self.future.result(timeout=0)
        except Exception as e:
            result = None
            if current_status == "completed":
                logger.warning("Status mismatch for task {}: status='completed' but future raised: {}".format(
                    self.task_id, str(e)
                ))

        if current_status == "completed":
            # Script completed successfully
            logger.info("✓ Task completed: {} (ID: {}, Time: {:.2f}s)".format(
                self.description, self.task_id, elapsed_time
            ))

            # Get output from buffer (single source of truth)
            output_text = self.get_current_output()

            # Extract only status and result from execution response
            result_data = None
            result_status = "success"

            if isinstance(result, dict):
                result_data = result.get("result")
                result_status = result.get("status", "success")
            else:
                result_data = result

            # Serialize result data
            serialized_result = self._serialize_result(result_data)

            # Build message with output
            if output_text:
                message = "Script execution completed: {}\nElapsed time: {:.2f}s\n\n=== Script Output ===\n{}".format(
                    self.script_name, elapsed_time, output_text
                )
            elif serialized_result is not None:
                message = "Script completed: {}\nElapsed time: {:.2f}s\nResult: {}".format(
                    self.description, elapsed_time, serialized_result
                )
            else:
                message = "Script completed: {}\nElapsed time: {:.2f}s".format(
                    self.description, elapsed_time
                )

            data = (TaskDataBuilder(
                    self.task_id, self.task_type, self.source,
                    self.script_name, self.script_path, self.description
                )
                .with_session(self.session_id)
                .with_git_commit(self.git_commit)
                .with_timing(self.start_time, self.end_time, elapsed_time)
                .with_output(output_text if output_text else "")
                .with_result(serialized_result)
                .build())

            return build_response(result_status, message, data)

        elif current_status == "interrupted":
            # Script was interrupted by user
            logger.info("⊘ Script task interrupted: {} (ID: {}, Time: {:.2f}s)".format(
                self.description, self.task_id, elapsed_time
            ))

            # Get output from buffer (single source of truth)
            output_text = self.get_current_output()

            # Build interrupted message with partial output
            if output_text:
                message = "Script interrupted by user: {}\nElapsed time: {:.2f}s\n\n=== Partial Output ===\n{}".format(
                    self.script_name, elapsed_time, output_text
                )
            else:
                message = "Script interrupted by user: {}\nElapsed time: {:.2f}s".format(
                    self.description, elapsed_time
                )

            data = (TaskDataBuilder(
                    self.task_id, self.task_type, self.source,
                    self.script_name, self.script_path, self.description
                )
                .with_session(self.session_id)
                .with_git_commit(self.git_commit)
                .with_timing(self.start_time, self.end_time, elapsed_time)
                .with_output(output_text if output_text else "")
                .build())

            return build_response("interrupted", message, data)

        else:  # status == "failed"
            # Script failed
            logger.error("✗ Script task failed: {} (ID: {})".format(self.description, self.task_id))

            # Get output from buffer (single source of truth)
            output_text = self.get_current_output()

            # Use error from task object (extracted in _on_complete and persisted)
            error_msg = self.error or "Task execution failed"

            # Build error message with partial output
            if output_text:
                message = "Script execution failed: {}\nElapsed time: {:.2f}s\nError: {}\n\n=== Partial Output ===\n{}".format(
                    self.script_name, elapsed_time, error_msg, output_text
                )
            else:
                message = "Script failed: {}\nElapsed time: {:.2f}s\nError: {}".format(
                    self.description, elapsed_time, error_msg
                )

            data = (TaskDataBuilder(
                    self.task_id, self.task_type, self.source,
                    self.script_name, self.script_path, self.description
                )
                .with_session(self.session_id)
                .with_git_commit(self.git_commit)
                .with_timing(self.start_time, self.end_time, elapsed_time)
                .with_output(output_text if output_text else "")
                .with_error(error_msg)
                .build())

            return build_response("error", message, data)

    def get_task_info(self):
        # type: () -> Dict[str, Any]
        """Get script task summary for listing."""
        info = {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "task_type": self.task_type,
            "source": self.source,  # Task source: "agent" or "user_console"
            "description": self.description,  # Agent-provided task description
            "status": self.status,
            "elapsed_time": self.get_elapsed_time(),
            "start_time": self.start_time,
            "name": self.script_name,  # Script file name (for backward compatibility)
            "entry_script": self.script_path,  # Entry script path (new naming)
            "script_path": self.script_path,  # Absolute path for LLM (backward compatibility)
            "git_commit": self.git_commit,  # Git version snapshot
            "notified": self.notified  # Whether completion notification has been sent
        }
        # Add end_time for completed/failed/interrupted tasks
        if self.status in ["completed", "failed", "interrupted"] and self.end_time is not None:
            info["end_time"] = self.end_time
        return info
