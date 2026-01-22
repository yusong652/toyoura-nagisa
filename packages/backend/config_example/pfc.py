"""
PFC (Particle Flow Code) Configuration Module

Configuration for PFC integration including:
- PFC installation path
- PFC workspace directory (used when PFC server not connected)
"""

from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PFCSettings(BaseSettings):
    """PFC Integration Settings"""

    # PFC Installation Path
    pfc_path: Path = Field(
        default=Path("C:/Program Files/Itasca/PFC700"),
        description="PFC installation directory (contains exe64/)",
        validation_alias="PFC_PATH",
    )

    # PFC Workspace Directory
    # This is the working directory for PFC operations when PFC server is not connected.
    # When PFC server IS connected, workspace is automatically synced from PFC's os.getcwd().
    # Set this to your primary PFC project directory.
    workspace: Optional[Path] = Field(
        default=None,
        description="PFC workspace directory (fallback when PFC server not connected)",
        validation_alias="PFC_WORKSPACE",
    )

    # PFC Server Connection Control
    # Set to False to disable all attempts to connect to PFC server (e.g. for pure development/testing)
    # This avoids timeouts and retries when you know PFC server is not running.
    server_enabled: bool = Field(
        default=True,
        description="Enable/disable PFC server connection attempts",
        validation_alias="PFC_SERVER_ENABLED",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        case_sensitive=False,
        env_prefix="",
        populate_by_name=True,
        extra="ignore",
    )

    @field_validator("pfc_path", "workspace", mode="before")
    @classmethod
    def convert_to_path(cls, v):
        """Convert string to Path if needed"""
        if v is None:
            return None
        if isinstance(v, str):
            return Path(v)
        return v

    @property
    def pfc_executable(self) -> Path:
        """Get PFC GUI executable path"""
        # Try common PFC versions
        exe_patterns = [
            self.pfc_path / "exe64" / "pfc3d700_gui.exe",  # PFC 7.0
            self.pfc_path / "exe64" / "pfc3d600_gui.exe",  # PFC 6.0
        ]
        for exe in exe_patterns:
            if exe.exists():
                return exe
        # Return default (may not exist)
        return self.pfc_path / "exe64" / "pfc3d700_gui.exe"

    @property
    def pfc_python(self) -> Path:
        """Get PFC embedded Python executable path"""
        return self.pfc_path / "exe64" / "python36" / "python.exe"

    def validate_pfc_installation(self) -> bool:
        """Check if PFC is installed at the configured path"""
        return self.pfc_executable.exists()

    def validate_workspace(self) -> bool:
        """Check if workspace directory exists"""
        if self.workspace is None:
            return False
        return self.workspace.exists()


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
