"""
Message Management API Routes (2025 Standard).

This module handles message-related API endpoints following:
- Clean Architecture principles
- FastAPI 2025 Standard (ApiResponse[T], standardized exceptions)
- RESTful conventions

Routes:
    DELETE /messages/{session_id}/{message_id} - Delete a message
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.presentation.models.api_models import ApiResponse
from backend.presentation.exceptions import MessageNotFoundError, InternalServerError
from backend.application.services.message_service import MessageService

router = APIRouter(tags=["messages"])


# =====================
# Response Data Models
# =====================
class MessageDeleteData(BaseModel):
    """Response data for message deletion."""
    session_id: str = Field(..., description="Session containing the message")
    message_id: str = Field(..., description="ID of deleted message")


# =====================
# Request Models
# =====================
class DeleteMessageRequest(BaseModel):
    """Request body for deleting a message (legacy)."""
    session_id: str = Field(..., description="Session ID")
    message_id: str = Field(..., description="Message ID to delete")


# =====================
# Dependency Injection
# =====================
def get_message_service() -> MessageService:
    """Dependency injection for MessageService."""
    return MessageService()


# =====================
# API Endpoints
# =====================
@router.delete(
    "/messages/{session_id}/{message_id}",
    response_model=ApiResponse[MessageDeleteData]
)
async def delete_message(
    session_id: str,
    message_id: str,
    service: MessageService = Depends(get_message_service)
) -> ApiResponse[MessageDeleteData]:
    """Delete a specific message from a chat session.

    Validates the session exists, deletes the message from storage,
    and updates session metadata.
    """
    try:
        result = await service.delete_message_async(
            session_id=session_id,
            message_id=message_id
        )

        if not result:
            raise MessageNotFoundError(message_id, session_id)

        return ApiResponse(
            success=True,
            message="Message deleted successfully",
            data=MessageDeleteData(
                session_id=session_id,
                message_id=message_id
            )
        )
    except MessageNotFoundError:
        raise
    except Exception as e:
        raise InternalServerError(
            message=f"Failed to delete message: {str(e)}"
        )


# =====================
# Legacy Routes (deprecated)
# =====================
@router.post("/messages/delete", response_model=ApiResponse[MessageDeleteData], deprecated=True)
async def delete_message_legacy(
    request: DeleteMessageRequest,
    service: MessageService = Depends(get_message_service)
) -> ApiResponse[MessageDeleteData]:
    """[DEPRECATED] Use DELETE /messages/{session_id}/{message_id} instead."""
    return await delete_message(request.session_id, request.message_id, service)
