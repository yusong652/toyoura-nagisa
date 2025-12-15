"""
PFC Python Console API - User Python commands for PFC simulations.

Provides REST endpoints for executing user Python commands (CLI `>` prefix)
in the PFC environment. Commands are saved as temporary scripts for traceability.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict

from backend.infrastructure.pfc.websocket_client import get_client, PFCWebSocketClient
from backend.infrastructure.monitoring.status_monitor import get_status_monitor
from backend.shared.utils.workspace import get_workspace_for_profile

router = APIRouter(prefix="/api/pfc/console", tags=["pfc-console"])


class ExecuteRequest(BaseModel):
    """Request body for PFC Python command execution."""
    code: str = Field(..., description="Python code to execute")
    session_id: str = Field(..., description="Session ID for task isolation")
    agent_profile: str = Field("pfc_expert", description="Agent profile for workspace resolution")
    timeout_ms: Optional[int] = Field(30000, description="Execution timeout in milliseconds (default: 30s)")


class ExecuteResponse(BaseModel):
    """Response body for PFC Python command execution."""
    success: bool
    task_id: Optional[str] = None
    script_name: Optional[str] = None
    script_path: Optional[str] = None
    code_preview: Optional[str] = None
    output: Optional[str] = None
    result: Optional[Any] = None
    elapsed_time: Optional[float] = None
    context: str = ""  # LLM context with caveat
    error: Optional[str] = None
    connected: bool = True  # PFC server connection status


class ConnectionStatusResponse(BaseModel):
    """Response body for PFC server connection status."""
    connected: bool
    message: str


def _format_pfc_python_context(
    code: str,
    task_id: str,
    output: str,
    error: Optional[str] = None
) -> str:
    """
    Format PFC Python execution result for LLM context injection.

    Uses XML-style tags similar to Claude Code's bash context format.

    Args:
        code: The Python code that was executed
        task_id: Task ID assigned to this execution
        output: Captured stdout from execution
        error: Error message if execution failed

    Returns:
        Formatted context string for LLM injection
    """
    context_parts = [
        "<pfc-python>",
        f"<input>{code}</input>",
        f"<task_id>{task_id}</task_id>",
        f"<output>{output if output else ''}</output>",
        f"<error>{error if error else ''}</error>",
        "</pfc-python>"
    ]
    return "\n".join(context_parts)


@router.get("/status", response_model=ConnectionStatusResponse)
async def check_connection_status() -> ConnectionStatusResponse:
    """
    Check PFC server connection status.

    Returns:
        ConnectionStatusResponse with connection status and message
    """
    try:
        client = await get_client()
        if client.connected:
            return ConnectionStatusResponse(
                connected=True,
                message="Connected to PFC server"
            )
        else:
            return ConnectionStatusResponse(
                connected=False,
                message="Not connected to PFC server"
            )
    except ConnectionError:
        return ConnectionStatusResponse(
            connected=False,
            message="PFC server is not available. Please start PFC server in PFC GUI."
        )
    except Exception as e:
        return ConnectionStatusResponse(
            connected=False,
            message=f"Connection check failed: {e}"
        )


@router.post("/execute", response_model=ExecuteResponse)
async def execute_pfc_python(request: ExecuteRequest) -> ExecuteResponse:
    """
    Execute PFC Python code from user console.

    The code is saved as a temporary script file in workspace/.quick_console/
    for traceability. Results are returned synchronously.

    Returns:
        ExecuteResponse with execution results, task info, and LLM context
    """
    try:
        # Get workspace path for the agent profile
        workspace_path = await get_workspace_for_profile(
            request.agent_profile,
            request.session_id
        )

        # Get PFC client (will auto-connect if needed)
        try:
            client = await get_client()
        except ConnectionError as e:
            return ExecuteResponse(
                success=False,
                connected=False,
                error=f"PFC server not available: {e}. Please start PFC server in PFC GUI.",
                context="",
            )

        # Execute quick Python code
        result = await client.send_quick_python(
            code=request.code,
            workspace_path=workspace_path,
            session_id=request.session_id,
            timeout_ms=request.timeout_ms or 30000,
        )

        # Extract data from result
        status = result.get("status", "error")
        message = result.get("message", "")
        data = result.get("data") or {}

        task_id = data.get("task_id", "")
        script_name = data.get("script_name", "")
        script_path = data.get("script_path", "")
        code_preview = data.get("code_preview", "")
        output = data.get("output", "")
        script_result = data.get("result")
        elapsed_time = data.get("elapsed_time")
        error_msg = data.get("error") if status == "error" else None

        # Format context for LLM injection
        context = _format_pfc_python_context(
            code=request.code,
            task_id=task_id,
            output=output,
            error=error_msg
        )

        # Store context for LLM injection (intent awareness)
        status_monitor = get_status_monitor(request.session_id)
        status_monitor.add_user_pfc_python_context(
            code=request.code,
            task_id=task_id,
            output=output,
            error=error_msg
        )

        return ExecuteResponse(
            success=(status == "success"),
            task_id=task_id,
            script_name=script_name,
            script_path=script_path,
            code_preview=code_preview,
            output=output,
            result=script_result,
            elapsed_time=elapsed_time,
            context=context,
            error=error_msg or (message if status == "error" else None),
            connected=True,
        )

    except ConnectionError as e:
        return ExecuteResponse(
            success=False,
            connected=False,
            error=f"Connection to PFC server lost: {e}",
            context="",
        )
    except TimeoutError as e:
        return ExecuteResponse(
            success=False,
            connected=True,
            error=f"Execution timed out: {e}",
            context="",
        )
    except Exception as e:
        return ExecuteResponse(
            success=False,
            connected=True,
            error=f"Unexpected error: {e}",
            context="",
        )
