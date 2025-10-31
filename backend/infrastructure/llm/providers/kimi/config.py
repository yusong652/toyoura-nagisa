"""
Kimi (Moonshot) Client Configuration

Handles configuration settings for Kimi/Moonshot models including
model parameters, API settings, and debug options.

Kimi uses OpenAI-compatible API format with base URL: https://api.moonshot.cn/v1
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from backend.config import get_llm_settings


@dataclass
class KimiModelSettings:
    """Kimi model-specific settings"""
    model: str = "moonshot-v1-32k"  # Default to 32k context model
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: float = 1.0

    # Kimi-specific features
    # Models: moonshot-v1-8k, moonshot-v1-32k, moonshot-v1-128k
    # Note: Kimi excels at long-context understanding (up to 200K tokens)

    def to_api_params(self) -> Dict[str, Any]:
        """Convert to Kimi API parameters (OpenAI-compatible format)"""
        params = {
            'model': self.model,
            'temperature': self.temperature,
            'top_p': self.top_p
        }

        if self.max_tokens is not None:
            params['max_tokens'] = self.max_tokens

        return params


@dataclass
class KimiClientConfig:
    """Complete Kimi client configuration"""
    model_settings: KimiModelSettings = field(default_factory=KimiModelSettings)
    api_key: Optional[str] = None
    base_url: str = "https://api.moonshot.cn/v1"
    debug: bool = False
    timeout: float = 60.0  # Longer timeout for long-context processing
    max_retries: int = 3

    def get_api_call_kwargs(
        self,
        *,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = True
    ) -> Dict[str, Any]:
        """
        Build complete kwargs for Kimi API call (OpenAI-compatible).

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


def get_kimi_client_config(**overrides) -> KimiClientConfig:
    """
    Get Kimi client configuration with optional overrides

    Args:
        **overrides: Configuration overrides

    Returns:
        KimiClientConfig instance
    """
    # Get base settings from global config
    llm_settings = get_llm_settings()

    # Check if there's a kimi_config method, otherwise use defaults
    try:
        kimi_config = llm_settings.get_kimi_config()
        model = kimi_config.model
        temperature = kimi_config.temperature
        max_tokens = kimi_config.max_tokens
        top_p = kimi_config.top_p if kimi_config.top_p is not None else 1.0
        api_key = kimi_config.moonshot_api_key
    except (AttributeError, KeyError):
        # Fallback to defaults if kimi config not available
        model = "moonshot-v1-32k"
        temperature = 0.7
        max_tokens = None
        top_p = 1.0
        api_key = None

    # Build model settings
    model_settings_dict = {
        'model': model,
        'temperature': temperature,
        'max_tokens': max_tokens,
        'top_p': top_p,
    }

    # Apply overrides to model settings
    if 'model_settings' in overrides:
        model_settings_dict.update(overrides['model_settings'])

    model_settings = KimiModelSettings(**model_settings_dict)

    # Build client config
    config_dict = {
        'model_settings': model_settings,
        'api_key': overrides.get('api_key', api_key),
        'base_url': overrides.get('base_url', "https://api.moonshot.cn/v1"),
        'debug': overrides.get('debug', llm_settings.debug),
        'timeout': overrides.get('timeout', 60.0),
        'max_retries': overrides.get('max_retries', 3)
    }

    return KimiClientConfig(**config_dict)
