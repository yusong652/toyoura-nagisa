"""
Zhipu (智谱) Client Configuration

Unified configuration for Zhipu GLM models including API credentials,
model parameters, and client settings.

Uses official zai-sdk for API access.
"""

from typing import Dict, Any, List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    debug: bool = Field(default=False, description="Enable debug logging")
    timeout: float = Field(default=60.0, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts")

    model_config = SettingsConfigDict(
        env_file=".env", env_nested_delimiter="__", case_sensitive=False, env_prefix="", extra="ignore"
    )

    def to_api_params(self) -> Dict[str, Any]:
        """
        Convert model parameters to Zhipu API format.

        Returns:
            Dict with model, temperature, and optional max_tokens/top_p
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

    def get_api_call_kwargs(
        self, *, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None, stream: bool = True
    ) -> Dict[str, Any]:
        """
        Build complete kwargs for Zhipu API call (OpenAI-compatible).

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

    def model_copy(self, **overrides) -> "ZhipuConfig":
        """
        Create a copy with overrides applied.

        Args:
            **overrides: Fields to override

        Returns:
            New ZhipuConfig instance with overrides
        """
        config_dict = self.model_dump()
        config_dict.update(overrides)
        return ZhipuConfig(**config_dict)


def get_zhipu_client_config(**overrides: Any) -> ZhipuConfig:
    """
    Get Zhipu client configuration with optional overrides.

    This function provides backward compatibility and a convenient way
    to create ZhipuConfig with overrides.

    Args:
        **overrides: Configuration overrides. Supports:
            - Direct field overrides: model, temperature, debug, etc.
            - Nested overrides: model_settings={'temperature': 0.8}

    Returns:
        ZhipuConfig instance

    Example:
        >>> config = get_zhipu_client_config(
        ...     model='glm-4.7',
        ...     temperature=0.8,
        ...     debug=True
        ... )
    """
    # Start with base config from environment
    try:
        base_config = ZhipuConfig()
    except Exception:
        # If env loading fails, use defaults
        base_config = ZhipuConfig(zhipu_api_key="", model="glm-4.7")

    # Handle nested model_settings overrides for backward compatibility
    if "model_settings" in overrides:
        model_settings = overrides.pop("model_settings")
        if isinstance(model_settings, dict):
            overrides.update(model_settings)

    # Apply overrides
    if overrides:
        return base_config.model_copy(**overrides)

    return base_config
