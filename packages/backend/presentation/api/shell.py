"""
Shell Command Execution API (2025 Standard).

Provides REST endpoints for executing user shell commands (CLI `!` prefix).
Manages working directory state and returns results with LLM context formatting.

Routes:
    POST /api/shell/execute     - Execute shell command
    GET  /api/shell/cwd         - Get current working directory
    PUT  /api/shell/cwd         - Set current working directory
"""
from typing import Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.presentation.models.api_models import ApiResponse
from backend.application.services.shell import ShellService
from backend.infrastructure.shell.executor import (
    ShellExecutorError,
    TimeoutError as ShellTimeoutError,
    ValidationError as ShellValidationError,
)
from backend.infrastructure.monitoring.status_monitor import get_status_monitor
from backend.shared.utils.workspace import get_workspace_for_profile

router = APIRouter(prefix="/api/shell", tags=["shell"])

# Service instances per session+profile (simple in-memory cache)
_shell_services: dict[tuple[str, str], ShellService] = {}


async def _get_shell_service(session_id: str, agent_profile: str) -> ShellService:
    """Get or create ShellService for a session and profile."""
    cache_key = (session_id, agent_profile)
    if cache_key not in _shell_services:
        workspace_root = await get_workspace_for_profile(agent_profile, session_id)
        _shell_services[cache_key] = ShellService(workspace_root=workspace_root)
    return _shell_services[cache_key]


# =====================
# Response Data Models
# =====================
class ShellExecuteData(BaseModel):
    """Response data for shell command execution."""
    stdout: str = Field(..., description="Standard output")
    stderr: str = Field(..., description="Standard error")
    exit_code: int = Field(..., description="Exit code")
    cwd: str = Field(..., description="Current working directory")
    context: str = Field(..., description="LLM context with caveat")


class CwdData(BaseModel):
    """Response data for current working directory."""
    cwd: str = Field(..., description="Current working directory path")


# =====================
# Request Models
# =====================
class ExecuteRequest(BaseModel):
    """Request body for shell command execution."""
    command: str = Field(..., description="Shell command to execute")
    session_id: str = Field(..., description="Session ID for state management")
    agent_profile: str = Field(default="general", description="Agent profile")
    timeout_ms: Optional[int] = Field(default=None, description="Timeout in milliseconds")


class SetCwdRequest(BaseModel):
    """Request body for setting current working directory."""
    session_id: str = Field(..., description="Session ID")
    agent_profile: str = Field(default="general", description="Agent profile")
    path: str = Field(..., description="New working directory path")


# =====================
# API Endpoints
# =====================
@router.post("/execute", response_model=ApiResponse[ShellExecuteData])
async def execute_shell_command(request: ExecuteRequest) -> ApiResponse[ShellExecuteData]:
    """Execute a shell command.

    Executes the command in the session's current working directory.
    Handles `cd` commands specially to update the persistent cwd state.
    """
    try:
        service = await _get_shell_service(request.session_id, request.agent_profile)
        result, context = await service.execute(
            command=request.command,
            timeout_ms=request.timeout_ms,
        )

        # Store context for LLM injection (intent awareness)
        status_monitor = get_status_monitor(request.session_id)
        status_monitor.add_user_bash_context(
            command=request.command,
            stdout=result.stdout,
            stderr=result.stderr,
        )

        # Command execution was successful (even if exit_code != 0).
        # Non-zero exit codes are valid outcomes (e.g., grep returns 1 when no match).
        # Only infrastructure errors (timeout, validation) should set success=False.
        return ApiResponse(
            success=True,
            message="Command executed" if result.exit_code == 0 else f"Command exited with code {result.exit_code}",
            data=ShellExecuteData(
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.exit_code,
                cwd=service.get_cwd(),
                context=context,
            )
        )

    except ShellValidationError as e:
        service = await _get_shell_service(request.session_id, request.agent_profile)
        return ApiResponse(
            success=False,
            message=str(e),
            error_code="VALIDATION_ERROR",
            data=ShellExecuteData(
                stdout="",
                stderr=str(e),
                exit_code=1,
                cwd=service.get_cwd(),
                context="",
            )
        )
    except ShellTimeoutError as e:
        service = await _get_shell_service(request.session_id, request.agent_profile)
        return ApiResponse(
            success=False,
            message=str(e),
            error_code="TIMEOUT",
            data=ShellExecuteData(
                stdout="",
                stderr=str(e),
                exit_code=124,
                cwd=service.get_cwd(),
                context="",
            )
        )
    except ShellExecutorError as e:
        service = await _get_shell_service(request.session_id, request.agent_profile)
        return ApiResponse(
            success=False,
            message=str(e),
            error_code="EXECUTOR_ERROR",
            data=ShellExecuteData(
                stdout="",
                stderr=str(e),
                exit_code=1,
                cwd=service.get_cwd(),
                context="",
            )
        )
    except Exception as e:
        try:
            service = await _get_shell_service(request.session_id, request.agent_profile)
            cwd = service.get_cwd()
        except Exception:
            cwd = ""
        return ApiResponse(
            success=False,
            message=f"Unexpected error: {e}",
            error_code="INTERNAL_ERROR",
            data=ShellExecuteData(
                stdout="",
                stderr=str(e),
                exit_code=1,
                cwd=cwd,
                context="",
            )
        )


