"""
BashOutput tool for retrieving output from background bash processes.

Provides output retrieval functionality for aiNagisa's background bash execution,
designed to match Claude Code's BashOutput tool behavior.
"""

from typing import Dict, Any, Optional
from pydantic import Field
from fastmcp.server.context import Context  # type: ignore

from backend.infrastructure.mcp.utils.tool_result import error_response
from ..utils.background_process_manager import get_process_manager

__all__ = ["bash_output", "register_bash_output_tool"]


def bash_output(
    context: Context,
    bash_id: str = Field(
        ...,
        description="The ID of the background shell to retrieve output from"
    ),
    filter: Optional[str] = Field(
        None,
        description="Optional regular expression to filter the output lines. Only lines matching this regex will be included in the result. Any lines that do not match will no longer be available to read."
    )
) -> Dict[str, Any]:
    """
    Retrieves output from a running or completed background bash shell.

    Takes a shell_id parameter identifying the shell and always returns only new output since the last check.
    Returns stdout and stderr output along with shell status.
    Supports optional regex filtering to show only lines matching a pattern.
    Use this tool when you need to monitor or check the output of a long-running shell.
    """
    # Validate bash_id parameter
    if not bash_id or not bash_id.strip():
        return error_response("bash_id parameter is required and cannot be empty")

    try:
        # Get session ID from MCP context for session isolation
        session_id = getattr(context, 'client_id', None) if context else None
        if not session_id:
            return error_response("Session ID not available")

        # Get the background process manager
        process_manager = get_process_manager()

        # Verify the process belongs to this session
        if bash_id.strip() not in [pid for pid in process_manager.processes.keys()
                                  if process_manager.processes[pid].session_id == session_id]:
            return error_response(f"Process {bash_id} not found in your session")

        # Retrieve output from the specified process
        return process_manager.get_process_output(bash_id.strip(), filter)
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