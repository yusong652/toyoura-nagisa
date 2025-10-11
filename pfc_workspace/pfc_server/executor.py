"""
PFC Command Executor - Executes ITASCA PFC commands via SDK.

This module provides command execution functionality for the PFC WebSocket server
using main thread queue execution strategy.

Python 3.6 compatible implementation.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from .main_thread_executor import MainThreadExecutor
from .task_manager import TaskManager

# Module logger
logger = logging.getLogger("PFC-Server")

# Default timeout for command execution (milliseconds)
DEFAULT_COMMAND_TIMEOUT_MS = 30000  # 30 seconds for testing
MAX_COMMAND_TIMEOUT_MS = 600000     # 10 minutes maximum


class PFCCommandExecutor:
    """
    Execute PFC commands using itasca SDK via main thread queue.

    All commands are executed in IPython main thread via queue mechanism
    to ensure thread safety and support for callback-based commands.
    """

    def __init__(self, main_executor, task_manager):
        # type: (MainThreadExecutor, TaskManager) -> None
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
            logger.info("✓ ITASCA SDK loaded for command execution")
        except ImportError:
            logger.warning("⚠ ITASCA SDK not available")
            self.itasca = None


    def _execute_pfc_command_sync(self, cmd_str):
        # type: (str) -> Any
        """
        Synchronous wrapper for itasca.command() (executed in main thread).

        This method is submitted to main thread queue and executed there.

        Args:
            cmd_str: Complete PFC command string

        Returns:
            Command result

        Raises:
            Exception: Any error during command execution
        """
        try:
            # Execute command via ITASCA SDK in main thread
            return self.itasca.command(cmd_str) # type: ignore

        except Exception as e:
            # Log the full exception for debugging
            logger.error("PFC command failed: {}".format(cmd_str))
            logger.error("Exception type: {}".format(type(e).__name__))
            logger.error("Exception message: {}".format(str(e)))
            # Re-raise to be handled by async wrapper
            raise

    async def execute_command(self, command, arg=None, params=None, timeout_ms=DEFAULT_COMMAND_TIMEOUT_MS, run_in_background=False):
        # type: (str, Any, Optional[Dict[str, Any]], int, bool) -> Dict[str, Any]
        """
        Execute a native PFC command via main thread queue with flexible execution control.

        This method assembles a complete PFC command string from the command name,
        optional positional argument, and optional keyword parameters, then submits
        it to the main thread queue for execution.

        Execution modes:
        - Synchronous (run_in_background=False): Wait for completion, return result/error immediately
        - Asynchronous (run_in_background=True): Return task_id immediately, query via check_task_status()

        Args:
            command: PFC command name (e.g., "model gravity", "contact cmat default", "ball create")
            arg: Optional single positional argument (value without keyword) using native Python types
                Supported types: bool, int, float, str, tuple
                Examples:
                  • True (bool) → "model large-strain true"
                  • 9.81 (float) → "model gravity 9.81"
                  • (0, 0, -9.81) (tuple) → "model gravity (0,0,-9.81)"
            params: Optional dictionary with keyword parameters (values can be None for boolean flags)
                Supported value types: bool, int, float, str, tuple, list
                Examples:
                  • {"radius": 1.0, "position": [0, 0, 0], "group": "my_balls"}
                  • {"condition": "stop"} → "model domain condition stop"
                  • {"model": "linear", "inheritance": None} → boolean flag
                  • {"active": True} → keyword with boolean value
            timeout_ms: Command execution timeout in milliseconds (default: 30000ms / 30 seconds)
                - Valid range: 1000-600000 (1 second to 10 minutes)
                - Only applies to synchronous execution (run_in_background=False)
            run_in_background: Background execution control (default: False - synchronous for testing)
                - False: Synchronous - wait for completion, catch errors immediately
                - True: Asynchronous - return task_id, query progress later

        Returns:
            Result dictionary following ToolResult pattern:
                For synchronous execution (run_in_background=False):
                    - status: "success" or "error"
                    - message: User-friendly message
                    - data: Command result data
                For asynchronous execution (run_in_background=True):
                    - status: "pending"
                    - message: Task submission confirmation
                    - data: {"task_id": str, "command": str}

        Note:
            All commands execute in IPython main thread via queue mechanism.
            This ensures thread safety and supports callback-based commands.
        """
        cmd_str = None

        try:
            if not self.itasca:
                return {
                    "status": "error",
                    "message": "ITASCA SDK not available: Server not running in PFC GUI environment",
                    "data": None
                }

            # Assemble complete PFC command string
            params = params or {}  # Handle None params
            cmd_str = self._assemble_command(command, arg, params)

            # Validate timeout range
            if timeout_ms < 1000:
                return {
                    "status": "error",
                    "message": "Timeout must be at least 1000ms (1 second)",
                    "data": None
                }
            elif timeout_ms > MAX_COMMAND_TIMEOUT_MS:
                return {
                    "status": "error",
                    "message": "Timeout cannot exceed {}ms ({} minutes)".format(
                        MAX_COMMAND_TIMEOUT_MS, MAX_COMMAND_TIMEOUT_MS // 60000
                    ),
                    "data": None
                }

            timeout_seconds = timeout_ms / 1000.0

            logger.info("Submitting PFC command to main thread: {} [{}]".format(
                cmd_str, "ASYNC" if run_in_background else "SYNC, timeout={}s".format(timeout_seconds)
            ))

            # Submit to main thread queue
            future = self.main_executor.submit(
                self._execute_pfc_command_sync,
                cmd_str
            )

            if run_in_background:
                # Asynchronous execution: register with task manager and return immediately
                task_id = self.task_manager.create_command_task(future, cmd_str)

                return {
                    "status": "pending",
                    "message": "Command submitted as background task: {}\nUse check_task_status tool to query progress.".format(cmd_str),
                    "data": {
                        "task_id": task_id,
                        "command": cmd_str
                    }
                }

            else:
                # Synchronous execution: wait for completion with timeout
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,  # Use default thread pool
                    future.result,  # Block until main thread processes
                    timeout_seconds  # Use specified timeout
                )

                # Serialize result for response
                serialized_result = self._serialize_result(result)

                # Build message based on whether there's a return value
                if serialized_result is not None:
                    message = "PFC command executed: {}\nResult: {}".format(
                        cmd_str, serialized_result
                    )
                else:
                    message = "PFC command executed: {}".format(cmd_str)

                logger.info("✓ PFC command successful: {}".format(cmd_str))

                return {
                    "status": "success",
                    "message": message,
                    "data": serialized_result
                }

        except asyncio.CancelledError:
            # Handle task cancellation separately
            logger.warning("PFC command cancelled: {}".format(cmd_str))
            raise

        except Exception as e:
            # Log comprehensive error information
            error_msg = str(e)
            logger.error("Command execution failed: {}".format(error_msg))

            if cmd_str:
                logger.error("  Failed command: {}".format(cmd_str))

            # Return error result (don't raise - keep server alive!)
            return {
                "status": "error",
                "message": "Command execution failed: {}".format(error_msg),
                "data": None
            }

    def _assemble_command(self, command: str, arg: Any, params: Dict[str, Any]) -> str:
        """
        Assemble complete PFC command string using type-driven formatting.

        Args:
            command: PFC command name (e.g., "model gravity", "contact cmat default", "ball create")
            arg: Optional positional argument (supports int, float, str, tuple, list)
            params: Keyword-value pairs for command parameters (None values are boolean flags)

        Returns:
            Complete PFC command string

        Examples:
            >>> _assemble_command("model gravity", 9.81, {})
            "model gravity 9.81"

            >>> _assemble_command("model gravity", (0, 0, -9.81), {})
            "model gravity (0,0,-9.81)"

            >>> _assemble_command("ball create", None, {"radius": 1.0, "position": [0, 0, 0]})
            "ball create radius 1.0 position (0,0,0)"

            >>> _assemble_command("contact cmat default", None, {"model": "linear", "inheritance": None})
            "contact cmat default model linear inheritance"

            >>> _assemble_command("model domain", None, {"condition": "stop"})
            "model domain condition stop"  # Auto-converted from key-value to flags

            >>> _assemble_command("contact cmat default", None, {"model": "linear", "property": {"kn": 1.0e6, "dp_nratio": 0.5}})
            "contact cmat default model linear property kn 1.0e6 dp_nratio 0.5"
        """
        # Pre-process params for PFC-specific special cases
        params = self._preprocess_params(params)

        # Start with base command
        cmd_parts = [command]

        # Add positional argument using type-driven formatting
        if arg is not None:
            cmd_parts.append(self._format_value(arg))

        # Add keyword-value pairs using type-driven formatting
        for keyword, value in params.items():
            cmd_parts.append(keyword)
            if value is not None:  # None = boolean flag (keyword only, no value)
                # Special handling for nested dictionaries
                if isinstance(value, dict):
                    self._append_dict_params(cmd_parts, value)
                else:
                    cmd_parts.append(self._format_value(value))

        return " ".join(cmd_parts)

    def _append_dict_params(self, cmd_parts, params_dict):
        # type: (list, Dict[str, Any]) -> None
        """
        Recursively append dictionary parameters to command parts list.

        Args:
            cmd_parts: List to append command parts to (modified in-place)
            params_dict: Dictionary of parameters to expand

        Example:
            >>> cmd_parts = ["contact", "cmat", "default", "property"]
            >>> _append_dict_params(cmd_parts, {"kn": 1.0e6, "dp_nratio": 0.5})
            >>> # cmd_parts becomes: ["contact", "cmat", "default", "property", "kn", "1000000.0", "dp_nratio", "0.5"]
        """
        for key, value in params_dict.items():
            cmd_parts.append(key)
            if value is not None:
                if isinstance(value, dict):
                    # Recursive handling for deeply nested dicts
                    self._append_dict_params(cmd_parts, value)
                else:
                    cmd_parts.append(self._format_value(value))

    def _preprocess_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pre-process parameters to handle PFC-specific special cases.

        PFC 'condition' parameter special handling:
        - PFC syntax: "model domain condition stop" (both are keywords/flags)
        - LLM intuition: {"condition": "stop"} (key-value pair)
        - Auto-conversion: {"condition": "stop"} → {"condition": None, "stop": None}

        Args:
            params: Original parameters dict

        Returns:
            Processed parameters dict

        Examples:
            >>> _preprocess_params({"condition": "stop"})
            {"condition": None, "stop": None}

            >>> _preprocess_params({"condition": "periodic"})
            {"condition": None, "periodic": None}

            >>> _preprocess_params({"radius": 1.0})
            {"radius": 1.0}  # No change for normal params
        """
        if not params or "condition" not in params:
            return params

        condition_value = params["condition"]

        # Known condition sub-keywords that should be independent flags
        # Based on PFC documentation: model domain condition <keyword>
        condition_flags = {"destroy", "periodic", "reflect", "stop"}

        if isinstance(condition_value, str) and condition_value in condition_flags:
            # LLM sent: {"condition": "stop"}
            # Convert to: {"condition": None, "stop": None}
            params = params.copy()  # Don't modify original
            params["condition"] = None  # condition becomes flag
            params[condition_value] = None  # Add sub-keyword as flag

        return params

    def _format_value(self, value: Any) -> str:
        """
        Format value based on Python type for PFC command assembly.

        Type-driven formatting logic:
        - Booleans (bool): Convert to PFC format (lowercase true/false)
        - Numbers (int/float): Direct string conversion
        - Tuples/Lists: Format as PFC tuple "(x,y,z)"
        - Dictionaries (dict): Expand to keyword-value pairs recursively
        - Strings: Smart handling for identifiers vs complex formats

        Args:
            value: Value to format (bool, int, float, str, tuple, list, dict, or other)

        Returns:
            Formatted string for PFC command

        Examples:
            >>> _format_value(True)
            "true"

            >>> _format_value(False)
            "false"

            >>> _format_value(9.81)
            "9.81"

            >>> _format_value((0, 0, -9.81))
            "(0,0,-9.81)"

            >>> _format_value([0, 0, 0])
            "(0,0,0)"

            >>> _format_value({"kn": 1.0e6, "dp_nratio": 0.5})
            "kn 1000000.0 dp_nratio 0.5"

            >>> _format_value("linear")
            '"linear"'

            >>> _format_value("-10 10 -10 10")
            "-10 10 -10 10"
        """
        # Booleans: convert to PFC format (lowercase true/false)
        # MUST check before int because bool is a subclass of int in Python
        if isinstance(value, bool):
            return str(value).lower()

        # Numbers: direct conversion
        elif isinstance(value, (int, float)):
            return str(value)

        # Tuples/Lists: format as PFC tuple
        elif isinstance(value, (tuple, list)):
            return f"({','.join(map(str, value))})"

        # Dictionaries: expand to keyword-value pairs (e.g., property parameters)
        elif isinstance(value, dict):
            parts = []
            for k, v in value.items():
                parts.append(k)
                if v is not None:  # None = boolean flag (keyword only, no value)
                    parts.append(self._format_value(v))  # Recursive formatting
            return " ".join(parts)

        # Strings: smart handling
        elif isinstance(value, str):
            # Complex formats (tuples, sequences, ranges) → use as-is
            if '(' in value or ' ' in value:
                return value
            # Simple identifiers → add quotes
            else:
                return f'"{value}"'

        # Fallback: string representation
        else:
            return str(value)

    def _serialize_result(self, result: Any) -> Any:
        """Convert PFC objects to JSON-serializable format."""
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
