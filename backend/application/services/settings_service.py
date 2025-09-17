"""
Settings Service - Business logic for application settings management.

This service handles configuration changes for TTS, tools, and other
application-level settings.
"""
from typing import Dict, Any


def get_settings_service() -> "SettingsService":
    """
    Dependency injection factory for SettingsService.

    Returns:
        SettingsService: Settings management service instance
    """
    return SettingsService()


class SettingsService:
    """
    Service layer for application settings management.
    
    Provides high-level operations for configuring application settings
    including TTS controls and tool management.
    """
    
    async def update_tts_enabled(
        self,
        enabled: bool
    ) -> Dict[str, Any]:
        """
        Update the TTS (Text-to-Speech) enabled status.

        This operation:
        1. Updates TTS engine's enabled configuration
        2. Affects all subsequent TTS operations
        3. Provides immediate feedback

        Args:
            enabled: Whether to enable or disable TTS

        Returns:
            Dict[str, Any]: Update result:
                - success: bool - Operation success flag
                - tts_enabled: bool - Updated TTS enabled status
        """
        print(f"[DEBUG] Updating TTS enabled status to: {enabled} (type: {type(enabled)})")

        # Get TTS engine from app state
        from backend.shared.utils.app_context import get_tts_engine
        tts_engine = get_tts_engine()

        # Update TTS engine configuration
        tts_engine.enabled = enabled
        
        return {
            "success": True,
            "tts_enabled": enabled
        }