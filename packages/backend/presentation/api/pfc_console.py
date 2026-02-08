"""
PFC Python Console API (2025 Standard).

Provides REST endpoints for executing user Python commands (CLI `>` prefix)
in the PFC environment. Commands are saved as temporary scripts for traceability.

Routes:
    GET  /api/pfc/console/status        - Check PFC server connection
    POST /api/pfc/console/execute       - Execute PFC Python code
    POST /api/pfc/console/reset         - Reset workspace state (dev only)
    GET  /api/pfc/console/tasks         - List all PFC tasks
    GET  /api/pfc/console/tasks/{id}    - Get task status
"""
from typing import Optional, Any, Dict, List
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.presentation.models.api_models import ApiResponse
from backend.presentation.exceptions import InternalServerError
from backend.infrastructure.pfc.task_manager import get_pfc_task_manager
from backend.infrastructure.monitoring.status_monitor import get_status_monitor
from backend.shared.utils.workspace import get_workspace_for_profile
from backend.shared.utils.mcp_utils import extract_mcp_text

router = APIRouter(prefix="/api/pfc/console", tags=["pfc-console"])


# =====================
# Response Data Models
# =====================
class ConnectionStatusData(BaseModel):
    """Response data for PFC server connection status."""
    connected: bool = Field(..., description="Whether connected to PFC server")


class ExecuteData(BaseModel):
    """Response data for PFC Python command execution."""
    task_id: Optional[str] = Field(default=None, description="Task ID")
    script_name: Optional[str] = Field(default=None, description="Script file name")
    script_path: Optional[str] = Field(default=None, description="Script file path")
    code_preview: Optional[str] = Field(default=None, description="Code preview")
    output: Optional[str] = Field(default=None, description="Execution output (stdout)")
    error: Optional[str] = Field(default=None, description="Error traceback if execution failed")
    result: Optional[Any] = Field(default=None, description="Script result")
    elapsed_time: Optional[float] = Field(default=None, description="Execution time")
    context: str = Field(default="", description="LLM context with caveat")
    connected: bool = Field(default=True, description="PFC server connection status")


class ResetData(BaseModel):
    """Response data for workspace reset."""
    user_console: Optional[Dict[str, Any]] = Field(default=None, description="User console reset info")
    tasks: Optional[Dict[str, Any]] = Field(default=None, description="Tasks reset info")
    git: Optional[Dict[str, Any]] = Field(default=None, description="Git reset info")
    connected: bool = Field(default=True, description="PFC server connection status")


class TaskItem(BaseModel):
    """Individual task item in list response."""
    task_id: str = Field(..., description="Task identifier")
    session_id: str = Field(..., description="Session identifier")
    status: str = Field(..., description="Task status")
    entry_script: str = Field(..., description="Entry script path")
    description: str = Field(..., description="Task description")
    start_time: Optional[float] = Field(default=None, description="Start timestamp")
    end_time: Optional[float] = Field(default=None, description="End timestamp")
    elapsed_time: Optional[float] = Field(default=None, description="Elapsed time in seconds")
    git_commit: Optional[str] = Field(default=None, description="Git commit hash")
    historical: bool = Field(default=False, description="Whether from historical storage")


class TasksListData(BaseModel):
    """Response data for task list query."""
    tasks: List[TaskItem] = Field(default_factory=list, description="Task list")
    total_count: int = Field(default=0, description="Total task count")
    displayed_count: int = Field(default=0, description="Displayed task count")
    has_more: bool = Field(default=False, description="Whether more tasks exist")
    connected: bool = Field(default=True, description="PFC server connection status")


class TaskStatusData(BaseModel):
    """Response data for individual task status query."""
    task_id: str = Field(..., description="Task identifier")
    status: str = Field(..., description="Task status: running, completed, failed, interrupted, not_found")
    entry_script: Optional[str] = Field(default=None, description="Entry script path")
    description: Optional[str] = Field(default=None, description="Task description")
    output: Optional[str] = Field(default=None, description="Task output")
    result: Optional[Any] = Field(default=None, description="Task result")
    start_time: Optional[float] = Field(default=None, description="Start timestamp")
    end_time: Optional[float] = Field(default=None, description="End timestamp")
    elapsed_time: Optional[float] = Field(default=None, description="Elapsed time in seconds")
    git_commit: Optional[str] = Field(default=None, description="Git commit hash")
    error: Optional[str] = Field(default=None, description="Error message for failed tasks")
    connected: bool = Field(default=True, description="PFC server connection status")


# =====================
# Request Models
# =====================
class ExecuteRequest(BaseModel):
    """Request body for PFC Python command execution."""
    code: str = Field(..., description="Python code to execute")
    session_id: str = Field(..., description="Session ID for task isolation")
    agent_profile: str = Field(default="pfc_expert", description="Agent profile for workspace resolution")
    timeout_ms: Optional[int] = Field(default=30000, description="Execution timeout in milliseconds")


