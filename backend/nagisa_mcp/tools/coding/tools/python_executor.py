"""execute_python_script tool – secure Python script execution with enterprise-grade protection."""

import os
import subprocess
from typing import Dict, List, Any, Optional

from pydantic import Field
from pydantic.fields import FieldInfo
from fastmcp import FastMCP  # type: ignore

from ..utils.path_security import (
    validate_path_in_workspace, 
    is_safe_symlink, 
    check_parent_symlinks
)
from ..utils.tool_result import ToolResult

__all__ = ["execute_python_script", "register_python_executor_tools"]

# -----------------------------------------------------------------------------
# Constants and limits
# -----------------------------------------------------------------------------

_DEFAULT_TIMEOUT = 30  # seconds
_MAX_TIMEOUT = 300  # 5 minutes maximum
_MAX_OUTPUT_SIZE = 10 * 1024 * 1024  # 10 MB maximum combined output
_OUTPUT_TRUNCATE_SIZE = 1024 * 1024  # 1 MB truncation point

# -----------------------------------------------------------------------------
# Helper utilities
# -----------------------------------------------------------------------------

def _truncate_output(output: str, max_size: int = _OUTPUT_TRUNCATE_SIZE) -> tuple[str, bool]:
    """Truncate output if too large, return (content, was_truncated)."""
    if len(output) <= max_size:
        return output, False
    
    truncated = output[:max_size] + "\n\n... [OUTPUT TRUNCATED - exceeded size limit] ..."
    return truncated, True

def _get_python_executable() -> str:
    """Get the appropriate Python executable path."""
    # Priority: PYTHON env var > sys.executable
    return os.getenv("PYTHON", os.sys.executable)

# -----------------------------------------------------------------------------
# Main implementation
# -----------------------------------------------------------------------------

