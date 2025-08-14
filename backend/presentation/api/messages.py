"""
Message Management API Routes.

This module handles message-related API endpoints following Clean Architecture principles.
Focuses on message CRUD operations within chat sessions.
"""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from backend.presentation.models.api_models import DeleteMessageRequest
from backend.domain.services.message_service import MessageService

router = APIRouter(tags=["messages"])


def get_message_service() -> MessageService:
    """
    Dependency injection for MessageService.
    
    Returns:
        MessageService: Message service instance
    """
    return MessageService()


@router.post("/messages/delete", response_model=dict)
async def delete_message(
    request: DeleteMessageRequest,
    service: MessageService = Depends(get_message_service)
) -> Dict[str, Any]:
    """
    Delete a specific message from a chat session.
    
    This endpoint:
    1. Validates the session exists
    2. Deletes the specified message from storage
    3. Updates session metadata
    
    Args:
        request: Delete message request with session_id and message_id
        
    Returns:
        Dict[str, Any]: Deletion result with structure:
            - session_id: str - Session containing the message
            - message_id: str - ID of deleted message
            - success: bool - Operation success flag
            - message: str - User-friendly status message
    
    Raises:
        HTTPException: 404 if session/message not found, 500 if deletion fails
    """
    try:
        result = await service.delete_message(
            session_id=request.session_id,
            message_id=request.message_id
        )
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Message {request.message_id} not found in session {request.session_id}"
            )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete message: {str(e)}"
        )