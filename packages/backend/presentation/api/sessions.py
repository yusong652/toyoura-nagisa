"""
Session Management API Routes (2025 Standard).

This module handles all session-related API endpoints following:
- Clean Architecture principles (thin controllers, service delegation)
- FastAPI 2025 Standard (ApiResponse[T], standardized exceptions)
- RESTful conventions (resource-based URLs, proper HTTP methods)

Routes:
    POST   /history          - Create new session
    GET    /history          - List all sessions
    GET    /history/{id}     - Get session details
    POST   /history/switch   - Switch active session
    DELETE /history/{id}     - Delete session
    GET    /history/{id}/token-usage - Get token usage
"""
from typing import List, Optional, Literal
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from backend.presentation.models.api_models import ApiResponse
from backend.presentation.exceptions import (
    SessionNotFoundError,
    InternalServerError,
)
from backend.application.services.session_service import SessionService
from backend.infrastructure.llm.base.client import LLMClientBase

router = APIRouter(tags=["sessions"])


# =====================
# Response Data Models
# =====================
class SessionData(BaseModel):
    """Session metadata for API responses."""
    id: str = Field(..., description="Session UUID")
    name: str = Field(..., description="Session display name")
    created_at: str = Field(..., description="Creation timestamp (ISO format)")
    updated_at: str = Field(..., description="Last update timestamp (ISO format)")
    message_count: Optional[int] = Field(None, description="Number of messages")
    mode: Optional[str] = Field(None, description="Session mode (build or plan)")
    llm_config: Optional[dict] = Field(None, description="Session-specific LLM configuration")


class SessionCreateData(BaseModel):
    """Response data for session creation."""
    session_id: str = Field(..., description="UUID of the newly created session")
    llm_config: Optional[dict] = Field(None, description="Initial LLM configuration")


class SessionDetailsData(BaseModel):
    """Detailed session information including history."""
    session: SessionData = Field(..., description="Session metadata")
    history: List[dict] = Field(..., description="Complete message history")
    message_count: int = Field(..., description="Total message count")


class SessionSwitchData(BaseModel):
    """Response data for session switch operation."""
    session_id: str = Field(..., description="Target session ID")
    message_count: int = Field(..., description="Total messages in session")
    recent_messages: List[dict] = Field(..., description="Recent message context")


class SessionDeleteData(BaseModel):
    """Response data for session deletion."""
    session_id: str = Field(..., description="Deleted session ID")


class SessionModeUpdateData(BaseModel):
    """Response data for session mode updates."""
    session_id: str = Field(..., description="Session UUID")
    mode: str = Field(..., description="Updated session mode")


class TokenUsageData(BaseModel):
    """Token usage statistics for a session."""
    prompt_tokens: int = Field(default=0, description="Input tokens (context window usage)")
    completion_tokens: int = Field(default=0, description="Output tokens (AI response)")
    total_tokens: int = Field(default=0, description="Total tokens used in last turn")
    tokens_left: Optional[int] = Field(default=None, description="Remaining tokens in context window")


# =====================
# Request Models
# =====================
class CreateSessionRequest(BaseModel):
    """Request body for creating a new session."""
    name: Optional[str] = Field(None, description="Session display name (defaults to 'New Session')")


class SwitchSessionRequest(BaseModel):
    """Request body for switching to a different session."""
    session_id: str = Field(..., description="Target session UUID")


class UpdateSessionModeRequest(BaseModel):
    """Request body for updating session mode."""
    mode: Literal["build", "plan"] = Field(..., description="Target session mode")


# =====================
# Dependency Injection
# =====================
def get_session_service() -> SessionService:
    """Dependency injection for SessionService."""
    return SessionService()


def get_llm_client(request: Request) -> LLMClientBase:
    """Get LLM client from app state."""
    return request.app.state.llm_client


# =====================
# API Endpoints
# =====================
@router.post("/history", response_model=ApiResponse[SessionCreateData])
async def create_session(
    request: CreateSessionRequest,
    service: SessionService = Depends(get_session_service)
) -> ApiResponse[SessionCreateData]:
    """Create a new chat session.

    Creates a new session with the provided name, initializes session
    metadata and storage, and returns the new session ID.
    """
    try:
        session_name = request.name or "New Session"
        result = await service.create_session(session_name=session_name)
        
        # Get details of the newly created session to return initial config
        session_id = result["session_id"]
        session_details = await service.get_session_details(session_id)
        llm_config = session_details["session"].get("llm_config") if session_details else None
        
        return ApiResponse(
            success=True,
            message="Session created successfully",
            data=SessionCreateData(
                session_id=session_id,
                llm_config=llm_config
            )
        )
    except Exception as e:
        raise InternalServerError(
            message=f"Failed to create session: {str(e)}"
        )


@router.get("/history", response_model=ApiResponse[List[SessionData]])
async def list_sessions(
    service: SessionService = Depends(get_session_service)
) -> ApiResponse[List[SessionData]]:
    """List all available chat sessions.

    Returns metadata for all sessions including name, timestamps,
    and message counts.
    """
    try:
        sessions = await service.get_all_sessions()
        session_list = [
            SessionData(
                id=s["id"],
                name=s["name"],
                created_at=s["created_at"],
                updated_at=s["updated_at"],
                message_count=s.get("message_count"),
                mode=s.get("mode"),
                llm_config=s.get("llm_config"),
            )
            for s in sessions
        ]
        return ApiResponse(
            success=True,
            message=f"Retrieved {len(session_list)} sessions",
            data=session_list
        )
    except Exception as e:
        raise InternalServerError(
            message=f"Failed to retrieve sessions: {str(e)}"
        )


