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

    Available Models:
    - glm-4.7: Latest GLM-4 model with improved capabilities
    - glm-4.6: GLM-4 Plus model
    - glm-4-plus, glm-4-0520, glm-4, glm-4-air, glm-4-airx, glm-4-flash
    - glm-4-long: Supports up to 1M tokens context
    """

    # API credentials (from environment variables)
    zhipu_api_key: str = Field(description="Zhipu API key")
    base_url: str = Field(
        default="https://open.bigmodel.cn/api/paas/v4/",
        description="Zhipu API base URL"
    )

    # Model selection (from environment variables, runtime overridable)
    model: str = Field(default="glm-4.7", description="Default model")
    secondary_model: str = Field(
        default="glm-4.7",
        description="Secondary model for SubAgent"
    )

    # Model parameters (runtime overridable)
    temperature: float = Field(
        default=0.95,
        description="Sampling temperature (0-1)"
    )
    max_tokens: Optional[int] = Field(
        default=1024*16,
        description="Maximum tokens to generate"
    )
    top_p: float = Field(
        default=0.7,
        description="Nucleus sampling threshold"
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
        Convert model parameters to Zhipu API format.

        Returns:
            Dict with model, temperature, top_p, and optional max_tokens
        """
        params = {
            'model': self.model,
            'temperature': self.temperature,
            'top_p': self.top_p
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
        ...     model='glm-4-plus',
        ...     temperature=0.8,
        ...     debug=True
        ... )
    """
    # Start with base config from environment
    try:
        base_config = ZhipuConfig()
    except Exception:
        # If env loading fails, use defaults
        base_config = ZhipuConfig(
            zhipu_api_key="",
            model="glm-4.7"
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