def execute_python_script(
    path: str = Field(
        ...,
        description=(
            "Workspace-relative path to the .py script to execute. The path must reside "
            "inside the coding workspace. If you need to create the file first, use write_file."
        ),
    ),
    args: Optional[List[str]] = Field(
        None,
        description=(
            "Command-line arguments passed directly to the Python interpreter. "
            "Provide one argument per list element, e.g. ['--epochs', '10']."
        ),
    ),
    timeout: int = Field(
        _DEFAULT_TIMEOUT,
        ge=1,
        le=_MAX_TIMEOUT,
        description=(
            "Maximum execution time in seconds. Script is force-terminated if exceeded. "
            f"Range: 1-{_MAX_TIMEOUT} seconds."
        ),
    ),
    working_directory: Optional[str] = Field(
        None,
        description=(
            "Working directory for script execution (workspace-relative). "
            "Defaults to the script's directory if not specified."
        ),
    ),
) -> Dict[str, Any]:
    """Executes a Python script in a secure, isolated environment and returns its output.

    ## Core Functionality
    - **Path:** The workspace-relative path to the `.py` script to execute.
    - **Args:** A list of string arguments to pass to the script (e.g., `['--user', 'admin']`).
    - **Timeout:** Maximum execution time in seconds (default: 30s, max: 300s).

    ## Strategic Usage
    - This is your primary tool for running tests, executing build scripts, or running any Python code.
    - **You must `write_file` first** to create the script before you can execute it.
    - The script runs in an isolated process. It cannot access or modify the state of the agent.
    - **Crucially, you must check the `exit_code` in the response to determine if the script itself succeeded or failed.**

    ## Return Value (What you will receive)
    The output you get back from this tool will be one of the following two things:

    1.  **Success (Tool ran the script):** A `JSON object` containing the execution results.
        - **Object Schema:** `{"exit_code": int, "stdout": string, "stderr": string}`
        - **Example (Script Success):**
          ```json
          {"exit_code": 0, "stdout": "Process finished successfully.", "stderr": ""}
          ```
        - **Example (Script Failure):**
          ```json
          {"exit_code": 1, "stdout": "", "stderr": "Traceback (most recent call last):\n  File \"test.py\", line 5, in <module>\n    raise ValueError(\"A sample error\")\nValueError: A sample error"}
          ```
    2.  **Error (Tool failed to run):** A single `string` starting with "Error:", explaining the tool-level failure.
        - Example: `"Error: Script does not exist: run_tests.py"`

    You MUST parse the JSON response and check the `exit_code` to determine the outcome.
    """

    # ------------------------------------------------------------------
    # Parameter validation (manual to stay lightweight)
    # ------------------------------------------------------------------

    # Handle Pydantic FieldInfo objects when invoked programmatically
    if isinstance(args, FieldInfo):
        args = None
    if isinstance(timeout, FieldInfo):
        timeout = _DEFAULT_TIMEOUT
    if isinstance(working_directory, FieldInfo):
        working_directory = None

    # Normalize args to list
    str_args = []
    if args:
        if not isinstance(args, list):
            return ToolResult(
                status="error", 
                message="'args' must be a list of strings", 
                error="'args' must be a list of strings"
            ).model_dump()
        str_args = [str(a) for a in args]

    # Helper shortcuts for consistent results
    def _error(message: str) -> Dict[str, Any]:
        return ToolResult(status="error", message=message, error=message).model_dump()

    def _success(message: str, llm_content: str, **data: Any) -> Dict[str, Any]:
        payload = data or None
        return ToolResult(
            status="success",
            message=message,
            llm_content=llm_content,
            data=payload,
        ).model_dump()

    # ------------------------------------------------------------------
    # Security validation and path resolution
    # ------------------------------------------------------------------

    # Validate script path
    abs_script_path = validate_path_in_workspace(path)
    if abs_script_path is None:
        return _error(f"Script path is outside of workspace: {path}")

    try:
        script_path = os.path.abspath(abs_script_path)
        
        # Check if script exists
        if not os.path.exists(script_path):
            return _error(f"Script does not exist: {path}")
        
        # Check if it's actually a file
        if not os.path.isfile(script_path):
            return _error(f"Path is not a file: {path}")
        
        # Check if it's a Python file
        if not script_path.endswith(('.py', '.pyw')):
            return _error(f"File is not a Python script (.py/.pyw): {path}")
        
        # Comprehensive symlink safety checks
        if os.path.islink(script_path) and not is_safe_symlink(script_path):
            return _error("Cannot execute symlink pointing outside workspace")
        
        # Check parent directory safety
        if not check_parent_symlinks(script_path):
            return _error("Cannot execute script with parent symlink pointing outside workspace")

        # Validate working directory if specified
        if working_directory:
            abs_workdir = validate_path_in_workspace(working_directory)
            if abs_workdir is None:
                return _error(f"Working directory is outside of workspace: {working_directory}")
            
            workdir_path = os.path.abspath(abs_workdir)
            if not os.path.exists(workdir_path):
                return _error(f"Working directory does not exist: {working_directory}")
            if not os.path.isdir(workdir_path):
                return _error(f"Working directory is not a directory: {working_directory}")
            
            # Check working directory symlink safety
            if os.path.islink(workdir_path) and not is_safe_symlink(workdir_path):
                return _error("Cannot use working directory with symlink pointing outside workspace")
            if not check_parent_symlinks(workdir_path):
                return _error("Cannot use working directory with parent symlink pointing outside workspace")
        else:
            # Default to script's directory
            workdir_path = os.path.dirname(script_path)

        # ------------------------------------------------------------------
        # Script execution
        # ------------------------------------------------------------------

        python_executable = _get_python_executable()
        cmd = [python_executable, script_path] + str_args
        
        import time
        start_time = time.time()

        try:
            result = subprocess.run(
                cmd,
                cwd=workdir_path,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            
            execution_time = time.time() - start_time
            
            # Check output size and truncate if necessary
            stdout_content, stdout_truncated = _truncate_output(result.stdout)
            stderr_content, stderr_truncated = _truncate_output(result.stderr)
            
            combined_size = len(result.stdout) + len(result.stderr)
            
            if combined_size > _MAX_OUTPUT_SIZE:
                return _error(f"Script output too large ({combined_size / 1024 / 1024:.1f}MB exceeds {_MAX_OUTPUT_SIZE / 1024 / 1024}MB limit)")

            # The tool's job is to run the script and report the results.
            # A non-zero exit code is a script failure, not a tool failure.
            # We will always return a success response containing the script's results.
            
            # Build the structured JSON payload for the LLM, as promised in the docstring.
            llm_content = {
                "exit_code": result.returncode,
                "stdout": stdout_content,
                "stderr": stderr_content,
            }

            # Create a human-readable summary message for the UI.
            status_msg = f"Script finished with exit code {result.returncode} in {execution_time:.2f}s."

            # Prepare the detailed data payload for the UI, which is not sent to the LLM.
            execution_data = {
                "script_path": script_path,
                "working_directory": workdir_path,
                "exit_code": result.returncode,
                "execution_time": round(execution_time, 3),
                "output": {
                    "stdout": stdout_content,
                    "stderr": stderr_content,
                    "combined_size": combined_size,
                    "stdout_truncated": stdout_truncated,
                    "stderr_truncated": stderr_truncated
                },
                "command": cmd,
                "limits_applied": {
                    "timeout": timeout,
                    "max_output_size": _MAX_OUTPUT_SIZE
                }
            }

            # Return a success response with the structured LLM content.
            return _success(status_msg, llm_content, **execution_data)

        except subprocess.TimeoutExpired as exc:
            execution_time = time.time() - start_time
            
            # Handle timeout with partial output
            partial_stdout, _ = _truncate_output(exc.stdout or "")
            partial_stderr, _ = _truncate_output(exc.stderr or "")
            
            # Build the structured JSON payload for the LLM.
            # A timeout is a script execution result, not a tool failure.
            llm_content = {
                "exit_code": -1,  # Convention for timeout
                "stdout": partial_stdout,
                "stderr": f"{partial_stderr}\n\n[ERROR] Script execution timed out after {timeout} seconds and was terminated.".strip()
            }

            # Create a human-readable summary message for the UI.
            status_msg = f"Script timed out after {timeout}s and was terminated."

            # Prepare the detailed data payload for the UI.
            timeout_data = {
                "script_path": script_path,
                "working_directory": workdir_path,
                "exit_code": -1,
                "execution_time": round(execution_time, 3),
                "output": {
                    "stdout": partial_stdout,
                    "stderr": llm_content["stderr"],
                    "combined_size": len(partial_stdout) + len(partial_stderr),
                    "stdout_truncated": len(exc.stdout or "") > _OUTPUT_TRUNCATE_SIZE,
                    "stderr_truncated": len(exc.stderr or "") > _OUTPUT_TRUNCATE_SIZE,
                },
                "command": cmd,
                "timeout_info": {
                    "timeout_seconds": timeout,
                    "was_killed": True
                }
            }

            # Return a success response with the structured LLM content.
            return _success(status_msg, llm_content, **timeout_data)

    except PermissionError:
        return _error("Permission denied when executing script")
    except Exception as exc:  # pylint: disable=broad-except
        return _error(f"Unexpected error during script execution: {exc}")

# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_python_executor_tools(mcp: FastMCP):
    """Register the execute_python_script tool with proper tags synchronization."""
    common = dict(
        tags={"coding", "execution", "python", "script", "runtime"}, 
        annotations={"category": "coding", "tags": ["coding", "execution", "python", "script", "runtime"]}
    )
    mcp.tool(**common)(execute_python_script) 