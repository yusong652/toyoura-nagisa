"""
OpenRouter Client Configuration

Handles configuration settings for OpenRouter models including
model parameters, API settings, and debug options.

OpenRouter uses OpenAI-compatible API format with base URL: https://openrouter.ai/api/v1
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from backend.config import get_llm_settings


@dataclass
class OpenRouterModelSettings:
    """OpenRouter model-specific settings"""
    model: str = "anthropic/claude-sonnet-4-5"  # Default model
    temperature: float = 0.7
    max_tokens: Optional[int] = 1024*16
    top_p: float = 1.0

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

    # OpenRouter required headers
    openrouter_headers: Optional[Dict[str, str]] = None

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


def get_openrouter_client_config(**overrides) -> OpenRouterClientConfig:
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

        # Build OpenRouter headers
        openrouter_headers = {
            "HTTP-Referer": openrouter_config.openrouter_http_referer,
            "X-Title": openrouter_config.openrouter_title,
        }
    except (AttributeError, KeyError):
        # Fallback to defaults if config not available
        model = "anthropic/claude-sonnet-4-5"
        api_key = None
        openrouter_headers = {
            "HTTP-Referer": "https://github.com/yusong652/toyoura-nagisa",
            "X-Title": "toyoura-nagisa",
        }

    # Build model settings
    model_settings_dict = {
        'model': model,
    }

    # Apply overrides to model settings
    if 'model_settings' in overrides:
        model_settings_dict.update(overrides['model_settings'])

    model_settings = OpenRouterModelSettings(**model_settings_dict)

    # Build client config
    config_dict = {
        'model_settings': model_settings,
        'api_key': overrides.get('api_key', api_key),
        'base_url': "https://openrouter.ai/api/v1",  # Always use OpenRouter
        'openrouter_headers': openrouter_headers,
        'debug': overrides.get('debug', llm_settings.debug),
        'timeout': overrides.get('timeout', 60.0),
        'max_retries': overrides.get('max_retries', 3)
    }

    return OpenRouterClientConfig(**config_dict)
