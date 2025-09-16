"""
Settings Management API Routes.

This module handles application settings endpoints including TTS controls
and tool configuration following Clean Architecture principles.
"""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Request
from backend.presentation.models.api_models import (
    UpdateTTSEnabledRequest
)
from backend.domain.services.settings_service import SettingsService
from backend.infrastructure.tts.base import BaseTTS

router = APIRouter(tags=["settings"])


def get_settings_service() -> SettingsService:
    """
    Dependency injection for SettingsService.
    
    Returns:
        SettingsService: Settings management service instance
    """
    return SettingsService()


def get_tts_engine(request: Request) -> BaseTTS:
    """
    Get TTS engine from app state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        BaseTTS: TTS engine instance
    """
    return request.app.state.tts_engine


@router.post("/chat/tts-enabled", response_model=dict)
async def update_tts_enabled(
    request: UpdateTTSEnabledRequest,
    service: SettingsService = Depends(get_settings_service),
    tts_engine: BaseTTS = Depends(get_tts_engine)
) -> Dict[str, Any]:
    """
    Update the TTS (Text-to-Speech) enabled status.
    
    This endpoint:
    1. Updates TTS engine's enabled configuration
    2. Provides real-time TTS control
    3. Affects all subsequent TTS operations
    
    Args:
        request: TTS enabled update request with enabled flag
        
    Returns:
        Dict[str, Any]: Update result with structure:
            - success: bool - Operation success flag
            - tts_enabled: bool - Updated TTS enabled status
    
    Raises:
        HTTPException: 500 if update fails
    """
    try:
        result = await service.update_tts_enabled(
            enabled=request.enabled,
            tts_engine=tts_engine
        )
        
        return result
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update TTS status: {str(e)}"
        )