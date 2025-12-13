"""
Shell Command Execution API - User shell commands for CLI.

Provides REST endpoints for executing user shell commands (CLI `!` prefix).
Manages working directory state and returns results with LLM context formatting.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional

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
# Key: (session_id, agent_profile)
_shell_services: dict[tuple[str, str], ShellService] = {}


async def _get_shell_service(session_id: str, agent_profile: str) -> ShellService:
    """Get or create ShellService for a session and profile."""
    cache_key = (session_id, agent_profile)
    if cache_key not in _shell_services:
        # Use unified workspace resolution based on agent profile
        workspace_root = await get_workspace_for_profile(agent_profile, session_id)
        _shell_services[cache_key] = ShellService(workspace_root=workspace_root)
    return _shell_services[cache_key]


class ExecuteRequest(BaseModel):
    """Request body for shell command execution."""
    command: str = Field(..., description="Shell command to execute")
    session_id: str = Field(..., description="Session ID for state management")
    agent_profile: str = Field("general", description="Agent profile for workspace resolution")
    timeout_ms: Optional[int] = Field(None, description="Optional timeout in milliseconds")


class ExecuteResponse(BaseModel):
    """Response body for shell command execution."""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    cwd: str
    context: str  # LLM context with caveat
    error: Optional[str] = None


class CwdResponse(BaseModel):
    """Response body for current working directory."""
    success: bool
    cwd: str
    error: Optional[str] = None


@router.post("/execute", response_model=ExecuteResponse)
async def execute_shell_command(request: ExecuteRequest) -> ExecuteResponse:
    """
    Execute a shell command.

    Executes the command in the session's current working directory.
    Handles `cd` commands specially to update the persistent cwd state.

    Returns:
        ExecuteResponse with stdout, stderr, exit_code, cwd, and LLM context
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

        return ExecuteResponse(
            success=result.exit_code == 0,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            cwd=service.get_cwd(),
            context=context,
        )

    except ShellValidationError as e:
        service = await _get_shell_service(request.session_id, request.agent_profile)
        return ExecuteResponse(
            success=False,
            stdout="",
            stderr=str(e),
            exit_code=1,
            cwd=service.get_cwd(),
            context="",
            error=str(e),
        )
    except ShellTimeoutError as e:
        service = await _get_shell_service(request.session_id, request.agent_profile)
        return ExecuteResponse(
            success=False,
            stdout="",
            stderr=str(e),
            exit_code=124,  # Standard timeout exit code
            cwd=service.get_cwd(),
            context="",
            error=str(e),
        )
    except ShellExecutorError as e:
        service = await _get_shell_service(request.session_id, request.agent_profile)
        return ExecuteResponse(
            success=False,
            stdout="",
            stderr=str(e),
            exit_code=1,
            cwd=service.get_cwd(),
            context="",
            error=str(e),
        )
    except Exception as e:
        try:
            service = await _get_shell_service(request.session_id, request.agent_profile)
            cwd = service.get_cwd()
        except Exception:
            cwd = ""
        return ExecuteResponse(
            success=False,
            stdout="",
            stderr=f"Unexpected error: {e}",
            exit_code=1,
            cwd=cwd,
            context="",
            error=str(e),
        )


@router.get("/cwd/{session_id}", response_model=CwdResponse)
async def get_current_directory(session_id: str, agent_profile: str = "general") -> CwdResponse:
    """
    Get the current working directory for a session.

    Args:
        session_id: Session ID
        agent_profile: Agent profile for workspace resolution

    Returns:
        CwdResponse with the current working directory path
    """
    try:
        service = await _get_shell_service(session_id, agent_profile)
        return CwdResponse(
            success=True,
            cwd=service.get_cwd(),
        )
    except Exception as e:
        return CwdResponse(
            success=False,
            cwd="",
            error=str(e),
        )


@router.post("/cwd/{session_id}")
async def set_current_directory(session_id: str, path: str) -> CwdResponse:
    """
    Set the current working directory for a session.

    Args:
        session_id: Session ID
        path: New working directory (absolute or relative)

    Returns:
        CwdResponse with the new working directory path
    """
    try:
        service = await _get_shell_service(session_id)
        new_cwd = service.set_cwd(path)
        return CwdResponse(
            success=True,
            cwd=new_cwd,
        )
    except ValueError as e:
        service = await _get_shell_service(session_id)
        return CwdResponse(
            success=False,
            cwd=service.get_cwd(),
            error=str(e),
        )
    except Exception as e:
        return CwdResponse(
            success=False,
            cwd="",
            error=str(e),
        )


def cleanup_session(session_id: str) -> None:
    """
    Clean up shell service for a session.

    Should be called when a session is deleted.

    Args:
        session_id: Session ID to clean up
    """
    if session_id in _shell_services:
        del _shell_services[session_id]
