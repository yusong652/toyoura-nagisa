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
from backend.nagisa_mcp.utils.tool_result import ToolResult
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
    """Executes a shell command in a secure, isolated environment and returns its output.

    ## ⚠️ CRITICAL SECURITY WARNING ⚠️
    This tool executes commands directly on the system shell. Malicious commands can cause irreversible damage. Always verify the safety and correctness of a command before execution.

    ## Core Functionality
    - **Command:** The full shell command string to execute. Supports pipes, redirects, and other shell features.
    - **Directory:** The workspace-relative directory where the command will be run. Defaults to the workspace root.
    - **Timeout:** Maximum execution time in seconds (default: 60s, max: 600s).

    ## Strategic Usage
    - This is your most powerful tool for interacting with the system, building projects, running tests, and managing files.
    - **You must check the `exit_code` in the response to determine if the command itself succeeded or failed.** A non-zero exit code indicates a command failure.

    ## Return Value (What you will receive)
    The output you get back from this tool will be one of the following two things:

    1.  **Success (Tool ran the command):** A `JSON object` containing the execution results.
        - **Object Schema:** `{"exit_code": int, "stdout": string, "stderr": string}`
        - **Example (Command Success):**
          ```json
          {"exit_code": 0, "stdout": "build/app.js\nbuild/vendor.js\n", "stderr": ""}
          ```
        - **Example (Command Failure):**
          ```json
          {"exit_code": 127, "stdout": "", "stderr": "bash: npm: command not found"}
          ```
    2.  **Error (Tool failed to run):** A single `string` starting with "Error:", explaining the tool-level failure.
        - Example: `"Error: Working directory is outside of workspace: /etc"`

    You MUST parse the JSON response and check the `exit_code` to determine the outcome.
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

            # The tool's job is to run the command and report the results.
            # A non-zero exit code is a command failure, not a tool failure.
            # We will always return a success response containing the command's results.

            # Build the structured JSON payload for the LLM, as promised in the docstring.
            llm_content = {
                "exit_code": result.returncode,
                "stdout": stdout_content,
                "stderr": stderr_content,
            }

            # Create a human-readable summary message for the UI.
            status_msg = f"Command finished with exit code {result.returncode} in {execution_time:.2f}s."

            # Prepare the detailed data payload for the UI, which is not sent to the LLM.
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

            # Return a success response with the structured LLM content.
            return _success(status_msg, llm_content, **execution_data)

        except subprocess.TimeoutExpired as exc:
            execution_time = time.time() - start_time
            
            # Handle timeout with partial output
            partial_stdout, _ = _truncate_output(exc.stdout or "")
            partial_stderr, _ = _truncate_output(exc.stderr or "")

            # Build the structured JSON payload for the LLM.
            # A timeout is a command execution result, not a tool failure.
            llm_content = {
                "exit_code": -1,  # Convention for timeout
                "stdout": partial_stdout,
                "stderr": f"{partial_stderr}\n\n[ERROR] Command execution timed out after {timeout} seconds and was terminated.".strip()
            }

            # Create a human-readable summary message for the UI.
            status_msg = f"Command timed out after {timeout}s and was terminated."

            # Prepare the detailed data payload for the UI.
            timeout_data = {
                "command": command,
                "directory": exec_dir,
                "exit_code": -1,
                "execution_time": round(execution_time, 3),
                "output": {
                    "stdout": partial_stdout,
                    "stderr": llm_content["stderr"],
                    "combined_size": len(partial_stdout) + len(partial_stderr),
                    "stdout_truncated": len(exc.stdout or "") > _OUTPUT_TRUNCATE_SIZE,
                    "stderr_truncated": len(exc.stderr or "") > _OUTPUT_TRUNCATE_SIZE,
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

            # Return a success response with the structured LLM content.
            return _success(status_msg, llm_content, **timeout_data)

    except PermissionError:
        return _error("Permission denied when executing command")
    except Exception as exc:  # pylint: disable=broad-except
        return _error(f"Unexpected error during command execution: {exc}")

# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_shell_command_tool(mcp: FastMCP):
    """Register the run_shell_command tool with proper tags synchronization."""
    common = dict(
        tags={"coding", "execution", "shell", "command", "system"}, 
        annotations={"category": "coding", "tags": ["coding", "execution", "shell", "command", "system"]}
    )
    mcp.tool(**common)(run_shell_command) 