"""
OpenRouter Client Configuration

Unified configuration for OpenRouter models including API credentials,
model parameters, and client settings.

OpenRouter uses OpenAI-compatible API format with base URL: https://openrouter.ai/api/v1
"""

from typing import Dict, Any, List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class OpenRouterConfig(BaseSettings):
    """
    Unified OpenRouter configuration.

    Combines environment variable loading (API keys, base URL) with
    runtime-overridable parameters (model, temperature, etc.).
    """

    # API credentials (from environment variables)
    openrouter_api_key: Optional[str] = Field(default=None, description="OpenRouter API key")
    base_url: str = Field(default="https://openrouter.ai/api/v1", description="API base URL")

    # Model selection (from environment variables, runtime overridable)
    model: str = Field(default="qwen/qwen3-235b-a22b-2507", description="Default model")
    secondary_model: str = Field(default="google/gemini-2.0-flash-001", description="Secondary model for SubAgent")

    # Model parameters (runtime overridable)
    temperature: float = Field(default=0.7, description="Sampling temperature (0-1).")
    max_tokens: Optional[int] = Field(default=1024 * 16, description="Maximum tokens to generate")
    top_p: Optional[float] = Field(default=None, description="Nucleus sampling threshold.")

    # Client settings (runtime overridable)
    timeout: float = Field(default=60.0, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts")

    def build_api_params(self) -> Dict[str, Any]:
        """
        Convert configuration fields to OpenRouter API format.
        """
        params: Dict[str, Any] = {
            "model": self.model,
            "temperature": self.temperature,
        }

        if self.max_tokens is not None:
            params["max_tokens"] = self.max_tokens

        if self.top_p is not None:
            params["top_p"] = self.top_p

        return params
