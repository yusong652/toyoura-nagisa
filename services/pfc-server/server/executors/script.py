"""
PFC Script Executor - Executes Python SDK scripts with direct API access.

This module provides script execution functionality using PFC Python SDK via
main thread queue, enabling queries and operations that return values.

Includes git-based version tracking: creates execution snapshots on
pfc-executions branch before each script execution.

Python 3.6 compatible implementation.
"""

import asyncio
import concurrent.futures
import logging
import os
import sys
import time
import traceback
import uuid
from typing import Any, Dict, Optional

from .main_thread import MainThreadExecutor
from ..utils import path_to_llm_format, FileBuffer
from ..managers import get_git_manager, set_current_task, clear_current_task, clear_interrupt

# Module logger
logger = logging.getLogger("PFC-Server")


class PFCScriptExecutor:
    """Execute Python scripts using PFC Python SDK via main thread queue."""

    def __init__(self, main_executor, task_manager):
        # type: (MainThreadExecutor, Any) -> None
        """
        Initialize executor with itasca module, main thread executor, and task manager.

        Args:
            main_executor: Main thread executor for queue-based execution
            task_manager: Task manager for long-running task tracking
        """
        self.main_executor = main_executor
        self.task_manager = task_manager

        try:
            import itasca  # type: ignore
            self.itasca = itasca
        except ImportError:
            logger.warning("⚠ ITASCA SDK not available for script execution")
            self.itasca = None

    def _execute_script_sync(self, script_path, script_content, output_buffer, task_id):
        # type: (str, str, Any, str) -> Dict[str, Any]
        """
        Execute Python script synchronously (called in main thread).

        Captures stdout during execution for progress tracking using shared buffer.
        Supports interruption via registered PFC callback.

        Args:
            script_path: Path to script (for error messages)
            script_content: Script content to execute
            output_buffer: FileBuffer for capturing stdout (shared with TaskManager)
            task_id: Task ID for interrupt checking

        Returns:
            Result dictionary with status, message, data, and output:
                - status: "success", "error", or "interrupted"
                - message: User-friendly message
                - data: Script result (from 'result' variable)
                - output: Captured stdout content (print statements)
        """
        # Use shared output buffer for stdout capture
        old_stdout = sys.stdout
        sys.stdout = output_buffer

        # Set current task for interrupt callback
        set_current_task(task_id)

        try:
            # Use IPython's global namespace for persistent state across scripts
            # This enables:
            # - Variables persist between script executions
            # - Imports are reused (no repeated import overhead)
            # - if __name__ == "__main__": works correctly
            # - Scripts share state with IPython Console
            import __main__
            exec_globals = __main__.__dict__

            # Ensure itasca is available in global namespace
            if "itasca" not in exec_globals:
                exec_globals["itasca"] = self.itasca

            # Set __file__ to current script path (updates each execution)
            exec_globals["__file__"] = script_path

            # Try to execute as expression first (single line, returns value)
            try:
                # Use compile() with script_path for better traceback
                code_obj = compile(script_content, script_path, 'eval')
                result = eval(code_obj, exec_globals, exec_globals)
            except SyntaxError:
                # If eval fails, try exec (multi-line script)
                # Use compile() with script_path to show actual file path in traceback
                code_obj = compile(script_content, script_path, 'exec')
                exec(code_obj, exec_globals, exec_globals)
                # Look for 'result' variable in global namespace
                result = exec_globals.get('result', None)

            # Get captured output from shared buffer
            output_text = output_buffer.getvalue()

            # Serialize result for response
            serialized_result = self._serialize_result(result)

            # Build message with result
            script_name = os.path.basename(script_path)
            if serialized_result is not None:
                message = "Script executed: {}\nResult: {}".format(
                    script_name, serialized_result
                )
            else:
                message = "Script executed: {}".format(script_name)

            return {
                "status": "success",
                "message": message,
                "data": serialized_result,
                "output": output_text  # Include captured output
            }

        except InterruptedError as e:
            # Task was interrupted by user via callback (direct raise)
            output_text = output_buffer.getvalue()
            logger.info("Script interrupted: {} - {}".format(script_path, str(e)))

            return {
                "status": "interrupted",
                "message": "Script interrupted by user: {}".format(str(e)),
                "data": None,
                "output": output_text  # Include output up to interruption point
            }

        except ValueError as e:
            # PFC wraps callback exceptions in ValueError
            # Check if this is a wrapped InterruptedError from our callback
            error_str = str(e)
            if "InterruptedError" in error_str and "_pfc_interrupt_check" in error_str:
                output_text = output_buffer.getvalue()
                logger.info("Script interrupted (via PFC callback): {}".format(script_path))

                return {
                    "status": "interrupted",
                    "message": "Script interrupted by user",
                    "data": None,
                    "output": output_text  # Include output up to interruption point
                }

            # Not an interrupt - re-raise as regular exception
            raise

        except Exception as e:
            # Get captured output even on error
            output_text = output_buffer.getvalue()

            # Capture complete stack trace for server logging (debugging)
            full_traceback = traceback.format_exc()
            logger.error("Script execution failed with traceback:\n{}".format(full_traceback))

            # Extract only user script frames (filter out server implementation)
            # This prevents exposing backend code to LLM
            tb = sys.exc_info()[2]
            user_frames = []

            # Walk through traceback to find user script frames
            while tb is not None:
                frame = tb.tb_frame
                filename = frame.f_code.co_filename
                # Only include frames from user script (not server code)
                if filename == script_path or filename == '<string>':
                    user_frames.append((
                        filename,
                        tb.tb_lineno,
                        frame.f_code.co_name,
                        None  # No source line (not available for dynamic code)
                    ))
                tb = tb.tb_next

            # Build user-facing error message with filtered traceback
            # Normalize path to LLM-friendly format (forward slashes) using utility
            display_path = path_to_llm_format(script_path)

            if user_frames:
                # Format user script traceback with absolute path in LLM-friendly format
                error_parts = ["Script execution failed:\n"]
                for filename, lineno, name, line in user_frames:
                    # Use absolute path with forward slashes for cross-platform consistency
                    error_parts.append('  File "{}", line {}, in {}\n'.format(
                        display_path, lineno, name
                    ))
                error_parts.append("{}: {}".format(type(e).__name__, str(e)))
                error_message = "".join(error_parts)
            else:
                # Fallback if no user frames found (shouldn't happen)
                error_message = "Script execution failed: {}: {}".format(
                    type(e).__name__, str(e)
                )

            return {
                "status": "error",
                "message": error_message,
                "data": None,
                "output": output_text  # Include output up to error point
            }

        finally:
            # Always restore stdout
            sys.stdout = old_stdout
            # Clear current task and interrupt flag
            clear_current_task()
            clear_interrupt(task_id)

    async def execute_script(self, session_id, script_path, description, timeout_ms=None, run_in_background=True, source="agent", enable_git_snapshot=True):
        # type: (str, str, str, Optional[int], bool, str, bool) -> Dict[str, Any]
        """
        Execute Python script with flexible execution control.

        Execution modes:
        - Asynchronous (run_in_background=True, default): Submit as background task, return task_id immediately
        - Synchronous (run_in_background=False): Wait for completion, return result with timeout

        Args:
            session_id: Session identifier for task isolation and persistence
            script_path: Absolute path to Python script file
                Example: "/path/to/pfc_project/scripts/analyze_balls.py"
            description: Task description from PFC agent (LLM-provided)
                Example: "Phase 2: Settling simulation with 50k particles"
            timeout_ms: Script execution timeout in milliseconds (only for synchronous mode)
                - None (default): No timeout limit for production simulations
                - 1000-600000: Custom timeout (1 second to 10 minutes) for testing
            run_in_background: Background execution control (default: True - production mode)
                - True: Asynchronous - return task_id immediately, query via check_task_status
                - False: Synchronous - wait for completion, return result directly
            source: Task source identifier (default: "agent")
                - "agent": Script created/executed by LLM agent (git snapshot enabled)
                - "user_console": Script from user Python console (no git snapshot)
                - "diagnostic": Diagnostic tool operation like plot capture (no git snapshot)
            enable_git_snapshot: Whether to create git snapshot before execution (default: True)
                - True: Create git commit on pfc-executions branch (for agent scripts)
                - False: Skip git snapshot (for quick console commands and diagnostic tools)
                - Note: Automatically set to False for source="user_console" or "diagnostic"

        Returns:
            Result dictionary:
                For asynchronous execution (run_in_background=True):
                    - status: "pending" - Task submitted successfully
                    - message: str - Submission confirmation message
                    - data: Dict with task_id and script_path
                For synchronous execution (run_in_background=False):
                    - status: "success" or "error"
                    - message: str - Execution result message
                    - data: Script result data
                    - output: Captured stdout from script

        Note:
            - Scripts are executed in IPython main thread via queue
            - Script must define 'result' variable for structured data
            - Print statements are captured and available in output
            - Script has access to 'itasca' module in global scope
        """
        # Initialize variables for exception handling
        task_id = None
        output_buffer = None
        git_commit = None
        script_name = os.path.basename(script_path)

        try:
            # Read script file
            with open(script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()
        except FileNotFoundError:
            return {
                "status": "error",
                "message": "Script file not found: {}".format(script_path),
                "data": None
            }
        except Exception as e:
            return {
                "status": "error",
                "message": "Failed to read script file: {}".format(str(e)),
                "data": None
            }

        try:
            # Generate task_id early (needed for log path, git commit, and interrupt tracking)
            task_id = uuid.uuid4().hex[:8]

            # Create output log file for complete output preservation
            # Path: .nagisa/sessions/{session_id}/logs/task_{task_id}.log
            log_dir = os.path.join(".nagisa", "sessions", session_id, "logs")
            log_path = os.path.join(log_dir, "task_{}.log".format(task_id))
            output_buffer = FileBuffer(log_path)

            # Create git execution snapshot (before running script)
            # This captures the exact code state that will be executed
            # Skip for quick console commands (enable_git_snapshot=False)
            # Use script_path to find the correct git repository (user's PFC project)
            git_commit = None
            if enable_git_snapshot:
                git_manager = get_git_manager(script_path)
                if git_manager.is_git_available():
                    git_commit = git_manager.create_execution_commit(
                        task_id=task_id,
                        description=description,
                        entry_script=script_path
                    )

            # Submit to main thread queue
            future = self.main_executor.submit(
                self._execute_script_sync,
                script_path,
                script_content,
                output_buffer,
                task_id
            )

            # Register task with manager (both modes need this)
            submit_time = time.time()
            self.task_manager.create_script_task(
                session_id,
                future,
                script_name,
                script_path,
                output_buffer,
                description,
                git_commit,
                source,
                task_id
            )

            if run_in_background:
                # Asynchronous: return immediately
                return {
                    "status": "pending",
                    "message": "Script submitted: {}".format(script_name),
                    "data": {
                        "task_id": task_id,
                        "task_type": "script",
                        "source": source,
                        "script_name": script_name,
                        "entry_script": script_path,
                        "script_path": script_path,
                        "description": description,
                        "start_time": submit_time,
                        "git_commit": git_commit
                    }
                }

            # Synchronous: wait for completion
            timeout_seconds = timeout_ms / 1000.0 if timeout_ms else None
            logger.debug("Executing script synchronously: {} [timeout={}s]".format(
                script_name, timeout_seconds if timeout_seconds else "None"
            ))

            loop = asyncio.get_event_loop()
            result_dict = await loop.run_in_executor(
                None,
                future.result,
                timeout_seconds
            )

            # Get result and timing info
            full_output = output_buffer.getvalue()
            task = self.task_manager.tasks.get(task_id)
            start_time = task.start_time if task else None
            end_time = task.end_time if task else None
            elapsed_time = (end_time - start_time) if (start_time and end_time) else 0

            return {
                "status": result_dict.get("status", "success"),
                "message": result_dict.get("message", "Script executed"),
                "data": {
                    "task_id": task_id,
                    "task_type": "script",
                    "source": source,
                    "script_name": script_name,
                    "entry_script": script_path,
                    "script_path": script_path,
                    "description": description,
                    "start_time": start_time,
                    "end_time": end_time,
                    "elapsed_time": elapsed_time,
                    "output": full_output,
                    "result": result_dict.get("data"),
                    "git_commit": git_commit
                }
            }

        except Exception as e:
            # Special handling for timeout errors
            # Python 3.6+: concurrent.futures.TimeoutError is an alias of TimeoutError
            is_timeout = isinstance(e, (concurrent.futures.TimeoutError, TimeoutError))

            if is_timeout:
                # Script execution timed out but task is still running in background
                # Return "pending" status to unify with background mode handling
                # This allows the tool layer to use the same code path for both cases
                logger.warning("Script execution timed out (still running): {} (timeout: {}ms)".format(script_path, timeout_ms))

                task = self.task_manager.tasks.get(task_id) if task_id else None
                timeout_message = "Foreground wait timed out after {}ms. Task '{}' continues in background.".format(
                    timeout_ms, script_name
                )

                return {
                    "status": "pending",
                    "message": timeout_message,
                    "data": {
                        "task_id": task_id,
                        "task_type": "script",
                        "source": source,
                        "script_name": script_name,
                        "entry_script": script_path,
                        "script_path": script_path,
                        "description": description,
                        "start_time": task.start_time if task else None,
                        "elapsed_time": task.get_elapsed_time() if task else None,
                        "output": output_buffer.getvalue() if output_buffer else "",
                        "git_commit": git_commit
                    }
                }

            # General error handling
            logger.error("Script execution failed: {}".format(e))

            error_message = "Script execution failed: {}".format(str(e))
            task = self.task_manager.tasks.get(task_id) if task_id else None
            output_text = output_buffer.getvalue() if output_buffer else ""

            return {
                "status": "error",
                "message": error_message,
                "data": {
                    "task_id": task_id,
                    "task_type": "script",
                    "script_name": script_name,
                    "entry_script": script_path,
                    "script_path": script_path,
                    "description": description,
                    "start_time": task.start_time if task else None,
                    "end_time": task.end_time if task else None,
                    "elapsed_time": (task.end_time - task.start_time) if (task and task.start_time and task.end_time) else None,
                    "output": output_text,
                    "error": error_message,
                    "git_commit": git_commit
                }
            }

    def _serialize_result(self, result: Any) -> Any:
        """
        Convert PFC objects to JSON-serializable format.

        Args:
            result: Any Python object returned from script execution

        Returns:
            JSON-serializable representation of the result
        """
        if result is None:
            return None
        elif isinstance(result, (str, int, float, bool)):
            return result
        elif isinstance(result, (list, tuple)):
            return [self._serialize_result(item) for item in result]
        elif isinstance(result, dict):
            return {k: self._serialize_result(v) for k, v in result.items()}
        else:
            # For complex PFC objects, return string representation
            return str(result)
