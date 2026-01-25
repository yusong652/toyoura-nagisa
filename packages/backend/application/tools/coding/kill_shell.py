"""
KillShell tool for terminating background bash processes.

Provides process termination functionality for toyoura-nagisa's background bash execution,
designed to match Claude Code's KillShell tool behavior.
"""

from datetime import datetime
from typing import Dict, Any
from pydantic import Field
from fastmcp.server.context import Context  # type: ignore

from backend.application.tools.registrar import ToolRegistrar
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.shell.background_process_manager import (
    get_process_manager,
    KillProcessResult,
)

__all__ = ["kill_shell", "register_kill_shell_tool"]


async def kill_shell(
    context: Context,
    shell_id: str = Field(
        ...,
        min_length=1,
        description="The ID of the background shell to kill"
    )
) -> Dict[str, Any]:
    """
    Kills a running background bash shell by its ID.

    Takes a shell_id parameter identifying the shell to kill and returns a success or failure status.
    Use this tool when you need to terminate a long-running shell.
    """
    # Parameter is pre-validated by Pydantic (min_length=1)

    try:
        # Get session ID from MCP context for session isolation
        # Architecture guarantee: tool_manager.py always injects _meta.client_id
        session_id = context.client_id

        # Get the background process manager
        process_manager = get_process_manager()

        # Verify the process belongs to this session
        if shell_id not in [pid for pid in process_manager.processes.keys()
                           if process_manager.processes[pid].session_id == session_id]:
            return error_response(f"Process {shell_id} not found in your session")

        # Kill the specified process
        result: KillProcessResult = process_manager.kill_process(shell_id)

        # Convert infrastructure result to tool response
        if not result.success:
            return error_response(result.error or "Unknown error")

        kill_message = f"Successfully killed shell: {result.process_id} ({result.command})"

        return success_response(
            message=kill_message,
            llm_content={
                "parts": [
                    {"type": "text", "text": kill_message}
                ]
            },
            shell_id=result.process_id,
            command=result.command,
            kill_successful=True,
            final_output=result.final_output,
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        return error_response(f"Failed to kill process: {e}")


def register_kill_shell_tool(registrar: ToolRegistrar):
    """
    Register the kill_shell tool with the registrar.

    Args:
        registrar: Tool registrar instance to register the tool with
    """
    registrar.tool(
        tags={"coding", "execution", "background", "process_control"},
        annotations={
            "category": "coding",
            "tags": ["coding", "execution", "background", "process_control"],
            "primary_use": "Terminate background bash processes",
            "dynamic": True,  # Only available when background processes exist
            "session_dependent": True
        }
    )(kill_shell)
