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

# Module logger
logger = logging.getLogger("PFC-Server")


class PFCCommandExecutor:
    """
    Execute PFC commands using itasca SDK via main thread queue.

    All commands are executed in IPython main thread via queue mechanism
    to ensure thread safety and support for callback-based commands.
    """

    def __init__(self, main_executor):
        # type: (MainThreadExecutor) -> None
        """
        Initialize executor with itasca module and main thread executor.

        Args:
            main_executor: Main thread executor for queue-based execution
        """
        self.main_executor = main_executor

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

    async def execute_command(self, command, arg=None, params=None):
        # type: (str, Any, Optional[Dict[str, Any]]) -> Dict[str, Any]
        """
        Execute a native PFC command via main thread queue.

        This method assembles a complete PFC command string from the command name,
        optional positional argument, and optional keyword parameters, then submits
        it to the main thread queue for execution.

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

        Returns:
            Result dictionary following ToolResult pattern:
                - status: Literal["success", "error"] - Operation outcome
                - message: str - User-friendly message (success description or error details)
                - data: Optional[Any] - Command result data (success only)

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

            logger.info("Submitting PFC command to main thread: {}".format(cmd_str))

            # Submit to main thread queue
            future = self.main_executor.submit(
                self._execute_pfc_command_sync,
                cmd_str
            )

            # Wait for main thread to execute (async)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,  # Use default thread pool
                future.result,  # Block until main thread processes
                300  # 5 minutes timeout
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
                cmd_parts.append(self._format_value(value))

        return " ".join(cmd_parts)

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
        - Strings: Smart handling for identifiers vs complex formats

        Args:
            value: Value to format (bool, int, float, str, tuple, list, or other)

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
