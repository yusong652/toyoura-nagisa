"""
OpenRouter Client Configuration

Handles configuration settings for OpenRouter models including
model parameters, API settings, and debug options.

OpenRouter uses OpenAI-compatible API format with base URL: https://openrouter.ai/api/v1
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from backend.config import get_llm_settings


class OpenRouterConfig(BaseSettings):
    """OpenRouter configuration loaded from environment variables."""

    openrouter_api_key: str = Field(description="OpenRouter API key")
    model: str = Field(default="qwen/qwen3-235b-a22b-2507", description="Default model")
    secondary_model: str = Field(
        default="google/gemini-2.5-flash",
        description="Secondary model for SubAgent"
    )
    embedding_model: str = Field(
        default="google/gemini-embedding-001",
        description="Embedding model name"
    )

    model_config = SettingsConfigDict(
        env_file='packages/backend/.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )


@dataclass
class OpenRouterModelSettings:
    """OpenRouter model-specific settings"""
    model: str = "anthropic/claude-sonnet-4-5"  # Default model
    temperature: Union[float, str] = 0.7
    max_tokens: Optional[Union[int, str]] = 1024*16
    top_p: Union[float, str] = 1.0

    # OpenRouter supports any model in their catalog:
    # - anthropic/claude-sonnet-4-5
    # - google/gemini-2.5-pro
    # - meta-llama/llama-3.3-70b-instruct
    # - moonshotai/kimi-k2-0905
    # - deepseek/deepseek-chat
    # See: https://openrouter.ai/models

    def to_api_params(self) -> Dict[str, Any]:
        """Convert to OpenRouter API parameters (OpenAI-compatible format)"""
        params = {
            'model': self.model,
            'temperature': self.temperature,
            'top_p': self.top_p
        }

        if self.max_tokens is not None:
            params['max_tokens'] = self.max_tokens

        return params


@dataclass
class OpenRouterClientConfig:
    """Complete OpenRouter client configuration"""
    model_settings: OpenRouterModelSettings = field(default_factory=OpenRouterModelSettings)
    api_key: Optional[str] = None
    base_url: str = "https://openrouter.ai/api/v1"  # Fixed for OpenRouter
    debug: bool = False
    timeout: float = 60.0
    max_retries: int = 3

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
            messages: Conversation messages in OpenAI format.
            tools: Optional tool schemas in OpenAI format.
            stream: Whether to stream the response.

        Returns:
            Dict containing all API call parameters.
        """
        kwargs: Dict[str, Any] = {
            "messages": messages,
            "stream": stream,
            "timeout": self.timeout,
        }

        kwargs.update(self.model_settings.to_api_params())

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        return kwargs


def get_openrouter_client_config(**overrides: Any) -> OpenRouterClientConfig:
    """
    Get OpenRouter client configuration with optional overrides

    Args:
        **overrides: Configuration overrides

    Returns:
        OpenRouterClientConfig instance
    """
    # Get base settings from global config
    llm_settings = get_llm_settings()

    # Try to get OpenRouter config from settings
    try:
        openrouter_config = llm_settings.get_openrouter_config()
        model = openrouter_config.model
        api_key = openrouter_config.openrouter_api_key
    except (AttributeError, KeyError):
        # Fallback to defaults if config not available
        model = "anthropic/claude-sonnet-4-5"
        api_key = None

    model_settings = OpenRouterModelSettings()
    model_settings.model = model

    model_overrides = overrides.get('model_settings')
    if isinstance(model_overrides, dict):
        for key, value in model_overrides.items():
            setattr(model_settings, key, value)

    # Build client config
    config_dict: Dict[str, Any] = {
        'model_settings': model_settings,
        'api_key': overrides.get('api_key', api_key),
        'base_url': "https://openrouter.ai/api/v1",  # Always use OpenRouter
        'debug': overrides.get('debug', llm_settings.debug),
        'timeout': overrides.get('timeout', 60.0),
        'max_retries': overrides.get('max_retries', 3)
    }

    return OpenRouterClientConfig(**config_dict)
