"""
Configuration system main entry point
Provides unified configuration interface and backward compatibility
"""
from __future__ import annotations
import os
from typing import Dict, Any
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .base import BaseConfig
from .llm import LLMSettings, get_llm_settings
from .tts import TTSSettings, get_tts_settings
from .email import EmailConfig, AuthConfig, SearchConfig, get_email_config, get_auth_config, get_search_config
from .text_to_image import TextToImageSettings, get_text_to_image_settings


class AppSettings(BaseSettings):
    """Application general configuration"""
    
    # Environment configuration
    environment: str = Field(default="development", description="Runtime environment")
    
    # Base configuration
    base: BaseConfig = Field(default_factory=BaseConfig, description="Base configuration")
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        env_prefix='APP_',
        extra='ignore'
    )
    
    def get_llm_settings(self) -> LLMSettings:
        """Get LLM configuration"""
        return LLMSettings()
    
    def get_tts_settings(self) -> TTSSettings:
        """Get TTS configuration"""
        return TTSSettings()
    
    def get_email_config(self) -> EmailConfig:
        """Get email configuration"""
        return EmailConfig()
    
    def get_auth_config(self) -> AuthConfig:
        """Get authentication configuration"""
        return AuthConfig()
    
    def get_search_config(self) -> SearchConfig:
        """Get search configuration"""
        return SearchConfig()
    
    def get_text_to_image_settings(self) -> TextToImageSettings:
        """Get text-to-image configuration"""
        return TextToImageSettings()


# Global configuration instance - recreate each time to ensure latest config
def get_app_settings() -> AppSettings:
    """Get application configuration instance - recreate each time to ensure latest config"""
    return AppSettings()


# -----------------------------------------------------------------------------
# Backward compatibility interface
# -----------------------------------------------------------------------------

# Path configuration
def get_base_config() -> BaseConfig:
    """Get base configuration"""
    return get_app_settings().base


# Base paths
BASE_DIR = Path(__file__).parent.parent
CHAT_DIR = BASE_DIR / "chat"
LOCATION_DB_PATH = BASE_DIR / "location_data"
MEMORY_DB_PATH = BASE_DIR / "memory_db"


# Prompt loading functions
def _load_prompt_file(filename: str) -> str:
    """Load specified prompt file from config/prompts directory"""
    prompt_path = BASE_DIR / "config" / "prompts" / filename
    try:
        return prompt_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def get_base_prompt() -> str:
    """
    Load base system prompt.
    Priority: environment variable `NAGISA_BASE_PROMPT`, then fallback to `base_prompt.md` file.
    """
    base_prompt_from_env = os.getenv("NAGISA_BASE_PROMPT")
    if base_prompt_from_env is not None:
        return base_prompt_from_env.strip()
    
    return _load_prompt_file("base_prompt.md")


def get_expression_prompt() -> str:
    """Load expression/keyword instruction prompt"""
    return _load_prompt_file("expression_prompt.md")


def get_tool_prompt() -> str:
    """Load tool usage guide prompt with workspace root substitution"""
    from backend.infrastructure.mcp.tools.coding.utils.path_security import WORKSPACE_ROOT
    
    prompt = _load_prompt_file("tool_prompt.md")
    if prompt:
        # Replace {workspace_root} placeholder with actual workspace path
        prompt = prompt.replace("{workspace_root}", str(WORKSPACE_ROOT))
    return prompt


def get_system_prompt(agent_profile: str = "general") -> str:
    """
    Get complete system prompt.
    
    DEPRECATED: This is a legacy implementation kept for config example purposes.
    Use backend.shared.utils.prompt.get_system_prompt() for the actual implementation.

    Args:
        agent_profile: Agent profile type ("general", "coding", "lifestyle", "disabled", etc.)
    """
    base = get_base_prompt()
    expression = get_expression_prompt()
    
    components = [base]
    
    # Only include tool prompt if agent profile is not "disabled"
    if agent_profile != "disabled":
        tool_prompt = get_tool_prompt()
        if tool_prompt:
            components.append(tool_prompt)
            
    components.append(expression)

    # Use separator to join all parts, filtering out empty strings
    full_prompt = "\n\n---\n\n".join(filter(None, components))
    return full_prompt




def get_text_to_image_config() -> Dict[str, Any]:
    """Get text-to-image configuration (backward compatibility)"""
    settings = get_app_settings().get_text_to_image_settings()
    
    # Since we now use ComfyUI, get its config directly
    comfyui_config = settings.get_current_config()
    
    config = {
        "provider": "comfyui",  # Now using ComfyUI
        "text_to_image_system_prompt": settings.text_to_image_system_prompt,
        "context_message_count": settings.context_message_count,
        "text_to_image_default_positive_prompt": settings.text_to_image_default_positive_prompt,
        "text_to_image_default_negative_prompt": settings.text_to_image_default_negative_prompt,
        "debug": settings.enable_debug,
        "comfyui": {
            "server_url": comfyui_config.comfyui_server_url,
            "available_samplers": comfyui_config.available_samplers,
            "available_schedulers": comfyui_config.available_schedulers,
            "available_checkpoints": comfyui_config.available_checkpoints,
            "model_type": comfyui_config.model_type,
            "default_seed": comfyui_config.default_seed,
            "client_id": comfyui_config.client_id,
            "return_base64": comfyui_config.return_base64,
            "debug": comfyui_config.debug,
            "model_presets": comfyui_config.model_presets,
        }
    }
    
    return config




# Export configuration getter functions
__all__ = [
    # New configuration system
    "AppSettings",
    "get_app_settings",
    
    # Configuration getter functions
    "get_base_config",
    
    # Prompt functions
    "get_base_prompt",
    "get_expression_prompt", 
    "get_tool_prompt",
    "get_system_prompt",
    
    # Backward compatibility function
    "get_text_to_image_config",
    
    # Path constants
    "BASE_DIR",
    "CHAT_DIR",
    "LOCATION_DB_PATH",
    "MEMORY_DB_PATH",
] 