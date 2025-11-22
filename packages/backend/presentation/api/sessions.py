"""
Session Management API Routes.

This module handles all session-related API endpoints following Clean Architecture principles.
Routes are thin layers that delegate business logic to the service layer.
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from backend.presentation.models.api_models import (
    SwitchSessionRequest,
    DeleteSessionRequest,
    NewHistoryRequest,
)
from backend.application.services.session_service import SessionService
from backend.infrastructure.llm.base.client import LLMClientBase

router = APIRouter(tags=["sessions"])


def get_session_service() -> SessionService:
    """
    Dependency injection for SessionService.
    
    Returns:
        SessionService: Session service instance
    """
    return SessionService()


def get_llm_client(request: Request) -> LLMClientBase:
    """
    Get LLM client from app state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        LLMClientBase: LLM client instance
    """
    return request.app.state.llm_client


@router.post("/history/create", response_model=dict)
async def create_session(
    request: NewHistoryRequest,
    service: SessionService = Depends(get_session_service)
) -> dict:
    """
    Create a new chat session.
    
    This endpoint:
    1. Creates a new session with the provided name
    2. Initializes session metadata and storage
    3. Returns the new session ID for client use
    
    Args:
        request: New history request with session name
        
    Returns:
        dict: Creation result with structure:
            - session_id: str - UUID of the newly created session
            - success: bool - Always True if successful
    
    Raises:
        HTTPException: 500 if session creation fails
    """
    try:
        session_name = request.name or "New Session"
        result = await service.create_session(session_name=session_name)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create session: {str(e)}"
        )


@router.get("/history/sessions", response_model=List[dict])
async def get_all_sessions(
    service: SessionService = Depends(get_session_service)
) -> List[dict]:
    """
    Get all available chat sessions.
    
    Returns:
        List[dict]: List of session metadata:
            - id: str - Session UUID
            - name: str - Session display name
            - created_at: str - Creation timestamp
            - updated_at: str - Last update timestamp
            - message_count: int - Number of messages
    
    Raises:
        HTTPException: 500 if retrieval fails
    """
    try:
        sessions = await service.get_all_sessions()
        return sessions
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to retrieve sessions: {str(e)}"
        )


@router.get("/history/{session_id}", response_model=dict)
async def get_session_details(
    session_id: str,
    service: SessionService = Depends(get_session_service)
) -> dict:
    """
    Get detailed information about a specific session.
    
    Args:
        session_id: Session UUID
        
    Returns:
        dict: Session details with structure:
            - session: dict - Session metadata
            - history: List[dict] - Complete message history
            - message_count: int - Total message count
    
    Raises:
        HTTPException: 404 if session not found, 500 if retrieval fails
    """
    try:
        result = await service.get_session_details(session_id)
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve session details: {str(e)}"
        )


@router.post("/history/switch", response_model=dict)
async def switch_session(
    request: SwitchSessionRequest,
    service: SessionService = Depends(get_session_service),
    llm_client: LLMClientBase = Depends(get_llm_client)
) -> dict:
    """
    Switch to a different chat session.
    
    This endpoint:
    1. Validates the target session exists
    2. Clears tool cache for the session
    3. Loads session history
    4. Returns recent messages for context
    
    Args:
        request: Switch session request with session_id
        
    Returns:
        dict: Switch result with structure:
            - session_id: str - Target session ID
            - success: bool - Operation success flag
            - message_count: int - Total messages in session
            - recent_messages: List[dict] - Recent message context
    
    Raises:
        HTTPException: 404 if session not found, 500 if switch fails
    """
    try:
        result = await service.switch_session(
            session_id=request.session_id,
            llm_client=llm_client
        )
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Session {request.session_id} not found"
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to switch session: {str(e)}"
        )


@router.delete("/history/{session_id}", response_model=dict)
async def delete_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
    llm_client: LLMClientBase = Depends(get_llm_client)
) -> dict:
    """
    Delete a chat session and all associated data.

    This endpoint:
    1. Validates session exists
    2. Deletes session history and metadata
    3. Clears tool cache
    4. Removes related memories from vector DB

    Args:
        session_id: Session UUID to delete

    Returns:
        dict: Deletion result with structure:
            - session_id: str - Deleted session ID
            - success: bool - Operation success flag
            - message: str - User-friendly status message

    Raises:
        HTTPException: 404 if session not found, 500 if deletion fails
    """
    try:
        result = await service.delete_session(
            session_id=session_id,
            llm_client=llm_client
        )
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete session: {str(e)}"
        )


@router.get("/history/{session_id}/token-usage", response_model=dict)
async def get_token_usage(
    session_id: str,
    service: SessionService = Depends(get_session_service)
) -> dict:
    """
    Get token usage information for a session.

    Returns the latest token usage statistics from the last LLM interaction.
    This data is persisted in runtime_state.json and survives session switches.

    Args:
        session_id: Session UUID

    Returns:
        dict: Token usage information with structure:
            - prompt_tokens: int - Input tokens (context window usage)
            - completion_tokens: int - Output tokens (AI response)
            - total_tokens: int - Total tokens used in last turn
            - tokens_left: int - Remaining tokens in context window
            Or empty dict if no token usage data available

    Raises:
        HTTPException: 500 if retrieval fails
    """
    try:
        usage = await service.get_token_usage(session_id)
        return usage if usage else {}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve token usage: {str(e)}"
        )