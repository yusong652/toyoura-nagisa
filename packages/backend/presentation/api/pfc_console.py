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
from backend.infrastructure.pfc.client import get_pfc_client
from backend.infrastructure.monitoring.status_monitor import get_status_monitor
from backend.shared.utils.workspace import get_workspace_for_profile

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
    output: Optional[str] = Field(default=None, description="Execution output")
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
    """Check PFC server connection status."""
    try:
        client = await get_pfc_client()
        if client.connected:
            return ApiResponse(
                success=True,
                message="Connected to PFC server",
                data=ConnectionStatusData(connected=True)
            )
        else:
            return ApiResponse(
                success=True,
                message="Not connected to PFC server",
                data=ConnectionStatusData(connected=False)
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

        try:
            client = await get_pfc_client()
        except ConnectionError as e:
            return ApiResponse(
                success=False,
                message=f"PFC server not available: {e}. Please start PFC server in PFC GUI.",
                error_code="PFC_NOT_CONNECTED",
                data=ExecuteData(connected=False, context="")
            )

        result = await client.send_user_console(
            code=request.code,
            workspace_path=str(workspace_path),
            session_id=request.session_id,
            timeout_ms=request.timeout_ms or 30000,
        )

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

        # Execution completed (even if Python code raised an error).
        # Error details are in output field for the CLI to display.
        # Only infrastructure errors (connection, timeout) should set success=False.
        return ApiResponse(
            success=True,
            message="Code executed" if status == "success" else (error_msg or message or "Execution completed with errors"),
            data=ExecuteData(
                task_id=task_id,
                script_name=script_name,
                script_path=script_path,
                code_preview=code_preview,
                output=output,
                result=script_result,
                elapsed_time=elapsed_time,
                context=context,
                connected=True,
            )
        )

    except ConnectionError as e:
        return ApiResponse(
            success=False,
            message=f"Connection to PFC server lost: {e}",
            error_code="PFC_CONNECTION_LOST",
            data=ExecuteData(connected=False, context="")
        )
    except TimeoutError as e:
        return ApiResponse(
            success=False,
            message=f"Execution timed out: {e}",
            error_code="TIMEOUT",
            data=ExecuteData(connected=True, context="")
        )
    except Exception as e:
        raise InternalServerError(message=f"Unexpected error: {e}")


@router.post("/reset", response_model=ApiResponse[ResetData])
async def reset_workspace(request: ResetRequest) -> ApiResponse[ResetData]:
    """Reset workspace state for testing.

    WARNING: This permanently deletes:
    - User console scripts and counter
    - All task history (memory + disk)
    - Git pfc-executions branch (all execution snapshots)

    Use only for development/testing to get a clean slate.
    """
    try:
        workspace_path = await get_workspace_for_profile(
            request.agent_profile,
            request.session_id
        )

        try:
            client = await get_pfc_client()
        except ConnectionError as e:
            return ApiResponse(
                success=False,
                message=f"PFC server not available: {e}. Please start PFC server in PFC GUI.",
                error_code="PFC_NOT_CONNECTED",
                data=ResetData(connected=False)
            )

        result = await client.reset_workspace(
            workspace_path=str(workspace_path)
        )

        status = result.get("status", "error")
        message = result.get("message", "")
        data = result.get("data") or {}

        success = (status == "success")
        return ApiResponse(
            success=success,
            message=message,
            error_code=None if success else "RESET_ERROR",
            data=ResetData(
                user_console=data.get("user_console"),
                tasks=data.get("tasks"),
                git=data.get("git"),
                connected=True,
            )
        )

    except ConnectionError as e:
        return ApiResponse(
            success=False,
            message=f"Connection to PFC server lost: {e}",
            error_code="PFC_CONNECTION_LOST",
            data=ResetData(connected=False)
        )
    except Exception as e:
        raise InternalServerError(message=f"Unexpected error: {e}")


@router.get("/tasks", response_model=ApiResponse[TasksListData])
async def list_pfc_tasks(
    limit: int = Query(default=20, ge=1, le=100, description="Maximum results"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination")
) -> ApiResponse[TasksListData]:
    """List all PFC tasks with pagination.

    This endpoint provides a user-facing view of PFC task history,
    reusing pfc-server's persistent task storage.
    """
    try:
        try:
            client = await get_pfc_client()
        except ConnectionError as e:
            return ApiResponse(
                success=False,
                message=f"PFC server not available: {e}. Please start PFC server in PFC GUI.",
                error_code="PFC_NOT_CONNECTED",
                data=TasksListData(connected=False)
            )

        result = await client.list_tasks(
            session_id=None,
            offset=offset,
            limit=limit,
        )

        status = result.get("status", "error")
        message = result.get("message", "")
        data = result.get("data", [])
        pagination = result.get("pagination", {})

        if status != "success":
            return ApiResponse(
                success=False,
                message=message,
                error_code="LIST_ERROR",
                data=TasksListData(connected=True)
            )

        tasks = []
        for task in data:
            tasks.append(TaskItem(
                task_id=task.get("task_id", ""),
                session_id=task.get("session_id", ""),
                status=task.get("status", "unknown"),
                entry_script=task.get("entry_script", task.get("script_path", task.get("name", "unknown"))),
                description=task.get("description", ""),
                start_time=task.get("start_time"),
                end_time=task.get("end_time"),
                elapsed_time=task.get("elapsed_time"),
                git_commit=task.get("git_commit"),
                historical=task.get("historical", False),
            ))

        return ApiResponse(
            success=True,
            message=message or f"Retrieved {len(tasks)} task(s)",
            data=TasksListData(
                tasks=tasks,
                total_count=pagination.get("total_count", len(tasks)),
                displayed_count=pagination.get("displayed_count", len(tasks)),
                has_more=pagination.get("has_more", False),
                connected=True,
            )
        )

    except ConnectionError as e:
        return ApiResponse(
            success=False,
            message=f"Connection to PFC server lost: {e}",
            error_code="PFC_CONNECTION_LOST",
            data=TasksListData(connected=False)
        )
    except Exception as e:
        raise InternalServerError(message=f"Unexpected error: {e}")


@router.get("/tasks/{task_id}", response_model=ApiResponse[TaskStatusData])
async def get_task_status(
    task_id: str,
    session_id: Optional[str] = Query(default=None, description="Session ID for context injection")
) -> ApiResponse[TaskStatusData]:
    """Get detailed status of a specific PFC task."""
    try:
        try:
            client = await get_pfc_client()
        except ConnectionError as e:
            return ApiResponse(
                success=False,
                message=f"PFC server not available: {e}. Please start PFC server in PFC GUI.",
                error_code="PFC_NOT_CONNECTED",
                data=TaskStatusData(task_id=task_id, status="error", connected=False)
            )

        result = await client.check_task_status(task_id)
        status = result.get("status", "error")

        if status == "not_found":
            return ApiResponse(
                success=False,
                message=f"Task not found: {task_id}",
                error_code="TASK_NOT_FOUND",
                data=TaskStatusData(task_id=task_id, status="not_found", connected=True)
            )

        data = result.get("data", {})

        status_map = {
            "running": "running",
            "success": "completed",
            "error": "failed",
            "interrupted": "interrupted",
        }

        mapped_status = status_map.get(status) or status
        entry_script = data.get("entry_script", data.get("script_path"))
        description = data.get("description")
        output = data.get("output")
        error = data.get("error")
        elapsed_time = data.get("elapsed_time")
        git_commit = data.get("git_commit")

        if session_id:
            status_monitor = get_status_monitor(session_id)
            status_monitor.add_user_pfc_task_context(
                task_id=task_id,
                status=mapped_status,
                entry_script=entry_script,
                description=description,
                output=output,
                error=error,
                elapsed_time=elapsed_time,
                git_commit=git_commit,
            )

        return ApiResponse(
            success=True,
            message=result.get("message", f"Task {task_id}: {mapped_status}"),
            data=TaskStatusData(
                task_id=task_id,
                status=mapped_status,
                entry_script=entry_script,
                description=description,
                output=output,
                result=data.get("result"),
                start_time=data.get("start_time"),
                end_time=data.get("end_time"),
                elapsed_time=elapsed_time,
                git_commit=git_commit,
                connected=True,
            )
        )

    except ConnectionError as e:
        return ApiResponse(
            success=False,
            message=f"Connection to PFC server lost: {e}",
            error_code="PFC_CONNECTION_LOST",
            data=TaskStatusData(task_id=task_id, status="error", connected=False)
        )
    except Exception as e:
        raise InternalServerError(message=f"Unexpected error: {e}")
