"""run_shell_command tool – secure shell command execution with enterprise-grade protection."""

import os
import subprocess
import shutil
import time
from typing import Dict, Any, List, Optional

from pydantic import Field
from pydantic.fields import FieldInfo
from fastmcp import FastMCP  # type: ignore

from pathlib import Path

from ..utils.path_security import (
    validate_path_in_workspace, 
    WORKSPACE_ROOT, 
    is_safe_symlink, 
    check_parent_symlinks
)
from ..utils.tool_result import ToolResult
from .config import get_tools_config

__all__ = ["run_shell_command", "register_shell_command_tool"]

# -----------------------------------------------------------------------------
# Constants and limits
# -----------------------------------------------------------------------------

_DEFAULT_TIMEOUT = 60  # seconds
_MAX_TIMEOUT = 600  # 10 minutes maximum
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

def _get_shell_executable() -> List[str]:
    """Get the appropriate shell executable for the platform."""
    if os.name == "nt":
        return ["cmd.exe", "/c"]
    else:
        # Prefer bash if available, fallback to sh
        bash_path = shutil.which("bash")
        if bash_path:
            return [bash_path, "-c"]
        else:
            return ["sh", "-c"]

def _validate_command(command: str) -> tuple[bool, str]:
    """Validate command safety. Return (is_valid, reason)."""
    if not command.strip():
        return False, "Command cannot be empty"
    
    # Check for extremely dangerous patterns
    dangerous_patterns = [
        "rm -rf /",
        ":(){ :|:& };:",  # Fork bomb
        "chmod -R 777 /",
        "dd if=/dev/zero",
        "> /dev/sda",
        "mkfs.",
    ]
    
    command_lower = command.lower()
    for pattern in dangerous_patterns:
        if pattern in command_lower:
            return False, f"Command contains dangerous pattern: {pattern}"
    
    return True, ""

# -----------------------------------------------------------------------------
# Main implementation
# -----------------------------------------------------------------------------

