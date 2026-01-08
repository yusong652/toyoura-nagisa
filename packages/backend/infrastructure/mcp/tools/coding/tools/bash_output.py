"""
BashOutput tool for retrieving output from background bash processes.

Provides output retrieval functionality for toyoura-nagisa's background bash execution,
designed to match Claude Code's BashOutput tool behavior.
"""

from datetime import datetime
from typing import Dict, Any
from pydantic import Field
from fastmcp.server.context import Context  # type: ignore

from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.mcp.utils.shell import truncate_output
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
        truncated_stdout = truncate_output(result.stdout)
        parts.append(f"<stdout>\n{truncated_stdout}\n</stdout>")
    elif not result.has_new_output and result.status == "running":
        # Provide helpful context when no new output
        hint = " (Process may be idle or computing)" if result.runtime_seconds > 10 else ""
        parts.append(f"<info>No new output since last check{hint}</info>")

    if result.stderr:
        truncated_stderr = truncate_output(result.stderr)
        parts.append(f"<stderr>\n{truncated_stderr}\n</stderr>")

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
    )
) -> Dict[str, Any]:
    """
    Retrieves output from a running or completed background bash shell.

    Returns only new output since the last check, along with shell status.
    Use this tool to monitor long-running background processes.
    """
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
        result: ProcessOutputResult = process_manager.get_process_output(bash_id)

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