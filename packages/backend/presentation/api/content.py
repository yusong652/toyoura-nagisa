"""
Content Generation API (2025 Standard).

Handles content generation endpoints including title generation.

Routes:
    POST /content/title    - Generate session title
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from backend.presentation.models.api_models import ApiResponse
from backend.presentation.exceptions import (
    BadRequestError,
    SessionNotFoundError,
    InternalServerError,
)
from backend.application.services.contents import TitleService
from backend.infrastructure.llm.base.client import LLMClientBase

router = APIRouter(tags=["content"])


# =====================
# Response Data Models
# =====================
class TitleGenerateData(BaseModel):
    """Response data for title generation."""
    session_id: str = Field(..., description="Session that received new title")
    title: str = Field(..., description="Generated title text")


# =====================
# Request Models
# =====================
class GenerateTitleRequest(BaseModel):
    """Request body for title generation."""
    session_id: str = Field(..., description="Session ID to generate title for")


# =====================
# Dependency Injection
# =====================
def get_title_service() -> TitleService:
    """Dependency injection for TitleService."""
    return TitleService()


def get_llm_client(request: Request) -> LLMClientBase:
    """Get LLM client from app state."""
    return request.app.state.llm_client


# =====================
# API Endpoints
# =====================
@router.post("/content/title", response_model=ApiResponse[TitleGenerateData])
async def generate_title(
    request: GenerateTitleRequest,
    http_request: Request,
    service: TitleService = Depends(get_title_service),
    llm_client: LLMClientBase = Depends(get_llm_client)
) -> ApiResponse[TitleGenerateData]:
    """Generate a descriptive title for a chat session.

    Analyzes conversation history and uses LLM to generate a contextual title.
    """
    try:
        result = await service.generate_title_for_session(
            session_id=request.session_id,
            llm_client=llm_client
        )

        if not result:
            raise SessionNotFoundError(request.session_id)

        if result.get("error"):
            raise BadRequestError(message=result["error"])

        return ApiResponse(
            success=True,
            message="Title generated successfully",
            data=TitleGenerateData(
                session_id=request.session_id,
                title=result.get("title", "")
            )
        )
    except (SessionNotFoundError, BadRequestError):
        raise
    except Exception as e:
        raise InternalServerError(
            message=f"Failed to generate title: {str(e)}"
        )


# =====================
# Legacy Routes (deprecated)
# =====================
@router.post("/history/generate-title", response_model=ApiResponse[TitleGenerateData], deprecated=True)
async def generate_title_legacy(
    http_request: Request,
    service: TitleService = Depends(get_title_service),
    llm_client: LLMClientBase = Depends(get_llm_client)
) -> ApiResponse[TitleGenerateData]:
    """[DEPRECATED] Use POST /content/title instead."""
    data = await http_request.json()
    session_id = data.get('session_id')
    if not session_id:
        raise BadRequestError(message="session_id not provided in request")
    request = GenerateTitleRequest(session_id=session_id)
    return await generate_title(request, http_request, service, llm_client)