class ResetRequest(BaseModel):
    """Request body for workspace reset."""
    session_id: str = Field(..., description="Session ID for workspace resolution")
    agent_profile: str = Field(default="pfc_expert", description="Agent profile for workspace resolution")


# =====================
# Helper Functions
# =====================
def _format_pfc_python_context(
    code: str,
    task_id: str,
    output: str,
    error: Optional[str] = None
) -> str:
    """Format PFC Python execution result for LLM context injection.

    Uses XML-style tags similar to Claude Code's bash context format.
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


# =====================
# API Endpoints
# =====================
@router.get("/status", response_model=ApiResponse[ConnectionStatusData])
async def check_connection_status() -> ApiResponse[ConnectionStatusData]:
    """Check PFC server connection status via MCP."""
    try:
        from backend.infrastructure.mcp.client import get_mcp_client_manager
        mcp_manager = get_mcp_client_manager()
        result = await mcp_manager.call_tool("pfc_list_tasks", {"limit": 1})
        if result.get("status") == "error":
            raise ConnectionError(result.get("message", "MCP tool call failed"))
        return ApiResponse(
            success=True,
            message="Connected to PFC server",
            data=ConnectionStatusData(connected=True)
        )
    except ConnectionError:
        return ApiResponse(
            success=True,
            message="PFC server is not available. Please start PFC server in PFC GUI.",
            data=ConnectionStatusData(connected=False)
        )
    except Exception as e:
        raise InternalServerError(message=f"Connection check failed: {e}")


@router.post("/execute", response_model=ApiResponse[ExecuteData])
async def execute_pfc_python(request: ExecuteRequest) -> ApiResponse[ExecuteData]:
    """Execute PFC Python code from user console.

    The code is saved as a temporary script file in workspace/.user_console/
    for traceability. Results are returned synchronously.
    """
    try:
        # Skip empty code - user typed ">" but no actual code
        if not request.code.strip():
            return ApiResponse(
                success=True,
                message="",
                data=ExecuteData(connected=True, context="")
            )

        workspace_path = await get_workspace_for_profile(
            request.agent_profile,
            request.session_id
        )

        # Create local task tracking
        task_manager = get_pfc_task_manager()
        task_id = task_manager.create_task(
            session_id=request.session_id,
            script_path="user_console",
            description=request.code[:50] + "..." if len(request.code) > 50 else request.code,
            source="user_console",
        )

        from backend.infrastructure.mcp.client import get_mcp_client_manager
        mcp_manager = get_mcp_client_manager()
        timeout_s = (request.timeout_ms or 30000) // 1000

        try:
            mcp_result = await mcp_manager.call_tool("pfc_execute_code", {
                "code": request.code,
                "timeout": timeout_s,
                "run_in_background": False,
            })
            if mcp_result.get("status") == "error":
                raise ConnectionError(mcp_result.get("message", "MCP tool call failed"))
        except ConnectionError as e:
            task_manager.update_status(task_id, "failed", error=str(e))
            return ApiResponse(
                success=False,
                message=f"PFC bridge not available: {e}. Please start pfc-bridge in PFC GUI.",
                error_code="PFC_NOT_CONNECTED",
                data=ExecuteData(connected=False, context="")
            )

        # Parse MCP text response
        text = extract_mcp_text(mcp_result)

        # Extract fields from MCP response text
        output = ""
        error_msg = None
        elapsed_time = None
        output_section = False
        output_lines = []

        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("- status:"):
                status_val = stripped.split(":", 1)[1].strip().lower()
            elif stripped.startswith("- error:"):
                error_msg = stripped.split(":", 1)[1].strip()
                if error_msg == "None" or error_msg == "":
                    error_msg = None
            elif "Output:" in line or "=== Script Output" in line:
                output_section = True
                continue
            elif output_section:
                output_lines.append(line)

        output = "\n".join(output_lines).strip()

        # Update task status
        is_error = error_msg is not None
        task_status = "failed" if is_error else "completed"
        task_manager.update_status(
            task_id,
            task_status,
            error=error_msg,
        )
        if output:
            task_manager.set_output(task_id, output)

        context = _format_pfc_python_context(
            code=request.code,
            task_id=task_id,
            output=output,
            error=error_msg
        )

        status_monitor = get_status_monitor(request.session_id)
        status_monitor.add_user_pfc_python_context(
            code=request.code,
            task_id=task_id,
            output=output,
            error=error_msg or ""
        )

        return ApiResponse(
            success=True,
            message="Code executed" if not is_error else (error_msg or "Execution completed with errors"),
            data=ExecuteData(
                task_id=task_id,
                output=output,
                error=error_msg,
                context=context,
                connected=True,
            )
        )

    except ConnectionError as e:
        # Update task status on connection failure
        if 'task_id' in locals() and 'task_manager' in locals():
            task_manager.update_status(task_id, "failed", error=str(e))
        return ApiResponse(
            success=False,
            message=f"Connection to PFC server lost: {e}",
            error_code="PFC_CONNECTION_LOST",
            data=ExecuteData(connected=False, context="")
        )
    except TimeoutError as e:
        # Update task status on timeout
        if 'task_id' in locals() and 'task_manager' in locals():
            task_manager.update_status(task_id, "failed", error=str(e))
        return ApiResponse(
            success=False,
            message=f"Execution timed out: {e}",
            error_code="TIMEOUT",
            data=ExecuteData(connected=True, context="")
        )
    except Exception as e:
        # Update task status on unexpected error
        if 'task_id' in locals() and 'task_manager' in locals():
            task_manager.update_status(task_id, "failed", error=str(e))
        raise InternalServerError(message=f"Unexpected error: {e}")


@router.post("/reset", response_model=ApiResponse[ResetData])
async def reset_workspace(request: ResetRequest) -> ApiResponse[ResetData]:
    """Reset local task state for testing.

    WARNING: This permanently deletes all local task history.
    Use only for development/testing to get a clean slate.
    """
    try:
        task_manager = get_pfc_task_manager()
        cleared = task_manager.clear_all_tasks()

        return ApiResponse(
            success=True,
            message=f"Cleared {cleared} task(s) from local state",
            data=ResetData(
                tasks={"cleared_count": cleared},
                connected=True,
            )
        )

    except Exception as e:
        raise InternalServerError(message=f"Unexpected error: {e}")


@router.get("/tasks", response_model=ApiResponse[TasksListData])
async def list_pfc_tasks(
    limit: int = Query(default=20, ge=1, le=100, description="Maximum results"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination")
) -> ApiResponse[TasksListData]:
    """List all PFC tasks with pagination from local task manager."""
    try:
        task_manager = get_pfc_task_manager()
        all_tasks = task_manager.list_tasks(offset=offset, limit=limit)

        tasks = []
        for t in all_tasks:
            tasks.append(TaskItem(
                task_id=t.task_id,
                session_id=t.session_id,
                status=t.status,
                entry_script=t.script_path,
                description=t.description or "",
                start_time=t.start_time.timestamp() if t.start_time else None,
                end_time=t.end_time.timestamp() if t.end_time else None,
                elapsed_time=t.elapsed_seconds,
                git_commit=t.git_commit,
                historical=False,
            ))

        total = task_manager.list_tasks(offset=0, limit=9999)
        total_count = len(total)

        return ApiResponse(
            success=True,
            message=f"Retrieved {len(tasks)} task(s)",
            data=TasksListData(
                tasks=tasks,
                total_count=total_count,
                displayed_count=len(tasks),
                has_more=(offset + limit) < total_count,
                connected=True,
            )
        )

    except Exception as e:
        raise InternalServerError(message=f"Unexpected error: {e}")


@router.get("/tasks/{task_id}", response_model=ApiResponse[TaskStatusData])
async def get_task_status(
    task_id: str,
    session_id: Optional[str] = Query(default=None, description="Session ID for context injection")
) -> ApiResponse[TaskStatusData]:
    """Get detailed status of a specific PFC task from local task manager."""
    try:
        task_manager = get_pfc_task_manager()
        task = task_manager.get_task(task_id)

        if task is None:
            return ApiResponse(
                success=False,
                message=f"Task not found: {task_id}",
                error_code="TASK_NOT_FOUND",
                data=TaskStatusData(task_id=task_id, status="not_found", connected=True)
            )

        output = "\n".join(task.output_lines) if task.output_lines else None

        if session_id:
            status_monitor = get_status_monitor(session_id)
            status_monitor.add_user_pfc_task_context(
                task_id=task_id,
                status=task.status,
                entry_script=task.script_path,
                description=task.description,
                output=output,
                error=task.error,
                elapsed_time=task.elapsed_seconds,
                git_commit=task.git_commit,
            )

        return ApiResponse(
            success=True,
            message=f"Task {task_id}: {task.status}",
            data=TaskStatusData(
                task_id=task_id,
                status=task.status,
                entry_script=task.script_path,
                description=task.description,
                output=output,
                result=task.result,
                start_time=task.start_time.timestamp() if task.start_time else None,
                end_time=task.end_time.timestamp() if task.end_time else None,
                elapsed_time=task.elapsed_seconds,
                git_commit=task.git_commit,
                error=task.error,
                connected=True,
            )
        )

    except Exception as e:
        raise InternalServerError(message=f"Unexpected error: {e}")
