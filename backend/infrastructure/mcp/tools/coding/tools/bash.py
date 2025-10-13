"""Shell command execution tool following Claude Code design principles.

This tool provides shell command execution with simple parameters and clean output,
designed to match Claude Code's Bash tool interface and behavior.
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional

from pydantic import Field
from fastmcp import FastMCP  # type: ignore
from fastmcp.server.context import Context  # type: ignore

from ..utils.path_security import validate_path_in_workspace, WORKSPACE_ROOT
from backend.infrastructure.mcp.utils.path_normalization import normalize_windows_paths, normalize_output_paths_to_llm_format
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response

__all__ = ["bash", "register_bash_tool"]

# Constants
DEFAULT_TIMEOUT_MS = 120000  # 2 minutes in milliseconds
MAX_TIMEOUT_MS = 600000      # 10 minutes maximum
MAX_OUTPUT_SIZE = 30000      # 30KB output limit (matching Claude Code)


def bash(
    context: Context,
    command: str = Field(
        ...,
        description="The command to execute"
    ),
    description: Optional[str] = Field(
        None,
        description=" Clear, concise description of what this command does in 5-10 words. Examples:\nInput: ls\nOutput: Lists files in current directory\n\nInput: git status\nOutput: Shows working tree status\n\nInput: npm install\nOutput: Installs package dependencies\n\nInput: mkdir foo\nOutput: Creates directory 'foo'"
    ),
    timeout: Optional[int] = Field(
        None,
        description="Optional timeout in milliseconds (max 600000)"
    ),
    run_in_background: bool = Field(
        False,
        description="Set to true to run in background without blocking, returns process ID immediately. Use BashOutput to monitor output. Default (false) blocks until completion and returns output directly. Use for: long builds, tests, dev servers."
    )
) -> Dict[str, Any]:
    """Executes bash commands in a persistent shell session with timeout and security.

IMPORTANT: This tool is for terminal operations like git, npm, docker, pytest, etc.
DO NOT use it for file operations - use specialized tools instead.

Usage notes:
  - Command argument is required
  - Timeout: 120000ms (2 minutes) default, 600000ms (10 minutes) max
  - Output truncated if exceeds 30000 characters
  - Always quote paths with spaces: cd "path with spaces/file.txt"
  - Use `run_in_background` for long-running processes (builds, tests, dev servers)

Avoid using these commands - use specialized tools instead:
  - File search: Use Glob (NOT find or ls)
  - Content search: Use Grep (NOT grep or rg)
  - Read files: Use Read (NOT cat/head/tail)
  - Edit files: Use Edit (NOT sed/awk)
  - Write files: Use Write (NOT echo >/cat <<EOF)

Command chaining:
  - Use '&&' to chain dependent commands: git add . && git commit -m "msg"
  - Use ';' for independent commands: command1 ; command2
  - DO NOT use newlines to separate commands

Working directory:
  - Maintain current directory using absolute paths
  - Avoid cd unless explicitly requested by user
  - Good: pytest /foo/bar/tests
  - Bad: cd /foo/bar && pytest tests
"""
    
    # Validate command
    if not command or not command.strip():
        return error_response("Command cannot be empty")

    # Handle Pydantic FieldInfo objects when invoked programmatically
    from pydantic.fields import FieldInfo
    if isinstance(description, FieldInfo):
        description = None
    if isinstance(timeout, FieldInfo):
        timeout = None
    if isinstance(run_in_background, FieldInfo):
        run_in_background = False
    
    # Acknowledge description parameter (used in tool interface)
    _ = description
    
    # Set timeout
    timeout_ms = timeout if timeout is not None else DEFAULT_TIMEOUT_MS
    if timeout_ms > MAX_TIMEOUT_MS:
        return error_response(f"Timeout cannot exceed {MAX_TIMEOUT_MS}ms (10 minutes)")
    if timeout_ms < 1000:
        return error_response("Timeout must be at least 1000ms (1 second)")

    timeout_seconds = timeout_ms / 1000.0

    # Validate workspace access
    if not validate_path_in_workspace("."):
        return error_response("Cannot access workspace directory")

    # Set working directory to workspace root
    work_dir = Path(str(WORKSPACE_ROOT))

    # Handle background execution
    if run_in_background:
        try:
            # Get session ID from MCP context
            session_id = getattr(context, 'client_id', None) if context else None
            if not session_id:
                return error_response("Session ID not available for background execution")

            from ..utils.background_process_manager import get_process_manager
            process_manager = get_process_manager()
            return process_manager.start_process(
                session_id=session_id,
                command=command,
                description=description
            )
        except Exception as e:
            return error_response(f"Failed to start background process: {e}")

    try:
        # Normalize Windows paths to prevent mixed separator errors
        normalized_command = normalize_windows_paths(command)

        # Execute command
        start_time = time.time()

        # Use shell=True for full shell command support
        process = subprocess.Popen(
            normalized_command,
            shell=True,
            cwd=str(work_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=os.environ.copy()
        )

        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
            exit_code = process.returncode
            execution_time = time.time() - start_time
            
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            exit_code = -1
            execution_time = timeout_seconds
            timeout_msg = f"Command timed out after {timeout_seconds:.1f} seconds"
            return error_response(timeout_msg)

        # Combine output (stdout and stderr)
        combined_output = ""
        if stdout:
            combined_output += stdout
        if stderr:
            if combined_output:
                combined_output += "\n" + stderr
            else:
                combined_output = stderr

        # Normalize Windows paths in output to LLM-friendly format (forward slashes)
        combined_output = normalize_output_paths_to_llm_format(combined_output)

        # Truncate if too large
        if len(combined_output) > MAX_OUTPUT_SIZE:
            combined_output = combined_output[:MAX_OUTPUT_SIZE] + f"\n\n... [OUTPUT TRUNCATED - exceeded {MAX_OUTPUT_SIZE} character limit] ..."

        # Build message for internal use
        if exit_code == 0:
            message = f"Command executed successfully (exit code {exit_code}, {execution_time:.1f}s)"
        else:
            message = f"Command failed with exit code {exit_code} ({execution_time:.1f}s)"
        
        # Always return complete terminal output for both success and failure
        # This matches real terminal behavior where you see all output regardless of exit code
        return success_response(
            message,
            llm_content={
                "parts": [
                    {"type": "text", "text": combined_output}
                ]
            },
            exit_code=exit_code,
            execution_time=execution_time,
            stdout=stdout,
            stderr=stderr,
            command=normalized_command,  # Show the normalized command that was actually executed
            original_command=command if normalized_command != command else None,  # Show original if different
            working_directory=str(work_dir)
        )

    except Exception as e:
        error_msg = f"Command execution failed: {e}"
        return error_response(error_msg)


def register_bash_tool(mcp: FastMCP):
    """Register the bash tool with FastMCP."""
    mcp.tool(
        tags={"coding", "execution", "shell"},
        annotations={
            "category": "coding",
            "tags": ["coding", "execution", "shell"],
            "primary_use": "Execute shell commands"
        }
    )(bash)