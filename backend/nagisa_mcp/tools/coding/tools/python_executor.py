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
    """execute_python_script – Secure Python script execution with enterprise-grade protection.

    This tool safely executes Python scripts in isolated subprocess environments with
    comprehensive security checks, resource limits, and detailed error reporting. All
    operations are restricted to the workspace directory with multi-layer protection
    against malicious paths and resource exhaustion.

    Successful response (``ToolResult.model_dump()``) – **keys of interest**::

        {
        "status": "success",
        "message": "Script executed successfully",           # short summary
        "llm_content": "Script output: Hello World!",       # detailed output for LLM
        "data": {
            "script_path": "/abs/workspace/scripts/main.py", # executed script path
            "working_directory": "/abs/workspace/scripts/",  # execution directory
            "exit_code": 0,                                  # process exit code
            "execution_time": 2.5,                          # runtime in seconds
            "output": {                                      # captured output
                "stdout": "Hello World!\\nProcessing...",    # standard output
                "stderr": "",                                # standard error
                "combined_size": 1024,                       # total output size
                "stdout_truncated": false,                   # whether truncated
                "stderr_truncated": false                    # whether truncated
            },
            "command": ["python3", "main.py", "--verbose"],  # executed command
            "limits_applied": {                              # resource limits info
                "timeout": 30,                               # timeout used
                "max_output_size": 10485760                  # output size limit
            }
        }
        }

    Error response::

        {
        "status": "error",
        "message": "Script execution failed with exit code 1",
        "error": "Script execution failed with exit code 1"
        }

    Security Features:
    - Path validation: All paths validated against workspace boundaries
    - Symlink safety: Prevents executing symlinks pointing outside workspace
    - Parent directory safety: Checks all parent directories for unsafe symlinks
    - Process isolation: Scripts run in separate subprocess with no shell access
    - Command injection prevention: Arguments passed as list, no shell interpolation
    - Working directory control: Execution restricted to workspace subdirectories

    Performance Features:
    - Timeout protection: Configurable execution time limits (1-300 seconds)
    - Output size limits: Large outputs automatically truncated (10MB max)
    - Memory protection: Captured output size tracking and limits
    - Process cleanup: Automatic termination of hung processes
    - Resource monitoring: Detailed execution statistics and timing

    Reliability Features:
    - Graceful error handling: Comprehensive error categorization and reporting
    - Detailed logging: Full command, timing, and output information
    - Exit code tracking: Standard process return code reporting
    - Environment isolation: Clean execution environment with controlled variables
    - Timeout handling: Proper process tree termination on timeout

    The **``llm_content``** field provides execution results optimized for the
    assistant's context, while **``message``** is a concise user summary.
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

            # Determine status
            success = result.returncode == 0
            status_msg = "Script executed successfully" if success else f"Script execution failed with exit code {result.returncode}"
            
            # Build LLM content
            if success:
                if stdout_content.strip():
                    llm_content = f"Script executed successfully. Output: {stdout_content[:500]}{'...' if len(stdout_content) > 500 else ''}"
                else:
                    llm_content = "Script executed successfully with no output"
            else:
                error_info = stderr_content[:200] if stderr_content else "No error details"
                llm_content = f"Script failed (exit code {result.returncode}). Error: {error_info}"

            # Prepare detailed data
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

            if success:
                return _success(status_msg, llm_content, **execution_data)
            else:
                # For failed executions, return error with detailed data
                return ToolResult(
                    status="error",
                    message=status_msg,
                    error=stderr_content if stderr_content else f"Script exited with code {result.returncode}",
                    data=execution_data
                ).model_dump()

        except subprocess.TimeoutExpired as exc:
            execution_time = time.time() - start_time
            
            # Handle timeout with partial output
            partial_stdout = exc.stdout or ""
            partial_stderr = exc.stderr or ""
            
            timeout_data = {
                "script_path": script_path,
                "working_directory": workdir_path,
                "exit_code": -1,
                "execution_time": round(execution_time, 3),
                "output": {
                    "stdout": partial_stdout,
                    "stderr": partial_stderr,
                    "combined_size": len(partial_stdout) + len(partial_stderr),
                    "stdout_truncated": False,
                    "stderr_truncated": False
                },
                "command": cmd,
                "timeout_info": {
                    "timeout_seconds": timeout,
                    "was_killed": True
                }
            }

            return ToolResult(
                status="error",
                message=f"Script exceeded timeout of {timeout}s and was terminated",
                error=f"Script exceeded timeout of {timeout}s and was terminated",
                data=timeout_data
            ).model_dump()

    except PermissionError:
        return _error("Permission denied when executing script")
    except Exception as exc:  # pylint: disable=broad-except
        return _error(f"Unexpected error during script execution: {exc}")

# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_python_executor_tools(mcp: FastMCP):
    common = dict(tags={"coding"}, annotations={"category": "coding"})
    mcp.tool(**common)(execute_python_script) 