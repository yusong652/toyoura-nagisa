"""
PFC (Particle Flow Code) Configuration Module

Minimal configuration for PFC integration:
- Optional PFC installation path (for environment display)
- Optional fallback workspace directory
"""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PFCSettings(BaseSettings):
    """PFC integration settings."""

    # Optional PFC installation path (used for env info display only)
    pfc_path: Optional[Path] = Field(
        default=None,
        description="Optional PFC installation directory",
        validation_alias="PFC_PATH",
    )

    # Optional fallback workspace when runtime workspace cannot be inferred
    workspace: Optional[Path] = Field(
        default=None,
        description="Optional fallback PFC workspace directory",
        validation_alias="PFC_WORKSPACE",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        case_sensitive=False,
        env_prefix="",
        populate_by_name=True,
        extra="ignore",
    )


# Global PFC settings instance
_pfc_settings: Optional[PFCSettings] = None


def get_pfc_settings() -> PFCSettings:
    """Get PFC settings instance (singleton)"""
    global _pfc_settings
    if _pfc_settings is None:
        _pfc_settings = PFCSettings()
    return _pfc_settings


def get_pfc_workspace() -> Optional[Path]:
    """
    Get configured PFC workspace path.

    Returns:
        Path if configured and exists, None otherwise
    """
    settings = get_pfc_settings()
    if settings.workspace and settings.workspace.exists():
        return settings.workspace
    return None
