"""
Zhipu (GLM) Client Configuration

Unified configuration for Zhipu GLM models including API credentials,
model parameters, and client settings.

Uses official zai-sdk for API access.
"""

from typing import Dict, Any, List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class ZhipuConfig(BaseSettings):
    """
    Unified Zhipu configuration.

    Combines environment variable loading (API keys, base URL) with
    runtime-overridable parameters (model, temperature, etc.).
    """

    # API credentials (from environment variables)
    zhipu_api_key: Optional[str] = Field(default=None, description="Zhipu API key")

    # Model selection (from environment variables, runtime overridable)
    model: str = Field(default="glm-4.7", description="Default model")
    secondary_model: str = Field(default="glm-4.7", description="Secondary model for SubAgent")

    # Model parameters (runtime overridable)
    temperature: float = Field(
        default=0.95, description="Sampling temperature (0-1). Do not set both temperature and top_p."
    )
    max_tokens: Optional[int] = Field(default=1024 * 16, description="Maximum tokens to generate")
    top_p: Optional[float] = Field(
        default=None, description="Nucleus sampling threshold. Do not set both temperature and top_p."
    )

    # Client settings (runtime overridable)
    timeout: float = Field(default=60.0, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts")

    def build_api_params(self) -> Dict[str, Any]:
        """
        Convert configuration fields to Zhipu API format.
        """
        params = {
            "model": self.model,
            "temperature": self.temperature,
        }

        if self.max_tokens is not None:
            params["max_tokens"] = self.max_tokens

        if self.top_p is not None:
            params["top_p"] = self.top_p

        return params
