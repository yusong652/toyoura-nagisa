"""Shell command execution tool following Claude Code design principles.

This tool provides shell command execution with simple parameters and clean output,
designed to match Claude Code's Bash tool interface and behavior.

Uses the infrastructure layer ShellExecutor for actual command execution.
"""

from typing import Dict, Any, Optional, cast

from pydantic import Field
from fastmcp import FastMCP  # type: ignore
from fastmcp.server.context import Context  # type: ignore

from ..utils.path_security import get_workspace_root_async
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.mcp.utils.shell import process_shell_output
from backend.infrastructure.shell import ShellExecutor
from backend.infrastructure.shell.executor import (
    ShellExecutorError,
    TimeoutError as ShellTimeoutError,
    ValidationError as ShellValidationError,
)

__all__ = ["bash", "register_bash_tool"]

# Singleton executor instance
_executor: Optional[ShellExecutor] = None


def _get_executor() -> ShellExecutor:
    """Get or create the singleton ShellExecutor instance."""
    global _executor
    if _executor is None:
        _executor = ShellExecutor()
    return _executor


async def bash(
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
  - cwd is fixed to workspace root (shown in <env> as `workspace:`)
  - Always use absolute paths; cd commands do NOT change cwd for subsequent calls
  - Good: pytest /foo/bar/tests
  - Bad: cd /foo/bar && pytest tests
"""
    
    # Handle Pydantic FieldInfo objects when invoked programmatically
    from pydantic.fields import FieldInfo
    if isinstance(description, FieldInfo):
        description = None
    if isinstance(timeout, FieldInfo):
        timeout = None
    if isinstance(run_in_background, FieldInfo):
        run_in_background = False

    # Get workspace root dynamically based on current session
    work_dir = await get_workspace_root_async(context)

    # Handle background execution (separate path, not using ShellExecutor)
    if run_in_background:
        try:
            from ..utils.background_process_manager import get_process_manager
            process_manager = get_process_manager()
            # Architecture guarantee: tool_manager.py always injects _meta.client_id
            return process_manager.start_process(
                session_id=cast(str, context.client_id),
                command=command,
                description=description
            )
        except Exception as e:
            return error_response(f"Failed to start background process: {e}")

    # Execute command using infrastructure layer ShellExecutor
    try:
        executor = _get_executor()
        result = await executor.execute(
            command=command,
            cwd=str(work_dir),
            timeout_ms=timeout,
        )

        # Process output for LLM consumption
        combined_output = process_shell_output(
            stdout=result.stdout,
            stderr=result.stderr,
        )

        # Build response message
        if result.exit_code == 0:
            message = f"Command executed successfully (exit code {result.exit_code}, {result.execution_time:.1f}s)"
        else:
            message = f"Command failed with exit code {result.exit_code} ({result.execution_time:.1f}s)"

        # Return complete terminal output for both success and failure
        return success_response(
            message,
            llm_content={
                "parts": [
                    {"type": "text", "text": combined_output}
                ]
            },
            exit_code=result.exit_code,
            execution_time=result.execution_time,
            stdout=result.stdout,
            stderr=result.stderr,
            command=result.command,
            original_command=result.original_command,
            working_directory=result.working_directory,
        )

    except ShellValidationError as e:
        return error_response(str(e))
    except ShellTimeoutError as e:
        return error_response(str(e))
    except ShellExecutorError as e:
        return error_response(str(e))
    except Exception as e:
        return error_response(f"Unexpected error: {e}")


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