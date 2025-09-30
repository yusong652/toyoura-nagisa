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
    """Executes a given bash command in a persistent shell session with optional timeout, ensuring proper handling and security measures.

Before executing the command, please follow these steps:

1. Directory Verification:
   - If the command will create new directories or files, first use the LS tool to verify the parent directory exists and is the correct location
   - For example, before running "mkdir foo/bar", first use LS to check that "foo" exists and is the intended parent directory

2. Command Execution:
   - Always quote file paths that contain spaces with double quotes (e.g., cd "path with spaces/file.txt")
   - Examples of proper quoting:
     - cd "/Users/name/My Documents" (correct)
     - cd /Users/name/My Documents (incorrect - will fail)
     - python "/path/with spaces/script.py" (correct)
     - python /path/with spaces/script.py (incorrect - will fail)
   - After ensuring proper quoting, execute the command.
   - Capture the output of the command.

Usage notes:
  - The command argument is required.
  - You can specify an optional timeout in milliseconds (up to 600000ms / 10 minutes). If not specified, commands will timeout after 120000ms (2 minutes).
  - It is very helpful if you write a clear, concise description of what this command does in 5-10 words.
  - If the output exceeds 30000 characters, output will be truncated before being returned to you.
  - You can use the `run_in_background` parameter to run the command in the background, which allows you to continue working while the command runs. You can monitor the output using the Bash tool as it becomes available. Never use `run_in_background` to run 'sleep' as it will return immediately. You do not need to use '&' at the end of the command when using this parameter.
  - VERY IMPORTANT: You MUST avoid using search commands like `find` and `grep`. Instead use Grep, Glob, or Task to search. You MUST avoid read tools like `cat`, `head`, `tail`, and `ls`, and use Read and LS to read files.
 - If you _still_ need to run `grep`, STOP. ALWAYS USE ripgrep at `rg` first, which all Claude Code users have pre-installed.
  - When issuing multiple commands, use the ';' or '&&' operator to separate them. DO NOT use newlines (newlines are ok in quoted strings).
  - Try to maintain your current working directory throughout the session by using absolute paths and avoiding usage of `cd`. You may use `cd` if the User explicitly requests it.
    <good-example>
    pytest /foo/bar/tests
    </good-example>
    <bad-example>
    cd /foo/bar && pytest tests
    </bad-example>
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
        # Execute command
        start_time = time.time()
        
        # Use shell=True for full shell command support
        process = subprocess.Popen(
            command,
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
            combined_output,  # Complete terminal output for LLM
            exit_code=exit_code,
            execution_time=execution_time,
            stdout=stdout,
            stderr=stderr,
            command=command,
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