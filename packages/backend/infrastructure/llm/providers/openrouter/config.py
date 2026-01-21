"""
OpenRouter Client Configuration

Unified configuration for OpenRouter models including API credentials,
model parameters, and client settings.

OpenRouter uses OpenAI-compatible API format with base URL: https://openrouter.ai/api/v1
"""

from typing import Dict, Any, List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    secondary_model: str = Field(
        default="google/gemini-2.0-flash-001",
        description="Secondary model for SubAgent"
    )

    # Model parameters (runtime overridable)
    temperature: float = Field(
        default=0.7,
        description="Sampling temperature (0-1)."
    )
    max_tokens: Optional[int] = Field(
        default=1024*16,
        description="Maximum tokens to generate"
    )
    top_p: Optional[float] = Field(
        default=1.0,
        description="Nucleus sampling threshold."
    )

    # Client settings (runtime overridable)
    debug: bool = Field(default=False, description="Enable debug logging")
    timeout: float = Field(default=60.0, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts")

    model_config = SettingsConfigDict(
        env_file='packages/backend/.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )

    def to_api_params(self) -> Dict[str, Any]:
        """
        Convert model parameters to OpenRouter API format.

        Returns:
            Dict with model, temperature, and optional max_tokens/top_p
        """
        params = {
            'model': self.model,
            'temperature': self.temperature,
            'top_p': self.top_p,
        }

        if self.max_tokens is not None:
            params['max_tokens'] = self.max_tokens

        return params

    def get_api_call_kwargs(
        self,
        *,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = True
    ) -> Dict[str, Any]:
        """
        Build complete kwargs for OpenRouter API call (OpenAI-compatible).

        Args:
            messages: Conversation messages in OpenAI format
            tools: Optional tool schemas in OpenAI format
            stream: Whether to stream the response

        Returns:
            Dict containing all API call parameters
        """
        kwargs: Dict[str, Any] = {
            "messages": messages,
            "stream": stream,
            "timeout": self.timeout,
        }

        kwargs.update(self.to_api_params())

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        return kwargs

    def model_copy(self, **overrides) -> "OpenRouterConfig":
        """
        Create a copy with overrides applied.

        Args:
            **overrides: Fields to override

        Returns:
            New OpenRouterConfig instance with overrides
        """
        config_dict = self.model_dump()
        config_dict.update(overrides)
        return OpenRouterConfig(**config_dict)


def get_openrouter_client_config(**overrides: Any) -> OpenRouterConfig:
    """
    Get OpenRouter client configuration with optional overrides.

    Args:
        **overrides: Configuration overrides. Supports direct field overrides
                    or nested model_settings overrides.

    Returns:
        OpenRouterConfig instance
    """
    # Start with base config from environment
    try:
        base_config = OpenRouterConfig()
    except Exception:
        # If env loading fails, use defaults
        base_config = OpenRouterConfig(
            openrouter_api_key="",
            model="qwen/qwen3-235b-a22b-2507"
        )

    # Handle nested model_settings overrides for backward compatibility
    if 'model_settings' in overrides:
        model_settings = overrides.pop('model_settings')
        if isinstance(model_settings, dict):
            overrides.update(model_settings)

    # Apply overrides
    if overrides:
        return base_config.model_copy(**overrides)

    return base_config