# =====================
# Legacy Routes (must be before /{session_id} to avoid path collision)
# =====================
@router.post("/history/create", response_model=ApiResponse[SessionCreateData], deprecated=True)
async def create_session_legacy(
    request: CreateSessionRequest,
    service: SessionService = Depends(get_session_service)
) -> ApiResponse[SessionCreateData]:
    """[DEPRECATED] Use POST /history instead."""
    return await create_session(request, service)


@router.get("/history/sessions", response_model=ApiResponse[List[SessionData]], deprecated=True)
async def list_sessions_legacy(
    service: SessionService = Depends(get_session_service)
) -> ApiResponse[List[SessionData]]:
    """[DEPRECATED] Use GET /history instead."""
    return await list_sessions(service)


# =====================
# Dynamic Routes
# =====================
@router.get("/history/{session_id}", response_model=ApiResponse[SessionDetailsData])
async def get_session_details(
    session_id: str,
    service: SessionService = Depends(get_session_service)
) -> ApiResponse[SessionDetailsData]:
    """Get detailed information about a specific session.

    Returns session metadata along with complete message history.
    """
    try:
        result = await service.get_session_details(session_id)
        if not result:
            raise SessionNotFoundError(session_id)

        return ApiResponse(
            success=True,
            message="Session details retrieved",
            data=SessionDetailsData(
                session=SessionData(**result["session"]),
                history=result["history"],
                message_count=result["message_count"]
            )
        )
    except SessionNotFoundError:
        raise
    except Exception as e:
        raise InternalServerError(
            message=f"Failed to retrieve session details: {str(e)}"
        )


@router.post("/history/switch", response_model=ApiResponse[SessionSwitchData])
async def switch_session(
    request: SwitchSessionRequest,
    service: SessionService = Depends(get_session_service),
    llm_client: LLMClientBase = Depends(get_llm_client)
) -> ApiResponse[SessionSwitchData]:
    """Switch to a different chat session.

    Validates the target session exists, clears tool cache,
    loads session history, and returns recent messages for context.
    """
    try:
        result = await service.switch_session(
            session_id=request.session_id,
            llm_client=llm_client
        )
        if not result:
            raise SessionNotFoundError(request.session_id)

        return ApiResponse(
            success=True,
            message=f"Switched to session {request.session_id[:8]}...",
            data=SessionSwitchData(
                session_id=result["session_id"],
                message_count=result["message_count"],
                recent_messages=result.get("recent_messages", [])
            )
        )
    except SessionNotFoundError:
        raise
    except Exception as e:
        raise InternalServerError(
            message=f"Failed to switch session: {str(e)}"
        )


@router.delete("/history/{session_id}", response_model=ApiResponse[SessionDeleteData])
async def delete_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
    llm_client: LLMClientBase = Depends(get_llm_client)
) -> ApiResponse[SessionDeleteData]:
    """Delete a chat session and all associated data.

    Deletes session history, metadata, clears tool cache,
    and removes related memories from vector DB.
    """
    try:
        result = await service.delete_session(
            session_id=session_id,
            llm_client=llm_client
        )
        if not result:
            raise SessionNotFoundError(session_id)

        return ApiResponse(
            success=True,
            message="Session deleted successfully",
            data=SessionDeleteData(session_id=session_id)
        )
    except SessionNotFoundError:
        raise
    except Exception as e:
        raise InternalServerError(
            message=f"Failed to delete session: {str(e)}"
        )


@router.get("/history/{session_id}/token-usage", response_model=ApiResponse[TokenUsageData])
async def get_token_usage(
    session_id: str,
    service: SessionService = Depends(get_session_service)
) -> ApiResponse[TokenUsageData]:
    """Get token usage information for a session.

    Returns the latest token usage statistics from the last LLM interaction.
    This data is persisted in runtime_state.json and survives session switches.
    """
    try:
        usage = await service.get_token_usage(session_id)
        if usage:
            return ApiResponse(
                success=True,
                message="Token usage retrieved",
                data=TokenUsageData(**usage)
            )
        return ApiResponse(
            success=True,
            message="No token usage data available",
            data=TokenUsageData()
        )
    except Exception as e:
        raise InternalServerError(
            message=f"Failed to retrieve token usage: {str(e)}"
        )


@router.post("/history/{session_id}/mode", response_model=ApiResponse[SessionModeUpdateData])
async def update_session_mode(
    session_id: str,
    request: UpdateSessionModeRequest,
    service: SessionService = Depends(get_session_service)
) -> ApiResponse[SessionModeUpdateData]:
    """Update the session mode (plan/build) and notify the frontend."""
    try:
        result = await service.update_session_mode(session_id, request.mode)
        if not result:
            raise SessionNotFoundError(session_id)

        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService
        await WebSocketNotificationService.send_session_mode_update(session_id, request.mode)

        return ApiResponse(
            success=True,
            message="Session mode updated",
            data=SessionModeUpdateData(session_id=session_id, mode=request.mode)
        )
    except SessionNotFoundError:
        raise
    except Exception as e:
        raise InternalServerError(
            message=f"Failed to update session mode: {str(e)}"
        )

