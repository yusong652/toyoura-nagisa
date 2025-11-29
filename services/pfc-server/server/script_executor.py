"""
PFC Script Executor - Executes Python SDK scripts with direct API access.

This module provides script execution functionality using PFC Python SDK via
main thread queue, enabling queries and operations that return values.

Includes git-based version tracking: creates execution snapshots on
pfc-executions branch before each script execution.

Python 3.6 compatible implementation.
"""

import asyncio
import logging
import sys
import time
import traceback
from io import StringIO
from typing import Any, Dict, Optional

from .main_thread_executor import MainThreadExecutor
from .utils import path_to_llm_format
from .git_version_manager import get_git_manager

# Module logger
logger = logging.getLogger("PFC-Server")

# Script execution timeout configuration
MAX_SCRIPT_TIMEOUT_MS = 600000  # 10 minutes maximum for synchronous scripts


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
            logger.info("✓ ITASCA SDK loaded for script execution")
        except ImportError:
            logger.warning("⚠ ITASCA SDK not available for script execution")
            self.itasca = None

    def _execute_script_sync(self, script_path, script_content, output_buffer):
        # type: (str, str, Any) -> Dict[str, Any]
        """
        Execute Python script synchronously (called in main thread).

        Captures stdout during execution for progress tracking using shared buffer.

        Args:
            script_path: Path to script (for error messages)
            script_content: Script content to execute
            output_buffer: StringIO buffer for capturing stdout (shared with TaskManager)

        Returns:
            Result dictionary with status, message, data, and output:
                - status: "success" or "error"
                - message: User-friendly message
                - data: Script result (from 'result' variable)
                - output: Captured stdout content (print statements)
        """
        import os

        # Use shared output buffer for stdout capture
        old_stdout = sys.stdout
        sys.stdout = output_buffer

        try:
            logger.info("Executing Python script in main thread: {}".format(script_path))

            # Prepare execution context with itasca module
            # Use single namespace for both globals and locals to ensure imported modules
            # are accessible within function definitions (solves import scoping issue)
            exec_context = {"itasca": self.itasca}

            # Try to execute as expression first (single line, returns value)
            try:
                # Use compile() with script_path for better traceback
                code_obj = compile(script_content, script_path, 'eval')
                result = eval(code_obj, exec_context, exec_context)
            except SyntaxError:
                # If eval fails, try exec (multi-line script)
                # Use compile() with script_path to show actual file path in traceback
                code_obj = compile(script_content, script_path, 'exec')
                exec(code_obj, exec_context, exec_context)
                # Look for 'result' variable in context
                result = exec_context.get('result', None)

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

    async def execute_script(self, session_id, script_path, description, timeout_ms=None, run_in_background=True):
        # type: (str, str, str, Optional[int], bool) -> Dict[str, Any]
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
        import os

        try:
            if not self.itasca:
                return {
                    "status": "error",
                    "message": "ITASCA SDK not available: Server not running in PFC GUI environment",
                    "data": None
                }

            # Read script file
            logger.info("Reading script file: {}".format(script_path))
            try:
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

            # Validate timeout if provided for synchronous mode
            if not run_in_background and timeout_ms is not None:
                if timeout_ms < 1000:
                    return {
                        "status": "error",
                        "message": "Timeout must be at least 1000ms (1 second)",
                        "data": None
                    }
                elif timeout_ms > MAX_SCRIPT_TIMEOUT_MS:
                    return {
                        "status": "error",
                        "message": "Timeout cannot exceed {}ms ({} minutes)".format(
                            MAX_SCRIPT_TIMEOUT_MS, MAX_SCRIPT_TIMEOUT_MS // 60000
                        ),
                        "data": None
                    }

            script_name = os.path.basename(script_path)

            # Create shared output buffer for real-time output capture
            output_buffer = StringIO()

            # Create git execution snapshot (before running script)
            # This captures the exact code state that will be executed
            git_manager = get_git_manager()
            exec_commit = None
            if git_manager.is_git_available():
                # Generate task_id early for commit message
                import uuid
                task_id_preview = uuid.uuid4().hex[:8]
                exec_commit = git_manager.create_execution_commit(
                    task_id=task_id_preview,
                    description=description,
                    entry_script=script_path
                )
                if exec_commit:
                    logger.info("✓ Created execution snapshot: {} for task {}".format(
                        exec_commit[:8], task_id_preview
                    ))
            else:
                logger.warning("Git not available - skipping version snapshot")

            # Submit to main thread queue
            future = self.main_executor.submit(
                self._execute_script_sync,
                script_path,
                script_content,
                output_buffer  # Pass shared buffer to executor
            )

            if run_in_background:
                # Asynchronous execution: register with task manager and return immediately
                logger.info("Submitting script as background task: {}".format(script_name))

                submit_time = time.time()
                task_id = self.task_manager.create_script_task(
                    session_id,
                    future,
                    script_name,
                    script_path,
                    output_buffer,  # Pass buffer reference for live status queries
                    description,  # Agent-provided task description
                    exec_commit  # Git version snapshot
                )

                return {
                    "status": "pending",
                    "message": "Script submitted: {}".format(script_name),
                    "data": {
                        "task_id": task_id,
                        "task_type": "script",
                        "script_name": script_name,
                        "entry_script": script_path,
                        "script_path": script_path,
                        "description": description,
                        "start_time": submit_time,
                        "exec_commit": exec_commit
                    }
                }

            else:
                # Synchronous execution: wait for completion with optional timeout
                # BUT still register as task for unified output management
                timeout_seconds = timeout_ms / 1000.0 if timeout_ms else None
                logger.info("Executing script synchronously: {} [timeout={}s]".format(
                    script_name, timeout_seconds if timeout_seconds else "None"
                ))

                # Register task BEFORE waiting (enables output caching and post-query)
                task_id = self.task_manager.create_script_task(
                    session_id,
                    future,
                    script_name,
                    script_path,
                    output_buffer,  # Pass buffer reference for output caching
                    description,  # Agent-provided task description
                    exec_commit  # Git version snapshot
                )

                loop = asyncio.get_event_loop()
                # Wait for script execution with timeout
                result_dict = await loop.run_in_executor(
                    None,  # Use default thread pool
                    future.result,  # Block until main thread processes
                    timeout_seconds  # Use specified timeout or None for no timeout
                )

                # Extract cached output from task (single source of truth)
                full_output = output_buffer.getvalue()

                # Get timing info from task for consistent time display
                task = self.task_manager.tasks.get(task_id)
                start_time = task.start_time if task else None
                end_time = task.end_time if task else None
                elapsed_time = (end_time - start_time) if (start_time and end_time) else 0

                # Return unified structure with all metadata in data field
                return {
                    "status": result_dict.get("status", "success"),
                    "message": result_dict.get("message", "Script executed"),
                    "data": {
                        "task_id": task_id,
                        "task_type": "script",
                        "script_name": script_name,
                        "entry_script": script_path,
                        "script_path": script_path,
                        "description": description,
                        "start_time": start_time,
                        "end_time": end_time,
                        "elapsed_time": elapsed_time,
                        "output": full_output,
                        "result": result_dict.get("data"),  # Script's 'result' variable
                        "exec_commit": exec_commit
                    }
                }

        except Exception as e:
            # Special handling for timeout errors (provide LLM-friendly guidance)
            # Python 3.6 compatibility: Check both TimeoutError types
            import concurrent.futures

            # In Python 3.6+, concurrent.futures.TimeoutError is an alias of TimeoutError
            # Check exception type name to handle both cases
            exception_type_name = type(e).__name__
            is_timeout = (
                isinstance(e, concurrent.futures.TimeoutError) or
                exception_type_name == 'TimeoutError'
            )

            if is_timeout:
                # Script execution timed out - retrieve task info if available
                import os
                script_name_for_error = os.path.basename(script_path)

                logger.error("Script execution timed out: {} (timeout: {}ms)".format(script_path, timeout_ms))
                logger.error("Exception type: {} - {}".format(type(e).__name__, str(e)))

                # Try to get task info for timing and output
                task_id_local = locals().get('task_id')
                task = self.task_manager.tasks.get(task_id_local) if task_id_local else None

                error_message = "Timeout after {}ms executing script '{}'. Increase timeout or use run_in_background=True.".format(
                    timeout_ms, script_name_for_error
                )

                return {
                    "status": "error",
                    "message": error_message,
                    "data": {
                        "task_id": task_id_local,
                        "task_type": "script",
                        "script_name": script_name_for_error,
                        "entry_script": script_path,
                        "script_path": script_path,
                        "description": description,
                        "start_time": task.start_time if task else None,
                        "output": output_buffer.getvalue() if 'output_buffer' in locals() else "", # type: ignore
                        "error": error_message,
                        "exec_commit": locals().get('exec_commit')
                    }
                }

            # General error handling (pre-execution errors)
            logger.error("Script submission failed: {}".format(e))
            logger.error("Exception type: {}".format(type(e).__name__))

            error_message = "Script submission failed: {}".format(str(e))

            return {
                "status": "error",
                "message": error_message,
                "data": {
                    "task_type": "script",
                    "script_name": os.path.basename(script_path) if script_path else "unknown",
                    "entry_script": script_path,
                    "script_path": script_path,
                    "description": description,
                    "error": error_message,
                    "exec_commit": locals().get('exec_commit')
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
