"""
Configuration system main entry point
Provides unified configuration interface
"""
from __future__ import annotations
from pathlib import Path

from .llm import LLMSettings
from .tts import TTSSettings
from .email import EmailConfig, AuthConfig, SearchConfig
from .text_to_image import TextToImageSettings
from .image_to_video import ImageToVideoSettings
from .memory import MemoryConfig
from .dev import DevelopmentConfig

# Base path configuration
BASE_DIR = Path(__file__).parent.parent
CHAT_DIR = BASE_DIR / "chat"
TOOL_DB_PATH = BASE_DIR / "tool_db"
LOCATION_DB_PATH = BASE_DIR / "location_data"
PROMPTS_DIR = BASE_DIR / "config" / "prompts"

# Configuration instances (singleton pattern)
_llm_settings = None
_tts_settings = None
_email_config = None
_auth_config = None
_search_config = None
_text_to_image_settings = None
_image_to_video_settings = None
_memory_config = None
_dev_config = None

def get_llm_settings() -> LLMSettings:
    """Get LLM configuration"""
    global _llm_settings
    if _llm_settings is None:
        _llm_settings = LLMSettings()
    return _llm_settings

def get_tts_settings() -> TTSSettings:
    """Get TTS configuration"""
    global _tts_settings
    if _tts_settings is None:
        _tts_settings = TTSSettings()
    return _tts_settings

def get_email_config() -> EmailConfig:
    """Get email configuration"""
    global _email_config
    if _email_config is None:
        _email_config = EmailConfig()
    return _email_config

def get_auth_config() -> AuthConfig:
    """Get authentication configuration"""
    global _auth_config
    if _auth_config is None:
        _auth_config = AuthConfig()
    return _auth_config

def get_search_config() -> SearchConfig:
    """Get search configuration"""
    global _search_config
    if _search_config is None:
        _search_config = SearchConfig()
    return _search_config

def get_text_to_image_settings() -> TextToImageSettings:
    """Get text-to-image configuration"""
    global _text_to_image_settings
    if _text_to_image_settings is None:
        _text_to_image_settings = TextToImageSettings()
    return _text_to_image_settings

def get_image_to_video_settings() -> ImageToVideoSettings:
    """Get image-to-video configuration"""
    global _image_to_video_settings
    if _image_to_video_settings is None:
        _image_to_video_settings = ImageToVideoSettings()
    return _image_to_video_settings

def get_memory_config() -> MemoryConfig:
    """Get memory system configuration"""
    global _memory_config
    if _memory_config is None:
        _memory_config = MemoryConfig()
    return _memory_config

def get_dev_config() -> DevelopmentConfig:
    """Get development configuration"""
    global _dev_config
    if _dev_config is None:
        _dev_config = DevelopmentConfig()
    return _dev_config

# Prompt loading functions - DEPRECATED: Redirects to prompt_builder.py for backward compatibility
# These functions are maintained only for backward compatibility.
# New code should use backend.shared.utils.prompt_builder directly.

def get_base_prompt() -> str:
    """
    DEPRECATED: Use backend.shared.utils.prompt.get_base_prompt() instead.
    Load base system prompt.
    """
    from backend.shared.utils.prompt import get_base_prompt as _get_base_prompt
    return _get_base_prompt()

def get_expression_prompt() -> str:
    """
    DEPRECATED: Use backend.shared.utils.prompt.get_expression_prompt() instead.
    Load expression/keyword instruction prompt.
    """
    from backend.shared.utils.prompt import get_expression_prompt as _get_expression_prompt
    return _get_expression_prompt()

def get_tool_prompt() -> str:
    """
    DEPRECATED: Use backend.shared.utils.prompt.get_tool_prompt() instead.
    Load tool usage guide prompt with workspace root substitution.
    """
    from backend.shared.utils.prompt import get_tool_prompt as _get_tool_prompt
    return _get_tool_prompt()

def get_system_prompt(tools_enabled: bool = True) -> str:
    """
    DEPRECATED: Use backend.shared.utils.prompt.get_system_prompt() instead.
    Get complete system prompt.
    """
    from backend.shared.utils.prompt import get_system_prompt as _get_system_prompt
    return _get_system_prompt(tools_enabled=tools_enabled)


# Export main interfaces
__all__ = [
    # Configuration getter functions
    "get_llm_settings",
    "get_tts_settings",
    "get_email_config",
    "get_auth_config",
    "get_search_config",
    "get_text_to_image_settings",
    "get_image_to_video_settings",
    "get_memory_config",
    "get_dev_config",
    
    # Prompt functions
    "get_base_prompt",
    "get_expression_prompt", 
    "get_tool_prompt",
    "get_system_prompt",
    
    # Path constants
    "BASE_DIR",
    "CHAT_DIR",
    "TOOL_DB_PATH",
    "LOCATION_DB_PATH", 
    "PROMPTS_DIR",
]