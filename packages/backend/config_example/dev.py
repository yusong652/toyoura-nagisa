"""
Development configuration settings
Contains settings specific to development environment
"""

import os


class DevelopmentConfig:
    """Development environment configuration settings."""

    def __init__(self):
        # Hot reload configuration (enabled by default for development)
        self.enable_reload: bool = self._get_bool_env(
            "DEV_ENABLE_RELOAD", True)

        # Reload delay in seconds (helps batch multiple file changes)
        self.reload_delay: float = float(os.getenv("DEV_RELOAD_DELAY", "0.5"))

        # Server configuration for development
        self.host: str = os.getenv("DEV_HOST", "0.0.0.0")
        self.port: int = int(os.getenv("DEV_PORT", "8000"))

        # Debug settings
        self.debug_mode: bool = self._get_bool_env("DEV_DEBUG", False)
        self.log_level: str = os.getenv("DEV_LOG_LEVEL", "INFO")

    def _get_bool_env(self, key: str, default: bool) -> bool:
        """Get boolean value from environment variable."""
        value = os.getenv(key, "").lower()
        if value in ("true", "1", "yes", "on"):
            return True
        elif value in ("false", "0", "no", "off"):
            return False
        return default

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return os.getenv("ENVIRONMENT", "development").lower() == "development"
