"""
Configuration system main entry point
Provides unified configuration interface and backward compatibility
"""
from __future__ import annotations
import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# BaseConfig removed - not used in actual configuration
from .llm import LLMSettings, get_llm_settings
from .dev import DevelopmentConfig


class AppSettings(BaseSettings):
    """Application general configuration"""
    
    # Environment configuration
    environment: str = Field(default="development", description="Runtime environment")
    
    # Base configuration removed - not needed in actual configuration
    
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
    

# Global configuration instance - recreate each time to ensure latest config
def get_app_settings() -> AppSettings:
    """Get application configuration instance - recreate each time to ensure latest config"""
    return AppSettings()


def get_dev_config() -> DevelopmentConfig:
    """Get development configuration instance"""
    return DevelopmentConfig()


# -----------------------------------------------------------------------------
# Backward compatibility interface
# -----------------------------------------------------------------------------

# Path configuration - BaseConfig removed, using direct path constants instead


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


def get_system_prompt(agent_profile = "pfc_expert") -> str:
    """
    Get complete system prompt.
    
    DEPRECATED: This is a legacy implementation kept for config example purposes.
    Use backend.shared.utils.prompt.get_system_prompt() for the actual implementation.

    Args:
        agent_profile: Agent profile type ("pfc_expert", "disabled")
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




# Export configuration getter functions
__all__ = [
    # New configuration system
    "AppSettings",
    "get_app_settings",

    # Development configuration
    "DevelopmentConfig",
    "get_dev_config",

    # Prompt functions
    "get_base_prompt",
    "get_expression_prompt",
    "get_tool_prompt",
    "get_system_prompt",

    # Path constants
    "BASE_DIR",
    "CHAT_DIR",
    "LOCATION_DB_PATH",
    "MEMORY_DB_PATH",
] 
