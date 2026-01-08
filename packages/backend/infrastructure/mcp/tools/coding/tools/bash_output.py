"""
BashOutput tool for retrieving output from background bash processes.

Provides output retrieval functionality for toyoura-nagisa's background bash execution,
designed to match Claude Code's BashOutput tool behavior.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import Field
from fastmcp.server.context import Context  # type: ignore

from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.shell.background_process_manager import (
    get_process_manager,
    ProcessOutputResult,
)

__all__ = ["bash_output", "register_bash_output_tool"]


def _build_llm_content(result: ProcessOutputResult) -> str:
    """Build LLM-friendly content from ProcessOutputResult."""
    parts = [f"<status>{result.status}</status>"]

    if result.exit_code is not None:
        parts.append(f"<exit_code>{result.exit_code}</exit_code>")

    if result.stdout:
        parts.append(f"<stdout>\n{result.stdout}\n</stdout>")
    elif not result.has_new_output and result.status == "running":
        # Provide helpful context when no new output
        hint = ""
        if result.is_python_script and result.runtime_seconds < 5:
            hint = " (Python unbuffered mode enabled, checking for output...)"
        elif result.runtime_seconds > 10:
            hint = " (Process may be idle or computing)"
        parts.append(f"<info>No new output since last check{hint}</info>")

    if result.stderr:
        parts.append(f"<stderr>\n{result.stderr}\n</stderr>")

    parts.append(f"<timestamp>{datetime.now().isoformat()}Z</timestamp>")

    parts.append("<stats>")
    parts.append(f"  <new_lines>{result.new_line_count}</new_lines>")
    parts.append(f"  <total_lines>{result.total_line_count}</total_lines>")
    parts.append(f"  <runtime_seconds>{result.runtime_seconds:.1f}</runtime_seconds>")
    parts.append("</stats>")

    return '\n\n'.join(parts)


async def bash_output(
    context: Context,
    bash_id: str = Field(
        ...,
        min_length=1,
        description="The ID of the background shell to retrieve output from"
    ),
    filter: Optional[str] = Field(
        None,
        description="Optional regular expression to filter the output lines. Only lines matching this regex will be included in the result. Any lines that do not match will no longer be available to read."
    ),
    wait: int = Field(
        1,
        description="Wait time in seconds before checking output (default: 1). Use longer wait times for long-running tasks to avoid excessive polling."
    )
) -> Dict[str, Any]:
    """
    Retrieves output from a running or completed background bash shell.

    Takes a shell_id parameter identifying the shell and always returns only new output since the last check.
    Returns stdout and stderr output along with shell status.
    Supports optional regex filtering to show only lines matching a pattern.
    Use this tool when you need to monitor or check the output of a long-running shell.
    """
    # Parameter is pre-validated by Pydantic (min_length=1)

    # Wait before checking output (prevents excessive polling, non-blocking)
    if wait > 0:
        await asyncio.sleep(wait)

    try:
        # Get session ID from MCP context for session isolation
        # Architecture guarantee: tool_manager.py always injects _meta.client_id
        session_id = context.client_id

        # Get the background process manager
        process_manager = get_process_manager()

        # Verify the process belongs to this session
        if bash_id not in [pid for pid in process_manager.processes.keys()
                          if process_manager.processes[pid].session_id == session_id]:
            return error_response(f"No shell found with ID: {bash_id}")

        # Retrieve output from the specified process
        result: ProcessOutputResult = process_manager.get_process_output(bash_id, filter)

        # Convert infrastructure result to tool response
        if not result.success:
            return error_response(result.error or "Unknown error")

        return success_response(
            message="Retrieved incremental output from background process",
            llm_content={
                "parts": [
                    {"type": "text", "text": _build_llm_content(result)}
                ]
            },
            process_id=result.process_id,
            status=result.status,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            command=result.command,
            has_new_output=result.has_new_output,
            incremental_mode=True,
            new_line_count=result.new_line_count,
            total_line_count=result.total_line_count,
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        return error_response(f"Failed to retrieve process output: {e}")


def register_bash_output_tool(mcp):
    """
    Register the bash_output tool with FastMCP.

    Args:
        mcp: FastMCP instance to register the tool with
    """
    mcp.tool(
        tags={"coding", "execution", "background", "monitoring"},
        annotations={
            "category": "coding",
            "tags": ["coding", "execution", "background", "monitoring"],
            "primary_use": "Retrieve output from background bash processes",
            "dynamic": True,  # Only available when background processes exist
            "session_dependent": True
        }
    )(bash_output)