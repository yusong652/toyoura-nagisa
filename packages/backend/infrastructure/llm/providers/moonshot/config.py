"""
Moonshot (Moonshot) Client Configuration

Unified configuration for Moonshot models including API credentials,
model parameters, and client settings.

Moonshot uses OpenAI-compatible API format with base URL: https://api.moonshot.ai/v1
"""

from typing import Dict, Any, List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class MoonshotConfig(BaseSettings):
    """
    Unified Moonshot configuration.

    Combines environment variable loading (API keys, base URL) with
    runtime-overridable parameters (model, temperature, etc.).
    """

    # API credentials (from environment variables)
    moonshot_api_key: Optional[str] = Field(default=None, description="Moonshot API key")
    base_url: str = Field(default="https://api.moonshot.ai/v1", description="API base URL")

    # Model selection (from environment variables, runtime overridable)
    model: str = Field(default="kimi-k2.5", description="Default model")
    secondary_model: str = Field(default="kimi-k2-0905-preview", description="Secondary model for SubAgent")

    # Client settings (runtime overridable)
    timeout: float = Field(default=60.0, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts")

    def build_api_params(self) -> Dict[str, Any]:
        """
        Convert configuration fields to Moonshot API format.
        """
        params: Dict[str, Any] = {
            "model": self.model,
        }

        return params
