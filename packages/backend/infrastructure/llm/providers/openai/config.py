"""
OpenAI Client Configuration

Unified configuration for OpenAI GPT models including API credentials,
model parameters, and client settings.
"""

from typing import Dict, Any, List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OpenAIConfig(BaseSettings):
    """
    Unified OpenAI configuration.

    Combines environment variable loading (API keys) with
    runtime-overridable parameters (model, temperature, etc.).

    Available Models:
    - gpt-5-mini-2025-08-07: Latest GPT-5 Mini (recommended for most tasks)
    - gpt-5-2025-08-07: GPT-5 full model
    - gpt-4o: GPT-4 Omni with vision
    - o1, o3: Reasoning models
    """

    # API credentials (from environment variables)
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")

    # Model selection (from environment variables, runtime overridable)
    model: str = Field(
        default="gpt-5-mini-2025-08-07",
        description="Default model"
    )
    secondary_model: str = Field(
        default="gpt-5-mini-2025-08-07",
        description="Secondary model for SubAgent"
    )

    # Model parameters (runtime overridable)
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature. Do not set both temperature and top_p."
    )
    max_tokens: Optional[int] = Field(
        default=1024*16,
        description="Maximum tokens to generate"
    )
    top_p: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling threshold. Do not set both temperature and top_p."
    )
    frequency_penalty: float = Field(
        default=0.0,
        ge=-2.0,
        le=2.0,
        description="Frequency penalty"
    )
    presence_penalty: float = Field(
        default=0.0,
        ge=-2.0,
        le=2.0,
        description="Presence penalty"
    )

    # Reasoning configuration (for reasoning models like o1, o3, gpt-5)
    reasoning_effort: Optional[str] = Field(
        default=None,
        description="Reasoning effort: minimal, medium, high (for reasoning models)"
    )

    # Client settings (runtime overridable)
    debug: bool = Field(
        default=False,
        description="Enable debug logging"
    )
    timeout: float = Field(
        default=120.0,
        description="Request timeout in seconds"
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of retries for failed requests"
    )

    model_config = SettingsConfigDict(
        env_file='packages/backend/.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )

    def to_api_params(self) -> Dict[str, Any]:
        """
        Convert model parameters to OpenAI API format.

        Note: Responses API ignores frequency/presence penalties for compatibility.

        Returns:
            Dict with model, temperature, top_p, and optional max_tokens
        """
        params = {
            'model': self.model,
            'temperature': self.temperature,
        }

        # Only include top_p if explicitly set
        if self.top_p is not None:
            params['top_p'] = self.top_p

        if self.max_tokens is not None:
            params['max_output_tokens'] = self.max_tokens

        return params

    def get_api_call_kwargs(
        self,
        *,
        instructions: Optional[str],
        input_items: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Build complete kwargs for OpenAI Responses API call.

        Args:
            instructions: System instructions to provide via Responses API
            input_items: Conversation items formatted for Responses API
            tools: Optional tool schemas in Responses API format

        Returns:
            Dict containing all API call parameters
        """
        kwargs: Dict[str, Any] = {
            "input": input_items,
            "timeout": self.timeout,
        }

        kwargs.update(self.to_api_params())

        if instructions:
            kwargs["instructions"] = instructions

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        # Add reasoning configuration for reasoning models (gpt-5, o1, o3 series)
        if self.reasoning_effort:
            kwargs["reasoning"] = {
                "effort": self.reasoning_effort
            }

        return kwargs

    def model_copy(self, **overrides) -> "OpenAIConfig":
        """
        Create a copy with overrides applied.

        Args:
            **overrides: Fields to override

        Returns:
            New OpenAIConfig instance with overrides
        """
        config_dict = self.model_dump()
        config_dict.update(overrides)
        return OpenAIConfig(**config_dict)


def get_openai_client_config(**overrides: Any) -> OpenAIConfig:
    """
    Get OpenAI client configuration with optional overrides.

    This function provides backward compatibility and a convenient way
    to create OpenAIConfig with overrides.

    Args:
        **overrides: Configuration overrides. Supports:
            - Direct field overrides: model, temperature, debug, etc.
            - Nested overrides: model_settings={'temperature': 0.8}

    Returns:
        OpenAIConfig instance

    Example:
        >>> config = get_openai_client_config(
        ...     model='gpt-5-2025-08-07',
        ...     temperature=0.8,
        ...     debug=True
        ... )
    """
    # Start with base config from environment
    try:
        base_config = OpenAIConfig()
    except Exception:
        # If env loading fails, use defaults
        base_config = OpenAIConfig(
            openai_api_key=None,
            model="gpt-5-mini-2025-08-07"
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
