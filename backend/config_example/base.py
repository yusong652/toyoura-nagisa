"""
Base Configuration Module
Contains path configurations, debug settings, and other common configuration items
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent
CHAT_DIR = PROJECT_ROOT / "chat"


class BaseConfig(BaseSettings):
    """Base Configuration Class"""
    
    # Path configuration
    base_dir: Path = Field(default=PROJECT_ROOT, description="Project root directory")
    chat_dir: Path = Field(default=CHAT_DIR, description="Chat-related files directory")
    tool_db_path: Path = Field(default=PROJECT_ROOT / "tool_db", description="Tool database path")
    location_db_path: Path = Field(default=PROJECT_ROOT / "location_data", description="Location database path")
    memory_db_path: Path = Field(default=PROJECT_ROOT / "memory_db", description="Memory database path")
    
    # Debug configuration
    debug: bool = Field(default=False, description="Global debug switch")
    
    # Prompt configuration
    base_prompt_env_key: str = Field(default="NAGISA_BASE_PROMPT", description="Base prompt environment variable key")
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        env_prefix='APP_',
        extra='ignore'
    )
    
    def __init__(self, **data):
        super().__init__(**data)
        # Ensure necessary directories exist
        self.tool_db_path.mkdir(parents=True, exist_ok=True)
        self.location_db_path.mkdir(parents=True, exist_ok=True)
        self.memory_db_path.mkdir(parents=True, exist_ok=True) 