@router.get("/cwd", response_model=ApiResponse[CwdData])
async def get_current_directory(
    session_id: str = Query(..., description="Session ID"),
    agent_profile: str = Query(default="general", description="Agent profile")
) -> ApiResponse[CwdData]:
    """Get the current working directory for a session."""
    try:
        service = await _get_shell_service(session_id, agent_profile)
        return ApiResponse(
            success=True,
            message="Current directory retrieved",
            data=CwdData(cwd=service.get_cwd())
        )
    except Exception as e:
        return ApiResponse(
            success=False,
            message=str(e),
            error_code="INTERNAL_ERROR",
            data=CwdData(cwd="")
        )


@router.put("/cwd", response_model=ApiResponse[CwdData])
async def set_current_directory(request: SetCwdRequest) -> ApiResponse[CwdData]:
    """Set the current working directory for a session."""
    try:
        service = await _get_shell_service(request.session_id, request.agent_profile)
        new_cwd = service.set_cwd(request.path)
        return ApiResponse(
            success=True,
            message=f"Changed to {new_cwd}",
            data=CwdData(cwd=new_cwd)
        )
    except ValueError as e:
        service = await _get_shell_service(request.session_id, request.agent_profile)
        return ApiResponse(
            success=False,
            message=str(e),
            error_code="INVALID_PATH",
            data=CwdData(cwd=service.get_cwd())
        )
    except Exception as e:
        return ApiResponse(
            success=False,
            message=str(e),
            error_code="INTERNAL_ERROR",
            data=CwdData(cwd="")
        )


# =====================
# Legacy Routes (deprecated)
# =====================
@router.get("/cwd/{session_id}", response_model=ApiResponse[CwdData], deprecated=True)
async def get_current_directory_legacy(
    session_id: str,
    agent_profile: str = "general"
) -> ApiResponse[CwdData]:
    """[DEPRECATED] Use GET /api/shell/cwd with query params instead."""
    return await get_current_directory(session_id, agent_profile)


@router.post("/cwd/{session_id}", response_model=ApiResponse[CwdData], deprecated=True)
async def set_current_directory_legacy(
    session_id: str,
    path: str,
    agent_profile: str = "general"
) -> ApiResponse[CwdData]:
    """[DEPRECATED] Use PUT /api/shell/cwd instead."""
    request = SetCwdRequest(session_id=session_id, agent_profile=agent_profile, path=path)
    return await set_current_directory(request)


# =====================
# Utilities
# =====================
def cleanup_session(session_id: str) -> None:
    """Clean up shell service for a session.

    Should be called when a session is deleted.
    """
    keys_to_remove = [key for key in _shell_services if key[0] == session_id]
    for key in keys_to_remove:
        del _shell_services[key]
