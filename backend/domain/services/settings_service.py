"""
Settings Service - Business logic for application settings management.

This service handles configuration changes for TTS, tools, and other
application-level settings.
"""
from typing import Dict, Any


class SettingsService:
    """
    Service layer for application settings management.
    
    Provides high-level operations for configuring application settings
    including TTS controls and tool management.
    """
    
    async def update_tools_enabled(
        self,
        enabled: bool,
        llm_client: Any
    ) -> Dict[str, Any]:
        """
        Update the tools enabled status for LLM client.
        
        This operation:
        1. Updates LLM client's tools_enabled configuration
        2. Synchronizes with Agent Profile system for consistency
        3. Provides deprecation notice for migration to new system
        
        Args:
            enabled: Whether to enable or disable tools
            llm_client: LLM client instance to configure
            
        Returns:
            Dict[str, Any]: Update result:
                - success: bool - Operation success flag
                - tools_enabled: bool - Updated tools enabled status
                - message: str - Deprecation notice and migration guidance
        """
        print(f"[DEBUG] Updating tools enabled status to: {enabled} (type: {type(enabled)})")
        print(f"[DEPRECATED] This endpoint is deprecated, recommend using /api/agent/profile")
        
        # Update LLM client configuration
        llm_client.update_config(tools_enabled=enabled)
        
        # agent_profile is now stateless - no global state to synchronize
        
        return {
            "success": True,
            "tools_enabled": enabled,
            "message": "Tools enabled/disabled successfully. Use agent_profile in chat requests for granular tool control."
        }
    
    async def update_tts_enabled(
        self,
        enabled: bool,
        tts_engine: Any
    ) -> Dict[str, Any]:
        """
        Update the TTS (Text-to-Speech) enabled status.
        
        This operation:
        1. Updates TTS engine's enabled configuration
        2. Affects all subsequent TTS operations
        3. Provides immediate feedback
        
        Args:
            enabled: Whether to enable or disable TTS
            tts_engine: TTS engine instance to configure
            
        Returns:
            Dict[str, Any]: Update result:
                - success: bool - Operation success flag  
                - tts_enabled: bool - Updated TTS enabled status
        """
        print(f"[DEBUG] Updating TTS enabled status to: {enabled} (type: {type(enabled)})")
        
        # Update TTS engine configuration
        tts_engine.enabled = enabled
        
        return {
            "success": True,
            "tts_enabled": enabled
        }