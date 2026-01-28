"""
Anthropic Client Configuration

Unified configuration for Anthropic Claude models including API credentials,
model parameters, and client settings.
"""

from typing import List, Dict, Any, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class AnthropicConfig(BaseSettings):
    """
    Unified Anthropic configuration.

    Combines environment variable loading (API keys) with
    runtime-overridable parameters (model, temperature, etc.).
    """

    # API credentials (from environment variables)
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key")

    # Model selection (from environment variables, runtime overridable)
    model: str = Field(default="claude-sonnet-4-5-20250929", description="Default model")
    secondary_model: str = Field(default="claude-haiku-4-5-20251001", description="Secondary model for SubAgent")

    # Model parameters (runtime overridable)
    max_tokens: int = Field(default=1024 * 16, ge=1, le=128000, description="Maximum number of tokens to generate")
    temperature: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Sampling temperature. Do not set both temperature and top_p."
    )
    top_p: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Nucleus sampling parameter. Do not set both temperature and top_p."
    )
    top_k: Optional[int] = Field(default=None, ge=1, description="Top-K sampling parameter")

    # Thinking configuration (for models that support thinking)
    enable_thinking: bool = Field(default=True, description="Whether to enable thinking for supported models")
    thinking_budget_tokens: int = Field(
        default=4096, ge=1000, le=100000, description="Budget tokens for thinking process"
    )

    # API settings
    api_version: str = Field(default="2023-06-01", description="Anthropic API version")
    timeout: int = Field(default=60, ge=1, description="Request timeout in seconds")
    max_retries: int = Field(default=3, ge=0, description="Maximum number of retries for failed requests")

    # Tool settings
    tools_enabled: bool = Field(default=True, description="Enable tool calling functionality")
    tool_timeout: int = Field(default=30, ge=1, description="Tool execution timeout in seconds")

    # Log settings
    log_requests: bool = Field(default=False, description="Log API requests and responses")

    def build_api_params(self) -> Dict[str, Any]:
        """
        Convert configuration fields to Anthropic API parameters.
        """
        params: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
        }

        if self.temperature is not None:
            params["temperature"] = self.temperature
        if self.top_p is not None:
            params["top_p"] = self.top_p
        if self.top_k is not None:
            params["top_k"] = self.top_k

        return params