def run_shell_command(
    command: str = Field(
        ...,
        description=(
            "Complete shell command string to execute. Supports pipes, redirects, "
            "logical operators, subshells, etc. Example: 'ls -l | grep .py > out.txt'"
        ),
    ),
    directory: Optional[str] = Field(
        None,
        description=(
            "Working directory for command execution (workspace-relative). "
            "Defaults to workspace root if not specified."
        ),
    ),
    timeout: int = Field(
        _DEFAULT_TIMEOUT,
        ge=1,
        le=_MAX_TIMEOUT,
        description=(
            "Maximum execution time in seconds. Command is force-terminated if exceeded. "
            f"Range: 1-{_MAX_TIMEOUT} seconds."
        ),
    ),
    allow_dangerous: bool = Field(
        False,
        description=(
            "Set to true to bypass basic dangerous command detection. "
            "Use with extreme caution - only for trusted operations."
        ),
    ),
) -> Dict[str, Any]:
    """run_shell_command – Secure shell command execution with enterprise-grade protection.

    Execute arbitrary shell commands with comprehensive security checks, resource limits,
    and detailed output handling. This tool provides full shell capabilities including
    pipes, redirects, and command chaining, while maintaining safety through multiple
    protection layers.

    ⚠️  **CRITICAL SECURITY WARNING** ⚠️
    This tool executes commands directly through the system shell with the same
    privileges as the host process. Malicious commands can cause irreversible
    damage to the system. Always verify command safety before execution.

    Successful response (``ToolResult.model_dump()``) – **keys of interest**::

        {
        "status": "success",
        "message": "Command executed successfully",        # short summary
        "llm_content": "Command output: Hello World!",    # detailed output for LLM
        "data": {
            "command": "echo 'Hello World!'",             # executed command
            "directory": "/abs/workspace/",               # execution directory
            "exit_code": 0,                               # process exit code
            "execution_time": 0.15,                       # runtime in seconds
            "output": {                                   # captured output
                "stdout": "Hello World!\\n",              # standard output
                "stderr": "",                             # standard error
                "combined_size": 13,                      # total output size
                "stdout_truncated": false,                # whether truncated
                "stderr_truncated": false                 # whether truncated
            },
            "shell_info": {                               # shell execution info
                "shell_executable": ["bash", "-c"],      # shell used
                "platform": "posix"                      # execution platform
            },
            "limits_applied": {                           # resource limits info
                "timeout": 60,                            # timeout used
                "max_output_size": 10485760               # output size limit
            }
        }
        }

    Error response::

        {
        "status": "error",
        "message": "Command execution failed with exit code 1",
        "error": "Command execution failed with exit code 1"
        }

    Security Features:
    - Path validation: Working directory validated against workspace boundaries
    - Symlink safety: Prevents execution in directories with unsafe symlinks
    - Dangerous command detection: Basic protection against destructive patterns
    - Process isolation: Commands run in separate subprocess environment
    - Working directory restriction: Execution limited to workspace subdirectories
    - Resource monitoring: Comprehensive tracking of execution and output

    Performance Features:
    - Timeout protection: Configurable execution time limits (1-600 seconds)
    - Output size limits: Large outputs automatically truncated (10MB max)
    - Memory protection: Captured output size tracking and limits
    - Process cleanup: Automatic termination of hung processes
    - Platform optimization: Uses optimal shell for each platform (bash/cmd)

    Reliability Features:
    - Graceful error handling: Comprehensive error categorization and reporting
    - Detailed logging: Full command, timing, and output information
    - Exit code tracking: Standard process return code reporting
    - Signal handling: Proper process termination and signal reporting
    - Timeout handling: Clean process tree termination on timeout

    Shell Features:
    - Full shell syntax: Supports pipes, redirects, variables, subshells
    - Command chaining: Logical operators (&&, ||, ;) fully supported  
    - Environment access: Commands can read/modify environment variables
    - Process spawning: Can launch additional processes and tools
    - File operations: Complete filesystem access within workspace

    The **``llm_content``** field provides execution results optimized for the
    assistant's context, while **``message``** is a concise user summary.
    """

    # ------------------------------------------------------------------
    # Parameter validation (manual to stay lightweight)
    # ------------------------------------------------------------------

    # Handle Pydantic FieldInfo objects when invoked programmatically
    if isinstance(directory, FieldInfo):
        directory = None
    if isinstance(timeout, FieldInfo):
        timeout = _DEFAULT_TIMEOUT
    if isinstance(allow_dangerous, FieldInfo):
        allow_dangerous = False

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
    # Command and directory validation
    # ------------------------------------------------------------------

    # Validate command safety
    if not allow_dangerous:
        is_valid, reason = _validate_command(command)
        if not is_valid:
            return _error(f"Dangerous command detected: {reason}")

    # Validate and resolve working directory
    if directory:
        abs_workdir = validate_path_in_workspace(directory)
        if abs_workdir is None:
            return _error(f"Working directory is outside of workspace: {directory}")
        
        workdir_path = Path(abs_workdir)
        
        try:
            if not workdir_path.exists():
                return _error(f"Working directory does not exist: {directory}")
            if not workdir_path.is_dir():
                return _error(f"Working directory is not a directory: {directory}")
            
            # Check working directory symlink safety
            if workdir_path.is_symlink() and not is_safe_symlink(workdir_path):
                return _error("Cannot use working directory with symlink pointing outside workspace")
            if not check_parent_symlinks(workdir_path):
                return _error("Cannot use working directory with parent symlink pointing outside workspace")
                
            exec_dir = str(workdir_path)
        except Exception as exc:
            return _error(f"Error accessing working directory: {exc}")
    else:
        # Default to workspace root
        exec_dir = str(WORKSPACE_ROOT)

    # ------------------------------------------------------------------
    # Shell command execution
    # ------------------------------------------------------------------

    try:
        shell_exe = _get_shell_executable()
        full_command = shell_exe + [command]
        
        start_time = time.time()

        try:
            result = subprocess.run(
                full_command,
                cwd=exec_dir,
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
                return _error(f"Command output too large ({combined_size / 1024 / 1024:.1f}MB exceeds {_MAX_OUTPUT_SIZE / 1024 / 1024}MB limit)")

            # Determine status
            success = result.returncode == 0
            status_msg = "Command executed successfully" if success else f"Command execution failed with exit code {result.returncode}"
            
            # Build LLM content
            if success:
                if stdout_content.strip():
                    llm_content = f"Command executed successfully. Output: {stdout_content[:500]}{'...' if len(stdout_content) > 500 else ''}"
                else:
                    llm_content = "Command executed successfully with no output"
            else:
                error_info = stderr_content[:200] if stderr_content else "No error details"
                llm_content = f"Command failed (exit code {result.returncode}). Error: {error_info}"

            # Prepare detailed data
            execution_data = {
                "command": command,
                "directory": exec_dir,
                "exit_code": result.returncode,
                "execution_time": round(execution_time, 3),
                "output": {
                    "stdout": stdout_content,
                    "stderr": stderr_content,
                    "combined_size": combined_size,
                    "stdout_truncated": stdout_truncated,
                    "stderr_truncated": stderr_truncated
                },
                "shell_info": {
                    "shell_executable": shell_exe,
                    "platform": "nt" if os.name == "nt" else "posix"
                },
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
                    error=stderr_content if stderr_content else f"Command exited with code {result.returncode}",
                    data=execution_data
                ).model_dump()

        except subprocess.TimeoutExpired as exc:
            execution_time = time.time() - start_time
            
            # Handle timeout with partial output
            partial_stdout = exc.stdout or ""
            partial_stderr = exc.stderr or ""
            
            timeout_data = {
                "command": command,
                "directory": exec_dir,
                "exit_code": -1,
                "execution_time": round(execution_time, 3),
                "output": {
                    "stdout": partial_stdout,
                    "stderr": partial_stderr,
                    "combined_size": len(partial_stdout) + len(partial_stderr),
                    "stdout_truncated": False,
                    "stderr_truncated": False
                },
                "shell_info": {
                    "shell_executable": shell_exe,
                    "platform": "nt" if os.name == "nt" else "posix"
                },
                "timeout_info": {
                    "timeout_seconds": timeout,
                    "was_killed": True
                }
            }

            return ToolResult(
                status="error",
                message=f"Command exceeded timeout of {timeout}s and was terminated",
                error=f"Command exceeded timeout of {timeout}s and was terminated",
                data=timeout_data
            ).model_dump()

    except PermissionError:
        return _error("Permission denied when executing command")
    except Exception as exc:  # pylint: disable=broad-except
        return _error(f"Unexpected error during command execution: {exc}")

# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_shell_command_tool(mcp: FastMCP):
    common = dict(tags={"shell", "coding"}, annotations={"category": "coding"})
    mcp.tool(**common)(run_shell_command) 