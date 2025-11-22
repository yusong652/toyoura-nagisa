"""
KillShell tool for terminating background bash processes.

Provides process termination functionality for aiNagisa's background bash execution,
designed to match Claude Code's KillShell tool behavior.
"""

from typing import Dict, Any
from pydantic import Field
from fastmcp.server.context import Context  # type: ignore

from backend.infrastructure.mcp.utils.tool_result import error_response
from ..utils.background_process_manager import get_process_manager

__all__ = ["kill_shell", "register_kill_shell_tool"]


async def kill_shell(
    context: Context,
    shell_id: str = Field(
        ...,
        description="The ID of the background shell to kill"
    )
) -> Dict[str, Any]:
    """
    Kills a running background bash shell by its ID.

    Takes a shell_id parameter identifying the shell to kill and returns a success or failure status.
    Use this tool when you need to terminate a long-running shell.
    """
    # Validate shell_id parameter
    if not shell_id or not shell_id.strip():
        return error_response("shell_id parameter is required and cannot be empty")

    try:
        # Get session ID from MCP context for session isolation
        session_id = getattr(context, 'client_id', None) if context else None
        if not session_id:
            return error_response("Session ID not available")

        # Get the background process manager
        process_manager = get_process_manager()

        # Verify the process belongs to this session
        if shell_id.strip() not in [pid for pid in process_manager.processes.keys()
                                   if process_manager.processes[pid].session_id == session_id]:
            return error_response(f"Process {shell_id} not found in your session")

        # Kill the specified process
        return process_manager.kill_process(shell_id.strip())
    except Exception as e:
        return error_response(f"Failed to kill process: {e}")


def register_kill_shell_tool(mcp):
    """
    Register the kill_shell tool with FastMCP.

    Args:
        mcp: FastMCP instance to register the tool with
    """
    mcp.tool(
        tags={"coding", "execution", "background", "process_control"},
        annotations={
            "category": "coding",
            "tags": ["coding", "execution", "background", "process_control"],
            "primary_use": "Terminate background bash processes",
            "dynamic": True,  # Only available when background processes exist
            "session_dependent": True
        }
    )(kill_shell)