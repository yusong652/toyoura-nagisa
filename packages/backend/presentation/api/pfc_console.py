"""
PFC Python Console API - User Python commands for PFC simulations.

Provides REST endpoints for executing user Python commands (CLI `>` prefix)
in the PFC environment. Commands are saved as temporary scripts for traceability.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict

from backend.infrastructure.pfc.client import get_client, PFCWebSocketClient
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


class ResetRequest(BaseModel):
    """Request body for workspace reset."""
    session_id: str = Field(..., description="Session ID for workspace resolution")
    agent_profile: str = Field("pfc_expert", description="Agent profile for workspace resolution")


class ResetResponse(BaseModel):
    """Response body for workspace reset."""
    success: bool
    message: str
    quick_console: Optional[Dict[str, Any]] = None
    tasks: Optional[Dict[str, Any]] = None
    git: Optional[Dict[str, Any]] = None
    connected: bool = True
    error: Optional[str] = None


class TaskItem(BaseModel):
    """Individual task item in list response."""
    task_id: str
    session_id: str
    status: str
    entry_script: str
    description: str
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    elapsed_time: Optional[float] = None
    git_commit: Optional[str] = None
    historical: bool = False


class TasksListResponse(BaseModel):
    """Response body for task list query."""
    success: bool
    message: str
    tasks: list[TaskItem] = []
    total_count: int = 0
    displayed_count: int = 0
    has_more: bool = False
    connected: bool = True
    error: Optional[str] = None


class TaskStatusResponse(BaseModel):
    """Response body for individual task status query."""
    success: bool
    message: str
    task_id: str
    status: str  # running, completed, failed, interrupted, not_found
    entry_script: Optional[str] = None
    description: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None
    result: Optional[Any] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    elapsed_time: Optional[float] = None
    git_commit: Optional[str] = None
    connected: bool = True


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
            workspace_path=str(workspace_path),
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
            error=error_msg or ""
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


@router.post("/reset", response_model=ResetResponse)
async def reset_workspace(request: ResetRequest) -> ResetResponse:
    """
    Reset workspace state for testing.

    WARNING: This permanently deletes:
    - Quick console scripts and counter
    - All task history (memory + disk)
    - Git pfc-executions branch (all execution snapshots)

    Use only for development/testing to get a clean slate.

    Returns:
        ResetResponse with reset details for each component
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
            return ResetResponse(
                success=False,
                message=f"PFC server not available: {e}",
                connected=False,
                error=f"PFC server not available: {e}. Please start PFC server in PFC GUI.",
            )

        # Execute workspace reset
        result = await client.reset_workspace(
            workspace_path=str(workspace_path)
        )

        # Extract data from result
        status = result.get("status", "error")
        message = result.get("message", "")
        data = result.get("data") or {}

        return ResetResponse(
            success=(status == "success"),
            message=message,
            quick_console=data.get("quick_console"),
            tasks=data.get("tasks"),
            git=data.get("git"),
            connected=True,
            error=None if status == "success" else message,
        )

    except ConnectionError as e:
        return ResetResponse(
            success=False,
            message=f"Connection to PFC server lost: {e}",
            connected=False,
            error=str(e),
        )
    except Exception as e:
        return ResetResponse(
            success=False,
            message=f"Unexpected error: {e}",
            connected=True,
            error=str(e),
        )


@router.get("/tasks", response_model=TasksListResponse)
async def list_pfc_tasks(
    limit: int = 20,
    offset: int = 0,
) -> TasksListResponse:
    """
    List all PFC tasks with pagination.

    This endpoint provides a user-facing view of PFC task history,
    reusing pfc-server's persistent task storage.

    Args:
        limit: Maximum number of tasks to return (default: 20)
        offset: Number of tasks to skip (default: 0)

    Returns:
        TasksListResponse with task list and pagination info
    """
    try:
        # Get PFC client (will auto-connect if needed)
        try:
            client = await get_client()
        except ConnectionError as e:
            return TasksListResponse(
                success=False,
                message=f"PFC server not available: {e}",
                connected=False,
                error=f"PFC server not available. Please start PFC server in PFC GUI.",
            )

        # Query task list from pfc-server
        result = await client.list_tasks(
            session_id=None,  # All sessions
            offset=offset,
            limit=limit,
        )

        # Extract data
        status = result.get("status", "error")
        message = result.get("message", "")
        data = result.get("data", [])
        pagination = result.get("pagination", {})

        if status != "success":
            return TasksListResponse(
                success=False,
                message=message,
                connected=True,
                error=message,
            )

        # Convert raw task data to TaskItem models
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

        return TasksListResponse(
            success=True,
            message=message,
            tasks=tasks,
            total_count=pagination.get("total_count", len(tasks)),
            displayed_count=pagination.get("displayed_count", len(tasks)),
            has_more=pagination.get("has_more", False),
            connected=True,
        )

    except ConnectionError as e:
        return TasksListResponse(
            success=False,
            message=f"Connection to PFC server lost: {e}",
            connected=False,
            error=str(e),
        )
    except Exception as e:
        return TasksListResponse(
            success=False,
            message=f"Unexpected error: {e}",
            connected=True,
            error=str(e),
        )


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """
    Get detailed status of a specific PFC task.

    Args:
        task_id: Task ID to query

    Returns:
        TaskStatusResponse with task details and output
    """
    try:
        # Get PFC client
        try:
            client = await get_client()
        except ConnectionError as e:
            return TaskStatusResponse(
                success=False,
                message=f"PFC server not available: {e}",
                task_id=task_id,
                status="error",
                connected=False,
                error="PFC server not available. Please start PFC server in PFC GUI.",
            )

        # Query task status
        result = await client.check_task_status(task_id)
        status = result.get("status", "error")

        if status == "not_found":
            return TaskStatusResponse(
                success=False,
                message=f"Task not found: {task_id}",
                task_id=task_id,
                status="not_found",
                connected=True,
                error=f"Task {task_id} not found or expired.",
            )

        # Extract data for all other statuses
        data = result.get("data", {})

        # Map pfc-server status to response status
        status_map = {
            "running": "running",
            "success": "completed",
            "error": "failed",
            "interrupted": "interrupted",
        }

        return TaskStatusResponse(
            success=True,
            message=result.get("message", f"Task {task_id}: {status}"),
            task_id=task_id,
            status=status_map.get(status) or status,
            entry_script=data.get("entry_script", data.get("script_path")),
            description=data.get("description"),
            output=data.get("output"),
            error=data.get("error"),
            result=data.get("result"),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            elapsed_time=data.get("elapsed_time"),
            git_commit=data.get("git_commit"),
            connected=True,
        )

    except ConnectionError as e:
        return TaskStatusResponse(
            success=False,
            message=f"Connection to PFC server lost: {e}",
            task_id=task_id,
            status="error",
            connected=False,
            error=str(e),
        )
    except Exception as e:
        return TaskStatusResponse(
            success=False,
            message=f"Unexpected error: {e}",
            task_id=task_id,
            status="error",
            connected=True,
            error=str(e),
        )
